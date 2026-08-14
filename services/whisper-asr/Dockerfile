# KUDOS local speech-to-text sidecar — faster-whisper.
# Runs entirely on the VPS (no API key): transcribes mic clips locally so
# KUDOS reliably "hears" users even when cloud STT quota runs out.
FROM python:3.11-slim

# ffmpeg is needed by faster-whisper / PyAV to decode webm/opus from browsers.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# faster-whisper (CTranslate2) — CPU inference, no GPU needed. Pinned core ver
# for stability; uvicorn/fastapi for the API surface (matches coqui sidecar).
RUN pip install --no-cache-dir --timeout=120 --retries=8 "faster-whisper==1.1.1" \
    uvicorn fastapi "python-multipart" pydantic

COPY server.py /app/server.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Model cache lives on a persistent volume so restarts skip the download.
ENV XDG_DATA_HOME=/models
ENV HF_HOME=/models/huggingface
ENV WHISPER_MODEL=small
ENV WHISPER_DEVICE=cpu
ENV WHISPER_COMPUTE_TYPE=int8

EXPOSE 8083
ENTRYPOINT ["/app/entrypoint.sh"]