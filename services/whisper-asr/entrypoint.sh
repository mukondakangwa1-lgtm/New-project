#!/bin/sh
# KUDOS Whisper ASR sidecar entrypoint.
# Downloads the faster-whisper model on first start (persistent /models
# volume), retrying until it completes, then launches the API server.
set -e

MODEL="${WHISPER_MODEL:-small}"
MODEL_DIR="$HF_HOME/models--Systran--faster-whisper-$MODEL"

echo "[whisper] checking for faster-whisper <$MODEL> model..."
if [ ! -d "$MODEL_DIR" ] || [ -z "$(ls -A "$MODEL_DIR" 2>/dev/null)" ]; then
  echo "[whisper] model not found — downloading into $HF_HOME (may take a few minutes)..."
  ATTEMPT=0
  while :; do
    ATTEMPT=$((ATTEMPT + 1))
    echo "[whisper] download attempt #$ATTEMPT"
    if python - <<PY
from faster_whisper import WhisperModel
WhisperModel("$MODEL", device="cpu", compute_type="int8")
print("model download complete")
PY
    then
      break
    fi
    echo "[whisper] download interrupted — retrying in 5s..."
    sleep 5
  done
else
  echo "[whisper] model already present — skipping download"
fi

exec uvicorn server:app --host 0.0.0.0 --port 8083