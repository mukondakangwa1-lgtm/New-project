# KUDOS local voice cloning sidecar — Coqui XTTS v2.
# Runs entirely on the VPS (no API key): voice cloning from reference audio
# and text-to-speech in a cloned voice, via the maintained `coqui-tts` fork.
FROM python:3.11-slim

# ffmpeg + espeak-ng are needed by the XTTS phonemizer / audio backend.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only torch first, then coqui-tts (0.27.4+ no longer bundles torch).
# Pinned: PyTorch <2.9 avoids the torchcodec requirement; coqui-tts 0.27.x
# patches the XttsConfig weights_only loader incompatibility; transformers<5
# keeps isin_mps_friendly available to TTS.
RUN pip install --no-cache-dir --timeout=120 --retries=8 torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --timeout=120 --retries=8 "coqui-tts==0.27.5" soundfile "transformers<5" \
        uvicorn fastapi "python-multipart" pydantic httpx

COPY server.py /app/server.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Model cache lives on a persistent volume so restarts skip the ~1.8GB download.
ENV XDG_DATA_HOME=/models
ENV HF_HOME=/models/huggingface
ENV COQUI_TOS_AGREED=1

EXPOSE 8082
ENTRYPOINT ["/app/entrypoint.sh"]
