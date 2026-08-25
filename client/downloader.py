import time
import urllib.request
import urllib.error

from .config import (
    SERVER_BASE_URL,
    REQUEST_TIMEOUT,
)


class HTTPDownloader:

    def __init__(
        self,
        throughput_estimator=None,
    ):
        self.throughput_estimator = (
            throughput_estimator
        )
        self.download_records = []

    def download(
        self,
        video_id,
        chunk_id,
        layer,
        layer_info,
    ):
        filename = layer_info["file"]
        url      = f"{SERVER_BASE_URL}/{filename}"

        print(f"[HTTP] GET {url}")

        start = time.perf_counter()

        try:
            with urllib.request.urlopen(
                url,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                status = response.status
                data   = response.read()

        except urllib.error.HTTPError as error:
            end = time.perf_counter()
            record = {
                "video_id":       video_id,
                "chunk_id":       chunk_id,
                "layer":          layer,
                "url":            url,
                "status":         error.code,
                "bytes":          0,
                "duration_ms":    (end - start) * 1000.0,
                "throughput_kbps": 0.0,
                "success":        False,
                "error":          str(error),
            }
            print(f"[HTTP] ERROR {error.code}")
            self.download_records.append(record)
            return None

        except Exception as error:
            end = time.perf_counter()
            record = {
                "video_id":       video_id,
                "chunk_id":       chunk_id,
                "layer":          layer,
                "url":            url,
                "status":         -1,
                "bytes":          0,
                "duration_ms":    (end - start) * 1000.0,
                "throughput_kbps": 0.0,
                "success":        False,
                "error":          str(error),
            }
            print(f"[HTTP] ERROR {error}")
            self.download_records.append(record)
            return None

        end      = time.perf_counter()
        duration = end - start
        size     = len(data)

        throughput_kbps = (
            size * 8 / duration / 1000.0
            if duration > 0
            else 0.0
        )

        record = {
            "video_id":        video_id,
            "chunk_id":        chunk_id,
            "layer":           layer,
            "url":             url,
            "status":          status,
            "bytes":           size,
            "duration_ms":     duration * 1000.0,
            "throughput_kbps": throughput_kbps,
            "success":         True,
        }

        self.download_records.append(record)

        # Update throughput estimator
        if self.throughput_estimator is not None:
            self.throughput_estimator.update(
                throughput_kbps
            )

        print(
            f"[HTTP] {status} "
            f"{size} bytes "
            f"{duration:.4f}s "
            f"{throughput_kbps:.1f} kbps"
        )

        return {
            "data":            data,
            "size":            size,
            "duration":        duration,
            "throughput_kbps": throughput_kbps,
            "record":          record,
        }
