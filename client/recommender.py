class Recommender:

    def __init__(
        self,
        metadata: dict
    ):

        self.metadata = metadata

    def recommend(
        self,
        max_videos=None
    ) -> list:

        playlist = [
            int(video["id"])
            for video in self.metadata["videos"]
        ]

        if max_videos is not None:

            playlist = playlist[
                :max_videos
            ]

        print(
            "[Recommender] Playlist:",
            playlist
        )

        return playlist
