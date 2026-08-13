"""KUDOS local voice sidecar — Coqui XTTS v2.

Zero-shot voice cloning and text-to-speech, fully local (no API key).

Endpoints:
  GET  /health                — readiness + model state
  POST /clone                 — (multipart "files") store reference audio -> voice_id
  GET  /voices                — list cloned voices on disk
  POST /tts                   — {text, voice_id?, language?, speaker?} -> {audio_b64, mime_type}
"""

from __future__ import annotations

import asyncio
import base64
import os
import threading
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

VOICES_DIR = os.environ.get("VOICES_DIR", "/data/voices")
os.makedirs(VOICES_DIR, exist_ok=True)
MODEL_NAME = os.environ.get("XTTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
DEFAULT_LANG = os.environ.get("XTTS_LANGUAGE", "en")

app = FastAPI(title="KUDOS Coqui Voice")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_tts = None
_tts_lock = threading.Lock()


def _model():
    """Load the XTTS model once (thread-safe)."""
    global _tts
    if _tts is not None:
        return _tts
    with _tts_lock:
        if _tts is None:
            from TTS.api import TTS

            _tts = TTS(MODEL_NAME).to("cpu")
    return _tts


class TTSRequest(BaseModel):
    text: str
    voice_id: str = ""
    language: str = ""
    speaker: str = ""


@app.get("/health")
async def health():
    return {
        "ok": True,
        "model_loaded": _tts is not None,
        "voices": [d for d in os.listdir(VOICES_DIR) if os.path.isdir(os.path.join(VOICES_DIR, d))],
    }


@app.post("/clone")
async def clone(files: list[UploadFile] = File(...)):
    """Store reference audio as a clone. XTTS is zero-shot, so 'cloning' just
    keeps the reference clips; /tts points at them via speaker_wav."""
    if not files:
        raise HTTPException(status_code=422, detail="No audio files uploaded")
    voice_id = uuid.uuid4().hex[:12]
    vdir = os.path.join(VOICES_DIR, voice_id)
    os.makedirs(vdir, exist_ok=True)

    refs = []
    for i, f in enumerate(files):
        data = await f.read()
        if len(data) < 4 * 1024:
            continue
        ext = (f.filename or f.content_type or "wav").split(".")[-1].split("/")[-1] or "wav"
        if ext not in ("wav", "mp3", "flac", "ogg", "webm", "m4a", "aac", "opus"):
            ext = "wav"
        path = os.path.join(vdir, f"ref_{i}.{ext}")
        with open(path, "wb") as fh:
            fh.write(data)
        refs.append(path)

    if not refs:
        raise HTTPException(status_code=422, detail="No usable reference audio uploaded")
    return {"voice_id": voice_id, "refs": len(refs)}


@app.get("/voices")
async def voices():
    out = []
    for d in os.listdir(VOICES_DIR):
        p = os.path.join(VOICES_DIR, d)
        if os.path.isdir(p):
            n = len([x for x in os.listdir(p)])
            out.append({"voice_id": d, "refs": n})
    return {"voices": out}


@app.post("/tts")
async def tts(req: TTSRequest):
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is required")

    kwargs = {"language": req.language or DEFAULT_LANG}

    if req.voice_id:
        vdir = os.path.join(VOICES_DIR, req.voice_id)
        if not os.path.isdir(vdir):
            raise HTTPException(status_code=404, detail=f"Voice {req.voice_id} not found")
        refs = sorted(os.path.join(vdir, f) for f in os.listdir(vdir) if f.startswith("ref_"))
        if not refs:
            raise HTTPException(status_code=404, detail=f"Voice {req.voice_id} has no reference audio")
        kwargs["speaker_wav"] = refs
    elif req.speaker:
        kwargs["speaker"] = req.speaker
    else:
        raise HTTPException(status_code=422, detail="Provide voice_id (cloned) or speaker (stock)")

    def _synthesize():
        out = "/tmp/kudos_xtts.wav"
        try:
            _model().tts_to_file(text=text, file_path=out, split_sentences=True, **kwargs)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"XTTS synthesis failed: {e}")
        with open(out, "rb") as fh:
            return fh.read()

    wav = await asyncio.to_thread(_synthesize)
    return {
        "audio_b64": base64.b64encode(wav).decode(),
        "mime_type": "audio/wav",
        "provider": "coqui",
    }
