# mục đích: lấy vầ xuwr lý metaadata
import json
import urllib.request


def load_metadata_from_url(
    url: str,
    timeout: int = 30
) -> dict:

    print(
        f"[Metadata] GET {url}"
    )

    with urllib.request.urlopen(
        url,
        timeout=timeout
    ) as response:

        raw = response.read()

    metadata = json.loads(
        raw.decode("utf-8")
    )

    validate_metadata(
        metadata
    )

    print(
        "[Metadata] Loaded "
        f"{len(metadata['videos'])} videos"
    )

    return metadata


def validate_metadata(
    metadata: dict
    ) -> None:
    if "videos" not in metadata:

        raise ValueError(
            "metadata.json không có key 'videos'"
        )

    if not isinstance(
        metadata["videos"],
        list
    ):

        raise ValueError(
            "'videos' phải là list"
        )

    for video in metadata["videos"]:

        if "id" not in video:

            raise ValueError(
                "Video thiếu 'id'"
            )

        if "chunks" not in video:

            raise ValueError(
                f"Video {video['id']} "
                "thiếu 'chunks'"
            )

        if not isinstance(
            video["chunks"],
            list
        ):

            raise ValueError(
                f"Video {video['id']} "
                "'chunks' phải là list"
            )

        for chunk in video["chunks"]:

            if "chunk_id" not in chunk:

                raise ValueError(
                    f"Video {video['id']} "
                    "có chunk thiếu chunk_id"
                )

            for layer in (
                "L0",
                "L1",
                "L2"
            ):

                if layer not in chunk:

                    raise ValueError(
                        f"Video {video['id']} "
                        f"chunk {chunk['chunk_id']} "
                        f"thiếu {layer}"
                    )

                info = chunk[layer]

                required_keys = [
                    "file",
                    "size_bytes",
                    "br_kbps",
                    "psnr",
                ]

                for key in required_keys:

                    if key not in info:

                        raise ValueError(
                            f"Video {video['id']} "
                            f"chunk {chunk['chunk_id']} "
                            f"{layer} thiếu '{key}'"
                        )

    print(
        "[Metadata] Validation OK"
    )


def build_video_index(
    metadata: dict
) -> dict:

    return {
        int(video["id"]): video
        for video in metadata["videos"]
    }


def build_chunk_index(
    video: dict
) -> dict:

    return {
        int(chunk["chunk_id"]): chunk
        for chunk in video["chunks"]
    }
