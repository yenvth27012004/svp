import time

from .config import (
    CHUNK_DURATION,
    B_MIN,
    K_NEXT,
    GAMMA,
)


class LayerSHORTScheduler:

    def __init__(
        self,
        metadata: dict,
        buffers: dict,
        throughput_provider,
    ):
        self.metadata = metadata

        self.video_index = {
            int(video["id"]): video
            for video in metadata["videos"]
        }

        self.buffers            = buffers
        self.throughput_provider = throughput_provider
        self.playlist           = []
        self.current_video_index = 0
        self.current_chunk      = 0
        self.last_decision_time_ms = 0.0

    def set_playlist(self, playlist):
        self.playlist = [int(v) for v in playlist]
        self.current_video_index = 0
        self.current_chunk = 0

    def current_video(self):
        if not self.playlist:
            return None
        if self.current_video_index >= len(self.playlist):
            return None
        return self.playlist[self.current_video_index]

    def next_video(self):
        next_index = self.current_video_index + 1
        if next_index >= len(self.playlist):
            return None
        return self.playlist[next_index]

    def get_chunk(self, video_id, chunk_id):
        vid = int(video_id)
        if vid not in self.video_index:
            return None
        for chunk in self.video_index[vid]["chunks"]:
            if int(chunk["chunk_id"]) == int(chunk_id):
                return chunk
        return None

    def target_layer(self, video_id, chunk_id):

        chunk = self.get_chunk(video_id, chunk_id)
        if chunk is None:
            return 0

        throughput   = float(self.throughput_provider())
        if throughput <= 0:
            return 0
        effective_bw = throughput * GAMMA  # GAMMA = 0.8

        l0_br  = float(chunk["L0"]["br_kbps"])
        l1_cum = float(chunk["L1"]["cum_br_kbps"])
        l2_cum = float(chunk["L2"]["cum_br_kbps"])

        if effective_bw < l0_br:
            return 0

        target = 0

        if effective_bw >= l1_cum:
            target = 1

        if effective_bw >= l2_cum:
            target = 2

        return target

    def decide(self):

        start         = time.perf_counter()
        current_video = self.current_video()

        if current_video is None:
            self._record_time(start)
            return None

        next_video     = self.next_video()
        current_buffer = self.buffers[current_video]

        # P1
        if (
            current_buffer.buffered_duration(CHUNK_DURATION)
            < B_MIN * CHUNK_DURATION
        ):
            chunk_id = current_buffer.next_missing_l0()
            if chunk_id is not None:
                self._record_time(start)
                return (current_video, chunk_id, 0, "P1")

        # P2
        if next_video is not None:
            next_buffer = self.buffers[next_video]
            if (
                next_buffer.buffered_duration(CHUNK_DURATION)
                < K_NEXT * CHUNK_DURATION
            ):
                chunk_id = next_buffer.next_missing_l0()
                if chunk_id is not None:
                    self._record_time(start)
                    return (next_video, chunk_id, 0, "P2")

        # P3
        for offset in [0, 1]:
            chunk_id      = self.current_chunk + offset
            if not current_buffer.has_chunk(chunk_id):
                continue
            current_layer = current_buffer.get_layer(chunk_id)
            if current_layer < 0:
                continue
            target = self.target_layer(current_video, chunk_id)
            if target > current_layer:
                self._record_time(start)
                return (
                    current_video,
                    chunk_id,
                    current_layer + 1,
                    "P3",
                )

        # P4
        if next_video is not None:
            next_buffer = self.buffers[next_video]
            if next_buffer.has_chunk(0):
                current_layer = next_buffer.get_layer(0)
                if current_layer >= 0:
                    target = self.target_layer(next_video, 0)
                    if target > current_layer:
                        self._record_time(start)
                        return (
                            next_video,
                            0,
                            current_layer + 1,
                            "P4",
                        )

        # P5
        for offset in [2, 3]:
            chunk_id      = self.current_chunk + offset
            if not current_buffer.has_chunk(chunk_id):
                continue
            current_layer = current_buffer.get_layer(chunk_id)
            if current_layer < 0:
                continue
            # P5 tối đa nâng lên L1
            target = min(1, self.target_layer(
                current_video, chunk_id
            ))
            if target > current_layer:
                self._record_time(start)
                return (
                    current_video,
                    chunk_id,
                    target,
                    "P5",
                )

        # P6
        if next_video is not None:
            next_buffer = self.buffers[next_video]
            for chunk_id in [1, 2]:
                if not next_buffer.has_chunk(chunk_id):
                    continue
                current_layer = next_buffer.get_layer(chunk_id)
                if current_layer < 0:
                    continue
                target = min(1, self.target_layer(
                    next_video, chunk_id
                ))
                if target > current_layer:
                    self._record_time(start)
                    return (
                        next_video,
                        chunk_id,
                        target,
                        "P6",
                    )

        # P7
        current_index = self.current_video_index

        for playlist_index in range(
            current_index + 2,
            min(len(self.playlist), current_index + 5),
        ):
            video_id = self.playlist[playlist_index]
            buffer   = self.buffers[video_id]

            if (
                buffer.buffered_duration(CHUNK_DURATION)
                < 2 * CHUNK_DURATION
            ):
                chunk_id = buffer.next_missing_l0()
                if chunk_id is not None:
                    self._record_time(start)
                    return (video_id, chunk_id, 0, "P7")

        self._record_time(start)
        return None

    def advance_playback(self, force_next_video=False):

        if force_next_video:
            self.current_video_index += 1
            self.current_chunk = 0
            return

        self.current_chunk += 1

        current_video = self.current_video()
        if current_video is None:
            return

        if current_video not in self.buffers:
            return

        buffer = self.buffers[current_video]
        if not buffer.has_chunk(self.current_chunk):
            self.current_video_index += 1
            self.current_chunk = 0

    def _record_time(self, start):
        self.last_decision_time_ms = (
            time.perf_counter() - start
        ) * 1000.0
