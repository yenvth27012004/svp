import time
import threading

from .config import CHUNK_DURATION


class StreamingSession:

    def __init__(
        self,
        playlist,
        video_index,
        buffers,
        scheduler,
        downloader,
        user_trace,
        metrics,
        user_id,
        trace_name,
    ):
        self.playlist    = playlist
        self.video_index = video_index
        self.buffers     = buffers
        self.scheduler   = scheduler
        self.downloader  = downloader
        self.user_trace  = user_trace
        self.metrics     = metrics
        self.user_id     = user_id
        self.trace_name  = trace_name

        self.state = {
            "cur_video_id":  playlist[0],
            "cur_play_time": 0.0,
            "session_end":   False,
        }

        self.state_lock     = threading.Lock()
        self.metrics_lock   = threading.Lock()
        self.scheduler_lock = threading.Lock()

        max_chunks = max(
            len(video_index[v]["chunks"])
            for v in playlist
        )

        self.stall_time = {
            v: [0.0] * max_chunks
            for v in playlist
        }

    # ========================================================
    # RUN
    # ========================================================

    def run(self):

        session_start = time.perf_counter()

        t_download = threading.Thread(
            target=self._download_thread,
            daemon=True,
        )
        t_playback = threading.Thread(
            target=self._playback_thread,
            daemon=True,
        )

        t_download.start()
        t_playback.start()

        t_playback.join()

        with self.state_lock:
            self.state["session_end"] = True

        t_download.join(timeout=10.0)

        return time.perf_counter() - session_start

    # ========================================================
    # WASTAGE
    # Gồm 2 phần giống simulation:
    # 1. Phần chunk cuối bị cắt giữa chừng (partial_chunk)
    # 2. Chunk đã tải nhưng không được phát (not_played)
    # ========================================================

    def _record_wastage(
        self,
        video_id,
        last_played_chunk,
    ):

        buffer = self.buffers[video_id]

        chunk_index = {
            int(c["chunk_id"]): c
            for c in self.video_index[video_id]["chunks"]
        }

        watch_time = self.user_trace.get_watch_time(
            self.user_id, video_id
        )

        # Nếu không có watch_time data
        # → dùng toàn bộ duration video
        if watch_time <= 0:
            n_chunks   = len(
                self.video_index[video_id]["chunks"]
            )
            watch_time = n_chunks * CHUNK_DURATION

        # ====================================================
        # PHẦN 1: Chunk cuối bị cắt giữa chừng
        # Giống simulation:
        #   wastage += bitrate * (chunk_end - view_time)
        # ====================================================

        if last_played_chunk in chunk_index:

            layer = buffer.get_layer(last_played_chunk)

            if layer >= 0:

                chunk_start     = last_played_chunk * CHUNK_DURATION
                chunk_end       = chunk_start + CHUNK_DURATION
                viewed_in_chunk = watch_time - chunk_start

                # Chỉ tính nếu user không xem hết chunk này
                if (
                    viewed_in_chunk > 0
                    and viewed_in_chunk < CHUNK_DURATION
                ):

                    unwatched_ratio = (
                        chunk_end - watch_time
                    ) / CHUNK_DURATION

                    chunk_meta   = chunk_index[last_played_chunk]
                    total_bytes  = int(
                        chunk_meta["L0"]["size_bytes"]
                    )

                    if layer >= 1:
                        total_bytes += int(
                            chunk_meta["L1"]["size_bytes"]
                        )

                    if layer >= 2:
                        total_bytes += int(
                            chunk_meta["L2"]["size_bytes"]
                        )

                    wasted_bytes = int(
                        total_bytes * unwatched_ratio
                    )

                    with self.metrics_lock:
                        self.metrics.add_wastage({
                            "user_id":      self.user_id,
                            "video_id":     video_id,
                            "chunk_id":     last_played_chunk,
                            "layer":        layer,
                            "bytes_wasted": wasted_bytes,
                            "reason":       "partial_chunk",
                        })

        # ====================================================
        # PHẦN 2: Chunk hoàn toàn không được phát
        # ====================================================

        for chunk_id in sorted(chunk_index.keys()):

            if chunk_id <= last_played_chunk:
                continue

            layer = buffer.get_layer(chunk_id)

            if layer < 0:
                continue

            chunk_meta   = chunk_index[chunk_id]
            wasted_bytes = int(
                chunk_meta["L0"]["size_bytes"]
            )

            if layer >= 1:
                wasted_bytes += int(
                    chunk_meta["L1"]["size_bytes"]
                )

            if layer >= 2:
                wasted_bytes += int(
                    chunk_meta["L2"]["size_bytes"]
                )

            with self.metrics_lock:
                self.metrics.add_wastage({
                    "user_id":      self.user_id,
                    "video_id":     video_id,
                    "chunk_id":     chunk_id,
                    "layer":        layer,
                    "bytes_wasted": wasted_bytes,
                    "reason":       "not_played",
                })

    # ========================================================
    # PSNR
    # ========================================================

    def _record_psnr(
        self,
        video_id,
        chunk_id,
        layer,
    ):

        chunk_meta = None

        for c in self.video_index[video_id]["chunks"]:
            if int(c["chunk_id"]) == chunk_id:
                chunk_meta = c
                break

        if chunk_meta is None:
            return

        psnr = float(chunk_meta[f"L{layer}"]["psnr"])

        with self.metrics_lock:
            self.metrics.add_psnr({
                "user_id":      self.user_id,
                "video_id":     video_id,
                "chunk_id":     chunk_id,
                "layer_played": layer,
                "psnr":         psnr,
            })

    # ========================================================
    # DOWNLOAD THREAD
    # ========================================================

    def _download_thread(self):

        idle_guard     = 0
        MAX_IDLE_COUNT = 200

        while True:

            with self.state_lock:
                if self.state["session_end"]:
                    break

            with self.scheduler_lock:
                decision = self.scheduler.decide()

            if decision is None:
                idle_guard += 1
                if idle_guard > MAX_IDLE_COUNT:
                    print(
                        "[Download] idle quá lâu, "
                        "dừng download thread"
                    )
                    break
                time.sleep(0.1)
                continue

            idle_guard = 0

            (video_id, chunk_id, layer, priority) = decision

            if video_id not in self.video_index:
                continue

            buffer         = self.buffers[video_id]
            existing_layer = buffer.get_layer(chunk_id)

            if layer <= existing_layer:
                continue

            chunk = self.scheduler.get_chunk(
                video_id, chunk_id
            )
            if chunk is None:
                continue

            layer_info = chunk[f"L{layer}"]
            wt         = self.user_trace.get_watch_time(
                self.user_id, video_id
            )

            with self.metrics_lock:
                self.metrics.add_scheduler({
                    "user_id":          self.user_id,
                    "video_id":         video_id,
                    "chunk_id":         chunk_id,
                    "layer":            layer,
                    "priority":         priority,
                    "decision_time_ms": self.scheduler.last_decision_time_ms,
                    "watch_time_s":     wt,
                })

            print(
                f"[Scheduler] {priority} "
                f"v{video_id} c{chunk_id} L{layer}"
            )

            result = self.downloader.download(
                video_id=video_id,
                chunk_id=chunk_id,
                layer=layer,
                layer_info=layer_info,
            )

            if result is not None:

                buffer.set_layer(chunk_id, layer)

                record = dict(result["record"])
                record["user_id"]      = self.user_id
                record["watch_time_s"] = wt
                record["trace"]        = self.trace_name

                with self.metrics_lock:
                    self.metrics.add_download(record)

    # ========================================================
    # PLAYBACK THREAD
    # ========================================================

    def _playback_thread(self):

        while True:

            time.sleep(0.1)

            with self.state_lock:
                if self.state["session_end"]:
                    break
                cur_vid  = self.state["cur_video_id"]
                cur_play = self.state["cur_play_time"]

            watch_time = self.user_trace.get_watch_time(
                self.user_id, cur_vid
            )

            if watch_time <= 0:
                n_chunks   = len(
                    self.video_index[cur_vid]["chunks"]
                )
                watch_time = n_chunks * CHUNK_DURATION

            # ------------------------------------------------
            # Swipe theo watch_time
            # ------------------------------------------------

            if cur_play >= watch_time:

                last_played = int(cur_play / CHUNK_DURATION)

                # Ghi wastage trước khi swipe
                self._record_wastage(cur_vid, last_played)

                try:
                    cur_idx = self.playlist.index(cur_vid)
                except ValueError:
                    with self.state_lock:
                        self.state["session_end"] = True
                    break

                next_idx = cur_idx + 1

                # Hết playlist — video cuối
                if next_idx >= len(self.playlist):
                    with self.state_lock:
                        self.state["session_end"] = True
                    print("[Session] Playlist finished")
                    break

                next_vid = self.playlist[next_idx]

                print(
                    f"[Player] SWIPE "
                    f"v{cur_vid} "
                    f"play_time={cur_play:.1f}s "
                    f"watch_time={watch_time:.1f}s"
                )

                with self.state_lock:
                    self.state["cur_video_id"]  = next_vid
                    self.state["cur_play_time"] = 0.0

                with self.scheduler_lock:
                    self.scheduler.advance_playback(
                        force_next_video=True
                    )

                wt_next = self.user_trace.get_watch_time(
                    self.user_id, next_vid
                )

                print(
                    f"[Watch] "
                    f"user={self.user_id} "
                    f"video={next_vid} "
                    f"watch_time={wt_next:.3f}s"
                )

                continue

            # ------------------------------------------------
            # Buffer check
            # ------------------------------------------------

            buffer    = self.buffers[cur_vid]
            cur_chunk = int(cur_play / CHUNK_DURATION)

            has_l0 = (
                buffer.has_chunk(cur_chunk)
                and buffer.get_layer(cur_chunk) >= 0
            )

            if not has_l0:

                if cur_chunk < len(self.stall_time[cur_vid]):
                    self.stall_time[cur_vid][cur_chunk] += 0.1

                with self.metrics_lock:
                    self.metrics.add_playback({
                        "user_id":      self.user_id,
                        "video_id":     cur_vid,
                        "chunk_id":     cur_chunk,
                        "watch_time_s": watch_time,
                        "played":       0,
                        "stall_time_s": 0.1,
                    })

                print(
                    f"[Player] STALL "
                    f"v{cur_vid} c{cur_chunk}"
                )

            else:

                layer = buffer.get_layer(cur_chunk)

                with self.state_lock:
                    new_play = round(cur_play + 0.1, 4)
                    self.state["cur_play_time"] = new_play

                new_chunk = int(new_play / CHUNK_DURATION)

                if new_chunk > cur_chunk:

                    buffer.mark_played(cur_chunk)

                    self._record_psnr(
                        cur_vid, cur_chunk, layer
                    )

                    with self.scheduler_lock:
                        self.scheduler.advance_playback()
                        sched_video = (
                            self.scheduler.current_video()
                        )

                    print(
                        f"[Player] PLAY "
                        f"v{cur_vid} c{cur_chunk} "
                        f"layer={layer} "
                        f"play_time={cur_play:.1f}s"
                    )

                    # Scheduler tự nhảy video
                    # (hết chunk tự nhiên, không phải swipe)
                    if (
                        sched_video is not None
                        and sched_video != cur_vid
                    ):

                        wt_next = self.user_trace.get_watch_time(
                            self.user_id, sched_video
                        )

                        print(
                            f"[Watch] "
                            f"user={self.user_id} "
                            f"video={sched_video} "
                            f"watch_time={wt_next:.3f}s"
                        )

                        with self.state_lock:
                            self.state["cur_video_id"]  = sched_video
                            self.state["cur_play_time"] = 0.0

                with self.metrics_lock:
                    self.metrics.add_playback({
                        "user_id":      self.user_id,
                        "video_id":     cur_vid,
                        "chunk_id":     cur_chunk,
                        "watch_time_s": watch_time,
                        "played":       1,
                        "stall_time_s": 0.0,
                    })
