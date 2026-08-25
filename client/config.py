from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Apache URL — dùng MAHIMAHI_BASE nếu chạy trong Mahimahi
# nếu không có thì fallback về 127.0.0.1
_HOST = os.environ.get("MAHIMAHI_BASE", "127.0.0.1")

SERVER_BASE_URL = f"http://{_HOST}/videos"

METADATA_URL = f"{SERVER_BASE_URL}/metadata.json"

CHUNK_DURATION = 32 / 30
B_MIN = 2
K_NEXT = 2
GAMMA = 0.8
USER_ID = 0

WATCH_TIME_DIR = (
    PROJECT_ROOT / "data"
)

WATCH_TIME_VIDEO_ID_OFFSET = -1

MAX_VIDEOS = 100
MAX_ITERATIONS = 20000
REQUEST_TIMEOUT = 30

# OUTPUT
RESULTS_DIR = (
    PROJECT_ROOT / "results"
)
