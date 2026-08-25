#!/bin/bash
# Chạy LayerSHORT prototype với Mahimahi bandwidth trace.
# Dùng: ./run_with_trace.sh <trace.mahi> [user_id]
# Ví dụ: ./run_with_trace.sh dataset_mahimahi/Bus_B57/bus57_1.mahi 0
#   ./run_with_trace.sh dataset_mahimahi/Ferry/Ferry1.mahi 3

TRACE=${1} # $1 là đối số đầu tiên khi chạy scrip 
USER_ID=${2:-0} # đối số thứ 2 hoặc nếu không thêm đối số thứ 2 vào thì mặc định dùng user #0
PYTHON=/usr/bin/python3 # tạo 1 biến tên PYTHON chứa đừng dẫ pythhon 
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)" # chứa đường dẫn chứa file script này vd: media/fil/VR/Yen/svp

if [ -z "$TRACE" ]; then # kiểm tra xem trace đẫ được nhập chưa
    echo "Usage: $0 <trace.mahi> [user_id]" # nếu chưa thì in ra terminal .....
    echo ""
    echo "Available traces:"
    find dataset_mahimahi -name "*.mahi" | sort # tìm tất cả các file có đuôi .mahi sau đó xắp xếp
    exit 1
fi

if [ ! -f "$TRACE" ]; then
    echo "Trace file không tồn tại: $TRACE"
    echo "Chạy converter trước:"
    echo "  $PYTHON client/trace_converter.py"
    exit 1
fi

TRACE_NAME=$(basename "$TRACE" .mahi)
TRACE_GROUP=$(basename "$(dirname "$TRACE")")
echo "LayerSHORT HTTP Prototype + Mahimahi"
echo "Trace:   $TRACE_GROUP / $TRACE_NAME"
echo "User ID: $USER_ID"
echo "Python:  $($PYTHON --version 2>&1)"
echo ""

# Chạy trong Mahimahi shell
# mm-link dùng cùng 1 file cho uplink và downlink:
#   - downlink: Apache -> client (chunk download, quan trọng)
#   - uplink:   client -> Apache (HTTP request, nhỏ, không quan trọng)
#
# Mahimahi set env var $MAHIMAHI_BASE = IP của host
# bên ngoài shell. Apache chạy ở ngoài nên client
# phải dùng $MAHIMAHI_BASE thay vì 127.0.0.1.

cd "$SCRIPT_DIR"

mm-link "$TRACE" "$TRACE" -- bash -c "
    export MAHIMAHI_BASE=\$MAHIMAHI_BASE
    $PYTHON client/main.py \
        --user-id $USER_ID \
        --trace '$TRACE'
"
