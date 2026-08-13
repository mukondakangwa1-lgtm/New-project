#!/bin/sh
# KUDOS Coqui voice sidecar entrypoint.
# Downloads the XTTS v2 model on first start (persistent /models volume),
# retrying until it completes, then launches the API server.
set -e

MODEL_DIR="${XDG_DATA_HOME:-/models}/tts"
MODEL_TARGET="tts_models--multilingual--multi-dataset--xtts_v2"

echo "[coqui] checking for XTTS v2 model..."
if [ ! -d "$MODEL_DIR/$MODEL_TARGET" ] || [ -z "$(ls -A "$MODEL_DIR/$MODEL_TARGET" 2>/dev/null)" ]; then
  echo "[coqui] model not found — downloading (~1.8GB) into $MODEL_DIR (may take several minutes)..."
  ATTEMPT=0
  while :; do
    ATTEMPT=$((ATTEMPT + 1))
    echo "[coqui] download attempt #$ATTEMPT"
    if python - <<'PY'
import os
from TTS.utils.manage import ModelManager
os.environ.setdefault("COQUI_TOS_AGREED", "1")
mm = ModelManager()
mm.download_model("tts_models/multilingual/multi-dataset/xtts_v2")
print("model download complete")
PY
    then
      break
    fi
    echo "[coqui] download interrupted — retrying in 5s..."
    sleep 5
  done
else
  echo "[coqui] model already present — skipping download"
fi

exec uvicorn server:app --host 0.0.0.0 --port 8082
