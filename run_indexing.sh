#!/bin/bash
# Batch indexing — process all TSV files through the pipeline
# Uses: local GPU (Qwen3-4B INT8) + local PostgreSQL
# Resume-safe: tracks completed files in .indexing_done, skips them on restart

TSV_DIR="/c/users/user/NLWeb/data/crawler/articles"
DONE_FILE="/c/users/user/NLWeb/data/.indexing_done"
LOG_FILE="/c/users/user/NLWeb/data/indexing.log"

touch "$DONE_FILE"

echo "=== NLWeb Batch Indexing ===" | tee -a "$LOG_FILE"
echo "Start: $(date)" | tee -a "$LOG_FILE"

TOTAL=$(ls "$TSV_DIR"/*.tsv 2>/dev/null | wc -l)
DONE=$(wc -l < "$DONE_FILE")
echo "Total: $TOTAL files, Already done: $DONE, Remaining: $((TOTAL - DONE))" | tee -a "$LOG_FILE"

cd /c/users/user/NLWeb/code/python

for tsv_file in "$TSV_DIR"/*.tsv; do
    BASENAME=$(basename "$tsv_file")

    # Skip already completed files
    if grep -qF "$BASENAME" "$DONE_FILE" 2>/dev/null; then
        continue
    fi

    echo "[$(date +%H:%M:%S)] Processing: $BASENAME" | tee -a "$LOG_FILE"

    # Run pipeline — capture output, don't let failures stop the loop
    if OUTPUT=$(python -m indexing.pipeline "$tsv_file" --resume 2>&1); then
        SUCCESS=$(echo "$OUTPUT" | grep "^Success:" | awk '{print $2}' || echo "?")
        FAILED=$(echo "$OUTPUT" | grep "^Failed:" | awk '{print $2}' || echo "?")
        CHUNKS=$(echo "$OUTPUT" | grep "^Total chunks:" | awk '{print $3}' || echo "?")
        PG_ARTICLES=$(echo "$OUTPUT" | grep "^PostgreSQL articles:" | awk '{print $3}' || echo "?")
        PG_CHUNKS=$(echo "$OUTPUT" | grep "^PostgreSQL chunks:" | awk '{print $3}' || echo "?")

        echo "  Success=$SUCCESS Failed=$FAILED Chunks=$CHUNKS (DB: $PG_ARTICLES articles, $PG_CHUNKS chunks)" | tee -a "$LOG_FILE"

        # Mark file as done
        echo "$BASENAME" >> "$DONE_FILE"
    else
        echo "  ERROR: pipeline failed (exit $?), skipping" | tee -a "$LOG_FILE"
        echo "$OUTPUT" | tail -5 | tee -a "$LOG_FILE"
    fi
done

echo "=== Batch complete: $(date) ===" | tee -a "$LOG_FILE"
