#!/bin/bash
PYTHON=/usr/bin/python3
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TRACE_DIR="$SCRIPT_DIR/dataset_mahimahi"
RESULTS_DIR="$SCRIPT_DIR/results"
N_USERS=50

cd "$SCRIPT_DIR"

if [ ! -d "$TRACE_DIR" ]; then
    echo "[ERROR] Chưa có dataset_mahimahi/"
    echo "Chạy trước: $PYTHON client/trace_converter.py"
    exit 1
fi

TRACES=$(find "$TRACE_DIR" -name "*.mahi" | sort)
N_TRACES=$(echo "$TRACES" | wc -l)
total=$(($N_USERS * $N_TRACES))
current=0
success=0
failed=0
skipped=0

echo "----LayerSHORT----"
echo "Users:  $N_USERS (user 0 .. $(($N_USERS - 1)))"
echo "Traces: $N_TRACES"
echo "Total:  $total sessions"
echo ""

for trace in $TRACES; do

    trace_group=$(basename "$(dirname "$trace")")
    trace_name=$(basename "$trace" .mahi)

    for user_id in $(seq 0 $(($N_USERS - 1))); do

        current=$(($current + 1))
        out_dir="$RESULTS_DIR/${trace_group}/${trace_name}/user_${user_id}"

        if [ -f "$out_dir/summary.csv" ]; then
            skipped=$(($skipped + 1))
            echo "[$current/$total] SKIP $trace_group/$trace_name user=$user_id"
            continue
        fi

        echo ""
        echo "[$current/$total] $trace_group/$trace_name user=$user_id"
        # Không redirect — hiện log thẳng ra terminal
        mm-link "$trace" "$trace" -- bash -c "
            export MAHIMAHI_BASE=\$MAHIMAHI_BASE
            $PYTHON $SCRIPT_DIR/client/main.py \
                --user-id $user_id \
                --trace '$trace' \
                --output-dir '$out_dir'
        "

        if [ $? -eq 0 ]; then
            success=$(($success + 1))
            echo "$trace_group/$trace_name user=$user_id"
        else
            failed=$(($failed + 1))
            echo "[FAILED] $trace_group/$trace_name user=$user_id"
        fi

    done

done

echo ""
echo "DONE"
echo "  success: $success"
echo "  failed:  $failed"
echo "  skipped: $skipped"
echo "  total:   $total"
