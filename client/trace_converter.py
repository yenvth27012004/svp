import re
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_bw_mbps(line: str) -> float:
    """
    Parse các định dạng:
      - "3.97,Mbits/sec"
      - "3.97,Mbits/sec,,,"
      - "512,Kbits/sec"
      - "512,Kbits/sec,,,"
    Trả về Mbps dạng float, hoặc -1.0 nếu không parse được.
    """
    line = line.strip()
    if not line:
        return -1.0

    # Bắt số + đơn vị, bỏ qua dấu phẩy thừa ở cuối
    match = re.match(
        r"([0-9]*\.?[0-9]+)\s*,\s*(M|K)bits/sec",
        line,
        re.IGNORECASE,
    )

    if not match:
        return -1.0

    value = float(match.group(1))
    unit  = match.group(2).upper()

    if unit == "M":
        return value
    elif unit == "K":
        return value / 1000.0

    return -1.0


def csv_to_mahimahi(
    input_csv: str,
    output_path: str,
    packet_size_bytes: int = 1500,
):
    """
    Convert trace CSV sang Mahimahi format.

    Mahimahi format:
        mỗi dòng = 1 timestamp (ms)
        số dòng trong 1 giây = số packet 1500-byte được phép

    BW = 0 → không ghi packet nào trong giây đó
           → Mahimahi sẽ tái hiện đúng khoảng stall
    """

    entries = []

    with open(input_csv, "r", encoding="utf-8") as f:
        for line in f:
            bw = parse_bw_mbps(line)
            if bw >= 0:  # giữ cả BW=0, bỏ dòng không parse được
                entries.append(bw)

    if not entries:
        print(f"[Converter] SKIP (rỗng hoặc không parse được): {input_csv}")
        return

    os.makedirs(
        os.path.dirname(os.path.abspath(output_path)),
        exist_ok=True,
    )

    zero_seconds = sum(1 for bw in entries if bw == 0)

    with open(output_path, "w") as f_out:

        t_ms = 0

        for bw_mbps in entries:

            if bw_mbps == 0:
                # Không ghi packet nào → Mahimahi hiểu là BW=0 giây này
                t_ms += 1000
                continue

            bytes_per_sec = bw_mbps * 1_000_000 / 8

            n_packets = int(
                bytes_per_sec / packet_size_bytes
            )

            if n_packets < 1:
                n_packets = 1

            if n_packets == 1:
                f_out.write(f"{t_ms}\n")
            else:
                interval = 1000.0 / n_packets
                for i in range(n_packets):
                    ts = int(t_ms + i * interval)
                    f_out.write(f"{ts}\n")

            t_ms += 1000

    print(
        f"[Converter] {input_csv}"
        f" -> {output_path}"
        f" ({len(entries)} giây,"
        f" {zero_seconds} giây BW=0)"
    )


def convert_all_traces(
    dataset_dir: str = str(PROJECT_ROOT / "dataset"),
    output_dir: str  = str(PROJECT_ROOT / "dataset_mahimahi"),
):
    """
    Convert toàn bộ CSV trong dataset_dir
    sang Mahimahi format, giữ nguyên cấu trúc folder.
    """

    dataset_path = Path(dataset_dir)
    output_path  = Path(output_dir)

    if not dataset_path.exists():
        print(f"[Converter] Không tìm thấy: {dataset_dir}")
        return

    converted = 0
    skipped   = 0

    for csv_file in sorted(
        dataset_path.rglob("*.csv")
    ):

        relative = csv_file.relative_to(dataset_path)

        out_file = (
            output_path
            / relative.parent
            / (csv_file.stem + ".mahi")
        )

        csv_to_mahimahi(
            str(csv_file),
            str(out_file),
        )

        if out_file.exists():
            converted += 1
        else:
            skipped += 1

    print(
        f"\n[Converter] Done: "
        f"{converted} converted, "
        f"{skipped} skipped"
        f" -> {output_dir}/"
    )


if __name__ == "__main__":
    convert_all_traces()
