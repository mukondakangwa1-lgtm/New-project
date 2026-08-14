"""KUDOS local speech-to-text sidecar — faster-whisper.

Runs entirely on the VPS (no API key, no credits): transcribes the mic clips
the moment the browser sends them. Because it's local, KUDOS "hears" reliably
even when cloud STT quota runs out or a model is deprecated.

Endpoints:
  GET  /health                — readiness + model state
  POST /transcribe            — (multipart "file" [+ "language"]) -> {text, language}
"""

from __future__ import annotations

import os
import threading

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

MODEL_NAME = os.environ.get("WHISPER_MODEL", "small")
DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")
DEFAULT_LANG = os.environ.get("WHISPER_LANGUAGE", "en")

app = FastAPI(title="KUDOS Whisper ASR")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_model = None
_model_lock = threading.Lock()


def _get_model():
    """Load the faster-whisper model once (thread-safe)."""
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel

            _model = WhisperModel(MODEL_NAME, device=DEVICE, compute_type=COMPUTE_TYPE)
    return _model


@app.get("/health")
async def health():
    return {"ok": True, "status": "ready", "model": MODEL_NAME, "device": DEVICE}


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form(""),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="empty audio file")
    if len(content) < 2048:
        raise HTTPException(status_code=422, detail="audio too short to transcribe")

    mime = (file.content_type or "audio/webm").split(";")[0].strip()
    ext = {"audio/mpeg": ".mp3", "audio/mp4": ".m4a", "audio/x-m4a": ".m4a",
           "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/ogg": ".ogg"}.get(mime, ".webm")

    tmp_path = f"/tmp/kudos_asr_{os.getpid()}{ext}"
    with open(tmp_path, "wb") as fh:
        fh.write(content)
    try:
        segments, info = await __run_transcribe(tmp_path, language)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    text = " ".join(seg for seg in segments if isinstance(seg, str))
    return {"text": text, "language": info or DEFAULT_LANG}


async def __run_transcribe(path: str, language: str) -> tuple[list[str], str]:
    """Run faster-whisper off the event loop; keep the audio-level language."""

    def _run():
        gen, info = _get_model().transcribe(
            path,
            language=(language or DEFAULT_LANG or None),
            vad_filter=False,
            beam_size=5,
        )
        return [seg.text for seg in gen], (getattr(info, "language", "") or DEFAULT_LANG)

    import asyncio

    segments, lang = await asyncio.to_thread(_run)
    return segments, lang