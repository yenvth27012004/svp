from dataclasses import dataclass


@dataclass
class ChunkState:

    #-1: chưa tải L0
    #0: L0
    #1: L0 + L1
    #2: L0 + L1 + L2

    layer: int = -1


class VideoBuffer:

    def __init__(
        self,
        video: dict
    ):

        self.video_id = int(
            video["id"]
        )

        self.chunks = {
            int(chunk["chunk_id"]):
                ChunkState()

            for chunk in video["chunks"]
        }

        self.played = set()

    def get_layer(
        self,
        chunk_id: int
    ) -> int:

        chunk_id = int(chunk_id)

        if chunk_id not in self.chunks:

            return -1

        return self.chunks[
            chunk_id
        ].layer

    def set_layer(
        self,
        chunk_id: int,
        layer: int
    ):

        chunk_id = int(chunk_id)

        if chunk_id not in self.chunks:

            raise ValueError(
                f"Video {self.video_id}: "
                f"chunk {chunk_id} không tồn tại"
            )

        old_layer = (
            self.chunks[
                chunk_id
            ].layer
        )

        if layer < old_layer:

            raise ValueError(
                f"Layer không thể giảm "
                f"{old_layer} -> {layer}"
            )

        self.chunks[
            chunk_id
        ].layer = int(layer)

        print(
            f"[Buffer] "
            f"v{self.video_id} "
            f"c{chunk_id}: "
            f"L{old_layer} -> L{layer}"
        )

    def has_chunk(
        self,
        chunk_id: int
    ) -> bool:

        return (
            int(chunk_id)
            in self.chunks
        )

    def mark_played(
        self,
        chunk_id: int
    ):

        self.played.add(
            int(chunk_id)
        )

    def is_played(
        self,
        chunk_id: int
    ) -> bool:

        return (
            int(chunk_id)
            in self.played
        )

    def buffered_duration(
        self,
        chunk_duration: float
    ) -> float:

        duration = 0.0

        for cid, state in (
            self.chunks.items()
        ):

            if (
                state.layer >= 0
                and cid not in self.played
            ):

                duration += (
                    chunk_duration
                )

        return duration

    def next_missing_l0(self):

        for cid in sorted(
            self.chunks
        ):

            if (
                self.chunks[cid].layer
                < 0
            ):

                return cid

        return None

    def highest_layer(
        self,
        chunk_id
    ) -> int:

        return self.get_layer(
            chunk_id
        )
