import os
import sys
import argparse
import threading

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from client.config import (
    METADATA_URL,
    MAX_VIDEOS,
    USER_ID,
    WATCH_TIME_DIR,
    WATCH_TIME_VIDEO_ID_OFFSET,
    RESULTS_DIR,
    B_MIN,
    K_NEXT,
)

from client.metadata import load_metadata_from_url, build_video_index
from client.user_trace import UserTrace
from client.recommender import Recommender
from client.buffer import VideoBuffer
from client.scheduler import LayerSHORTScheduler
from client.downloader import HTTPDownloader
from client.metrics import Metrics
from client.session import StreamingSession

class ThroughputEstimator:

    def __init__(self):
        self.current_kbps = -1.0
        self._lock = threading.Lock()

    def update(self, throughput_kbps):
        if throughput_kbps is not None and throughput_kbps > 0:
            with self._lock:
                self.current_kbps = throughput_kbps

    def get(self):
        with self._lock:
            return self.current_kbps


def preload_initial_buffer(
    playlist,
    video_index,
    buffers,
    downloader,
    metrics,
    user_trace,
    user_id,
    trace_name,
    b_min,
    k_next,
):
    print()
    print("Khởi tạo buffer cho v0 và v1")

    def download_chunk(video_id, chunk_id, target_layer):
        buffer = buffers[video_id]

        chunk_meta = None
        for c in video_index[video_id]["chunks"]:
            if int(c["chunk_id"]) == chunk_id:
                chunk_meta = c
                break

        if chunk_meta is None:
            print(
                f"SKIP "
                f"v{video_id} c{chunk_id} "
                f"(không tìm thấy)"
            )
            return

        wt = user_trace.get_watch_time(
            user_id, video_id
        )

        for layer in range(target_layer + 1):

            if buffer.get_layer(chunk_id) >= layer:
                continue

            layer_info = chunk_meta[f"L{layer}"]

            print(
                f"[Preload] "
                f"v{video_id} c{chunk_id} L{layer}"
            )

            result = downloader.download(
                video_id=video_id,
                chunk_id=chunk_id,
                layer=layer,
                layer_info=layer_info,
            )

            if result is None:
                print(
                    f"FAILED "
                    f"v{video_id} c{chunk_id} L{layer}"
                )
                return

            buffer.set_layer(chunk_id, layer)

            record = dict(result["record"])
            record["user_id"]      = user_id
            record["watch_time_s"] = wt
            record["trace"]        = trace_name

            metrics.add_download(record)

    if len(playlist) >= 1:

        v0 = playlist[0]

        download_chunk(v0, 0, 2)

        for c in range(1, b_min + 1):
            if buffers[v0].has_chunk(c):
                download_chunk(v0, c, 0)

    if len(playlist) >= 2:

        v1 = playlist[1]

        download_chunk(v1, 0, 2)

        for c in range(1, k_next + 1):
            if buffers[v1].has_chunk(c):
                download_chunk(v1, c, 0)

    print("Done.")
    print()


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id",    type=int, default=None)
    parser.add_argument("--trace",      type=str, default=None)
    parser.add_argument("--output-dir", type=str, default=None)
    args = parser.parse_args()

    user_id = (
        args.user_id
        if args.user_id is not None
        else USER_ID
    )

    trace_name = (
        os.path.basename(args.trace)
        if args.trace
        else "no_trace"
    )

    if args.output_dir:
        output_dir = args.output_dir
    else:
        trace_stem = (
            os.path.splitext(trace_name)[0]
            if args.trace
            else "no_trace"
        )
        output_dir = os.path.join(
            str(RESULTS_DIR),
            trace_stem,
            f"user_{user_id}",
        )

    print("=" * 60)
    print("LayerSHORT HTTP Prototype")
    print(f"User:   {user_id}")
    print(f"Trace:  {trace_name}")
    print(f"Output: {output_dir}")
    print("=" * 60)

    metadata    = load_metadata_from_url(METADATA_URL)
    video_index = build_video_index(metadata)

    user_trace = UserTrace(
        data_dir=WATCH_TIME_DIR,
        video_id_offset=WATCH_TIME_VIDEO_ID_OFFSET,
    )
    user_trace.print_user(user_id)

    recommender = Recommender(metadata)
    playlist    = recommender.recommend(MAX_VIDEOS)

    if not playlist:
        print("Playlist rỗng")
        return

    buffers = {}
    for vid in playlist:
        if vid not in video_index:
            print(f"Video {vid} không có trong metadata")
            continue
        buffers[vid] = VideoBuffer(video_index[vid])

    if not buffers:
        print("Không có video buffer")
        return

    playlist = [v for v in playlist if v in buffers]

    throughput = ThroughputEstimator()

    scheduler = LayerSHORTScheduler(
        metadata=metadata,
        buffers=buffers,
        throughput_provider=throughput.get,
    )
    scheduler.set_playlist(playlist)

    downloader = HTTPDownloader(
        throughput_estimator=throughput
    )

    metrics = Metrics()

    preload_initial_buffer(
        playlist=playlist,
        video_index=video_index,
        buffers=buffers,
        downloader=downloader,
        metrics=metrics,
        user_trace=user_trace,
        user_id=user_id,
        trace_name=trace_name,
        b_min=B_MIN,
        k_next=K_NEXT,
    )

    session = StreamingSession(
        playlist=playlist,
        video_index=video_index,
        buffers=buffers,
        scheduler=scheduler,
        downloader=downloader,
        user_trace=user_trace,
        metrics=metrics,
        user_id=user_id,
        trace_name=trace_name,
    )

    wall_time = session.run()

    summary = metrics.summary()
    summary["session_wall_time_s"] = wall_time
    summary["user_id"]             = user_id
    summary["trace"]               = trace_name
    summary["playlist_size"]       = len(playlist)

    print()
    print("=" * 60)
    print("RESULT")
    print("=" * 60)

    for key, value in summary.items():
        print(f"{key}: {value}")

    metrics.save(
        output_dir=output_dir,
        summary=summary,
    )

    print()
    print(f"Results: {output_dir}")


if __name__ == "__main__":
    main()
