from pathlib import Path
import re


class UserTrace:
    FILE_PATTERN = re.compile(
        r"^watch_time(\d+)\.csv$"
    )

    def __init__(
        self,
        data_dir,
        video_id_offset=-1,
    ):
        self.data_dir = Path(data_dir)

        # offset để map file_number -> user_id
        # watch_time1.csv -> user 0: offset = -1
        self.user_id_offset = video_id_offset

        # (user_id, video_id) -> watch_time
        self.watch_time = {}

        self._load()

    def _load(self):

        if not self.data_dir.exists():
            raise FileNotFoundError(
                f"Không tìm thấy data directory: "
                f"{self.data_dir}"
            )

        files = []

        for path in self.data_dir.iterdir():

            if not path.is_file():
                continue

            match = self.FILE_PATTERN.match(
                path.name
            )

            if match is None:
                continue

            file_number = int(match.group(1))

            files.append((file_number, path))

        files.sort(key=lambda x: x[0])

        if not files:
            raise FileNotFoundError(
                f"Không tìm thấy "
                f"watch_time*.csv trong "
                f"{self.data_dir}"
            )

        print(
            f"[WatchTrace] Found "
            f"{len(files)} watch-time files"
        )

        for file_number, path in files:

            # watch_time1.csv -> user_id = 1 + (-1) = 0
            user_id = (
                file_number + self.user_id_offset
            )

            self._load_one_file(path, user_id)

        print(
            f"[WatchTrace] Loaded "
            f"{len(self.watch_time)} "
            f"user-video records"
        )

    def _load_one_file(
        self,
        path: Path,
        user_id: int,
    ):
        video_id = 0

        with path.open("r", encoding="utf-8") as f:

            for raw_line in f:

                line = raw_line.strip()

                if not line:
                    continue

                try:
                    watch_time = float(line)
                except ValueError:
                    # bỏ qua header hoặc dòng lỗi
                    continue

                self.watch_time[
                    (int(user_id), int(video_id))
                ] = watch_time

                video_id += 1
    def get_watch_time(
        self,
        user_id: int,
        video_id: int,
    ) -> float:

        return self.watch_time.get(
            (int(user_id), int(video_id)),
            0.0,
        )
    def get_user_watch_times(
        self,
        user_id: int,
    ) -> dict:

        result = {}

        for (uid, vid), watch_time in (
            self.watch_time.items()
        ):
            if uid == int(user_id):
                result[vid] = watch_time

        return result

    def print_user(self, user_id: int):

        records = self.get_user_watch_times(user_id)

        print(f"[WatchTrace] user={user_id}")

        for video_id in sorted(records):
            print(
                f"  video={video_id} "
                f"watch_time={records[video_id]:.3f}s"
            )
