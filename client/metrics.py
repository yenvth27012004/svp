import csv
import os


DOWNLOAD_FIELDS = [
    "user_id", "video_id", "chunk_id", "layer",
    "url", "status", "bytes", "duration_ms",
    "throughput_kbps", "success", "watch_time_s", "trace",
]

SCHEDULER_FIELDS = [
    "user_id", "video_id", "chunk_id", "layer",
    "priority", "decision_time_ms", "watch_time_s",
]

PLAYBACK_FIELDS = [
    "user_id", "video_id", "chunk_id",
    "watch_time_s", "played", "stall_time_s",
]

WASTAGE_FIELDS = [
    "user_id", "video_id", "chunk_id", "layer",
    "bytes_wasted", "reason",
]

PSNR_FIELDS = [
    "user_id", "video_id", "chunk_id",
    "layer_played", "psnr",
]


class Metrics:

    def __init__(self):

        self.downloads = []
        self.scheduler = []
        self.playback  = []
        self.wastage   = []
        self.psnr      = []


    def add_download(self, record):
        self.downloads.append(record)

    def add_scheduler(self, record):
        self.scheduler.append(record)

    def add_playback(self, record):
        self.playback.append(record)

    def add_wastage(self, record):
        self.wastage.append(record)

    def add_psnr(self, record):
        self.psnr.append(record)


    def summary(self):

        successful = [
            r for r in self.downloads
            if r.get("success", False)
        ]

        total_bytes = sum(
            r["bytes"] for r in successful
        )

        total_dl_time = (
            sum(r["duration_ms"] for r in successful)
            / 1000.0
        )

        avg_throughput = (
            total_bytes * 8 / total_dl_time / 1000.0
            if total_dl_time > 0
            else 0.0
        )

        total_stall = sum(
            r.get("stall_time_s", 0.0)
            for r in self.playback
        )

        avg_sched_time = (
            sum(r["decision_time_ms"] for r in self.scheduler)
            / len(self.scheduler)
            if self.scheduler else 0.0
        )

        # Wastage ratio
        total_wasted = sum(
            r["bytes_wasted"] for r in self.wastage
        )

        wastage_ratio = (
            total_wasted / total_bytes * 100.0
            if total_bytes > 0
            else 0.0
        )

        # PSNR trung bình
        avg_psnr = (
            sum(r["psnr"] for r in self.psnr)
            / len(self.psnr)
            if self.psnr else 0.0
        )

        return {
            "http_requests":                len(self.downloads),
            "successful_requests":          len(successful),
            "downloaded_bytes":             total_bytes,
            "download_time_s":              total_dl_time,
            "average_throughput_kbps":      avg_throughput,
            "stall_time_s":                 total_stall,
            "scheduler_decisions":          len(self.scheduler),
            "average_scheduler_ms":         avg_sched_time,
            "wasted_bytes":                 total_wasted,
            "wastage_ratio_pct":            round(wastage_ratio, 4),
            "average_psnr_db":              round(avg_psnr, 4),
        }


    def save(self, output_dir, summary):

        os.makedirs(output_dir, exist_ok=True)

        self._save_csv(
            output_dir, "downloads.csv",
            self.downloads, DOWNLOAD_FIELDS,
        )
        self._save_csv(
            output_dir, "scheduler_decisions.csv",
            self.scheduler, SCHEDULER_FIELDS,
        )
        self._save_csv(
            output_dir, "playback.csv",
            self.playback, PLAYBACK_FIELDS,
        )
        self._save_csv(
            output_dir, "wastage.csv",
            self.wastage, WASTAGE_FIELDS,
        )
        self._save_csv(
            output_dir, "psnr.csv",
            self.psnr, PSNR_FIELDS,
        )

        summary_path = os.path.join(
            output_dir, "summary.csv"
        )

        with open(
            summary_path, "w",
            newline="", encoding="utf-8"
        ) as f:
            writer = csv.DictWriter(
                f, fieldnames=summary.keys()
            )
            writer.writeheader()
            writer.writerow(summary)

        print(f"[Metrics] Saved to {output_dir}")

    @staticmethod
    def _save_csv(output_dir, filename, rows, fieldnames):

        if not rows:
            return

        path = os.path.join(output_dir, filename)

        with open(
            path, "w",
            newline="", encoding="utf-8"
        ) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames,
                extrasaction="ignore",
                restval="",
            )
            writer.writeheader()
            writer.writerows(rows)
