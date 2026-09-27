#!/usr/bin/env bash
# Sequential benchmark queue: for each L40S-target model, run the frozen
# 5-page smoke set first; only on a clean smoke (exit 0) run the full 462
# pages. A failed/blocked smoke records the blocker (in the run report and
# this log) and the queue continues. One model at a time on the GPU.
# MBZUAI/AIN is intentionally absent: its documented OCR prompt is UNRESOLVED
# (see configs/models/MBZUAI__AIN.yaml) and it is excluded from this session.
set -u
cd "$(dirname "$0")/.."
PY=.venv-gpu/bin/python
LOG=outputs/queue_log.txt
echo "queue start: $(date -u +%FT%TZ)" | tee -a "$LOG"

run_model() {
  local model="$1"; shift
  echo "=== $model smoke: $(date -u +%FT%TZ)" | tee -a "$LOG"
  if $PY scripts/run_official.py --model-id "$model" --scope smoke "$@" \
      >>"$LOG" 2>&1; then
    echo "=== $model smoke PASS -> full: $(date -u +%FT%TZ)" | tee -a "$LOG"
    if $PY scripts/run_official.py --model-id "$model" --scope full "$@" \
        >>"$LOG" 2>&1; then
      echo "=== $model full COMPLETE: $(date -u +%FT%TZ)" | tee -a "$LOG"
    else
      echo "!!! $model full had failures (see report): $(date -u +%FT%TZ)" | tee -a "$LOG"
    fi
  else
    echo "!!! $model smoke FAILED/BLOCKED -> skipping full: $(date -u +%FT%TZ)" | tee -a "$LOG"
  fi
}

run_model "amad-iq/amad-vlm6" --chat-style raw_text --think-end-marker '</think>'
run_model "amad-iq/amad-vlm5" --chat-style raw_text --think-end-marker '</think>'
run_model "YasserSami/Qari-OCR-0.4.0-VL-4B-Instruct" --chat-style raw_text --base-repo Qwen/Qwen3-VL-4B-Instruct
run_model "context212/alhazen-ocr" --chat-style raw_text --base-repo unsloth/Qwen3-VL-2B-Instruct
run_model "sherif1313/Arabic-GLM-OCR-v2" --chat-style raw_text
run_model "AhmedZaky1/DIMI-Arabic-OCR-V2" --chat-style raw_text --base-repo Qwen/Qwen2.5-VL-7B-Instruct
run_model "loay/Arabic-OCR-DeepSeek-OCR-2" --chat-style no_template --processor-repo unsloth/DeepSeek-OCR-2
run_model "hastyle/olmOCR-arabic-lora-v2" --chat-style raw_text --base-repo allenai/olmOCR-2-7B-1025 --processor-repo allenai/olmOCR-2-7B-1025

echo "queue end: $(date -u +%FT%TZ)" | tee -a "$LOG"
