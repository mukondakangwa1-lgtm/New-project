"""KUDOS Voice Providers — cloning, TTS and voice conversion across backends.

Unifies two cloning-capable backends behind one interface:
  - ElevenLabs   (cloud, needs ELEVENLABS_API_KEY)
  - Coqui XTTS   (local sidecar, needs COQUI_TTS_URL — no API key)

The superadmin's signature voice can be cloned by either. Voice ids returned
by Coqui are namespaced `coqui:<id>` so callers know which provider owns a
voice (ElevenLabs ids are used bare).
"""

from __future__ import annotations

import base64

import httpx

from app.core.config import settings
from app.core.llm_engine import get_api_key

_ELEVEN = "https://api.elevenlabs.io"
_OPENAI_AUDIO = "https://api.openai.com/v1/audio"
COQUI_PREFIX = "coqui:"

# OpenAI TTS stock voices (fallback voices KUDOS can speak with).
OPENAI_TTS_VOICES = ["alloy", "ash", "ballad", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer"]


def eleven_key() -> str | None:
    return settings.ELEVENLABS_API_KEY or get_api_key("elevenlabs") or None


def coqui_url() -> str:
    return (settings.COQUI_TTS_URL or "").strip().rstrip("/")


def is_coqui_voice(voice_id: str) -> bool:
    return (voice_id or "").startswith(COQUI_PREFIX)


def coqui_available() -> bool:
    return bool(coqui_url())


def clone_provider() -> str:
    """Which provider should clone the signature voice."""
    prefs = ["elevenlabs", "coqui"]
    chosen = (settings.VOICE_CLONE_PROVIDER or "").strip()
    if chosen in prefs:
        # Honour explicit choice only if that provider is actually available.
        if chosen == "elevenlabs" and eleven_key():
            return "elevenlabs"
        if chosen == "coqui" and coqui_available():
            return "coqui"
    if eleven_key():
        return "elevenlabs"
    if coqui_available():
        return "coqui"
    return ""


# ──────────────────────────────────────────────
# CLONING
# ──────────────────────────────────────────────


async def clone_voice(samples: list[dict], name: str = "KUDOS") -> dict:
    """Clone a voice from reference audio. Auto-picks the available provider.
    Returns {"voice_id", "name", "provider"} or {"error": ...}."""
    provider = clone_provider()
    if not provider:
        return {
            "error": (
                "No voice-cloning provider available — add ELEVENLABS_API_KEY "
                "or enable the local Coqui sidecar (COQUI_TTS_URL)"
            )
        }
    if provider == "elevenlabs":
        return await _eleven_clone(samples, name)
    return await _coqui_clone(samples, name)


async def _eleven_clone(samples: list[dict], name: str) -> dict:
    key = eleven_key()
    if not key:
        return {"error": "ElevenLabs API key not configured"}
    files = []
    for i, s in enumerate(samples):
        files.append(
            (
                "files",
                (
                    f"sample_{i}.{s.get('mime', 'audio/webm').split('/')[-1].split(';')[0]}",
                    s["data"],
                    s.get("mime", "audio/webm"),
                ),
            )
        )
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            res = await client.post(
                f"{_ELEVEN}/v1/voices/add",
                headers={"xi-api-key": key},
                data={
                    "name": name,
                    "description": f"Cloned via Digital Campus KUDOS voice engine ({name})",
                    "labels": '{"accent": "", "gender": "", "age": ""}',
                    "remove_background_noise": "true",
                },
                files=files,
            )
            if res.status_code == 200:
                voice_id = (res.json().get("voice_id") or "").strip()
                if voice_id:
                    return {"voice_id": voice_id, "name": name, "provider": "elevenlabs"}
                return {"error": "ElevenLabs did not return a voice id"}
            return {"error": f"ElevenLabs clone failed ({res.status_code}): {res.text[:200]}"}
    except Exception as e:
        return {"error": f"ElevenLabs clone error: {e}"}


async def _coqui_clone(samples: list[dict], name: str) -> dict:
    url = coqui_url()
    if not url:
        return {"error": "Coqui sidecar not configured (COQUI_TTS_URL)"}
    files = []
    for i, s in enumerate(samples):
        ext = s.get("mime", "audio/webm").split("/")[-1].split(";")[0] or "wav"
        files.append(("files", (f"ref_{i}.{ext}", s["data"], s.get("mime", "audio/webm"))))
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            res = await client.post(f"{url}/clone", files=files)
            if res.status_code == 200:
                voice_id = (res.json().get("voice_id") or "").strip()
                if voice_id:
                    return {
                        "voice_id": f"{COQUI_PREFIX}{voice_id}",
                        "name": name,
                        "provider": "coqui",
                    }
                return {"error": "Coqui sidecar did not return a voice id"}
            return {"error": f"Coqui clone failed ({res.status_code}): {res.text[:200]}"}
    except Exception as e:
        return {"error": f"Coqui clone error: {e}"}


# ──────────────────────────────────────────────
# TEXT-TO-SPEECH
# ──────────────────────────────────────────────


def tts_provider_preference() -> list[str]:
    """Provider order for TTS, auto-detected."""
    order = []
    chosen = (settings.VOICE_TTS_PROVIDER or "").strip()
    if chosen:
        order = [chosen]
    if eleven_key():
        order.append("elevenlabs")
    if coqui_available():
        order.append("coqui")
    if get_api_key("openai"):
        order.append("openai")
    return order


async def synthesize(text: str, voice_id: str = "", default_voice: str = "") -> dict:
    """Speak text. Tries providers in preference order. Returns
    {"mime_type", "data"(base64), "provider"} or {"error": ...}."""
    text = (text or "").strip()
    if not text:
        return {"error": "Nothing to speak"}

    providers = tts_provider_preference()
    if not providers:
        return {"error": "No TTS provider configured (ElevenLabs, Coqui or OpenAI key needed)"}

    # If the voice is a Coqui clone, Coqui must be first in line.
    if voice_id and is_coqui_voice(voice_id) and coqui_available():
        providers = ["coqui"] + [p for p in providers if p != "coqui"]

    for p in providers:
        out = {}
        if p == "elevenlabs" and (voice_id or default_voice):
            out = await _eleven_tts(text, voice_id or default_voice)
        elif p == "coqui" and (voice_id or default_voice):
            out = await _coqui_tts(text, voice_id, default_voice)
        elif p == "openai":
            out = await _openai_tts(text, default_voice or settings.OPENAI_TTS_VOICE)
        if out.get("data"):
            return out
    return {"error": "TTS providers returned no audio"}


async def _coqui_tts(text: str, voice_id: str = "", default_voice: str = "") -> dict:
    """Synthesize via the local Coqui sidecar. Accepts a cloned `coqui:<id>`
    voice or falls back to a stock speaker (default_voice) if no clone."""
    url = coqui_url()
    if not url:
        return {}
    payload: dict = {"text": text, "language": settings.COQUI_TTS_LANGUAGE}
    if voice_id and is_coqui_voice(voice_id):
        payload["voice_id"] = voice_id[len(COQUI_PREFIX):]
    elif default_voice and not is_coqui_voice(default_voice):
        payload["speaker"] = default_voice
    else:
        payload["voice_id"] = ""
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            res = await client.post(f"{url}/tts", json=payload)
            if res.status_code == 200:
                data = res.json()
                if data.get("audio_b64"):
                    return {
                        "mime_type": data.get("mime_type", "audio/wav"),
                        "data": data["audio_b64"],
                        "provider": "coqui",
                    }
            return {"error": f"Coqui TTS failed ({res.status_code}): {res.text[:200]}"}
    except Exception as e:
        return {"error": f"Coqui TTS error: {e}"}


async def _eleven_tts(text: str, voice_id: str) -> dict:
    key = eleven_key()
    if not key:
        return {}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.post(
                f"{_ELEVEN}/v1/text-to-speech/{voice_id}",
                headers={"xi-api-key": key, "Content-Type": "application/json"},
                params={"output_format": "mp3_44100_128"},
                json={
                    "text": text,
                    "model_id": settings.ELEVENLABS_TTS_MODEL,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.8,
                        "style": 0.0,
                        "use_speaker_boost": True,
                        "speed": 1.0,
                    },
                },
            )
            if res.status_code == 200:
                return {
                    "mime_type": "audio/mpeg",
                    "data": base64.b64encode(res.content).decode(),
                    "provider": "elevenlabs",
                }
    except Exception:
        pass
    return {}


async def _openai_tts(text: str, voice: str) -> dict:
    key = get_api_key("openai")
    if not key:
        return {}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.post(
                f"{_OPENAI_AUDIO}/speech",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": settings.OPENAI_TTS_MODEL, "voice": voice, "input": text},
            )
            if res.status_code == 200:
                return {
                    "mime_type": "audio/mpeg",
                    "data": base64.b64encode(res.content).decode(),
                    "provider": "openai",
                }
    except Exception:
        pass
    return {}


# ──────────────────────────────────────────────
# VOICE CONVERSION (voice changer)
# ──────────────────────────────────────────────


async def convert_voice(audio_bytes: bytes, mime: str, target_voice_id: str, model: str = "") -> dict:
    """Re-speak any spoken clip in the target voice.
    - ElevenLabs target -> speech-to-speech API.
    - Coqui target      -> no direct S2S in XTTS; returns an error with a hint
      so the endpoint can fall back to transcribe-and-resynthesize.
    Returns audio base64 or {"error": ...}."""
    if not target_voice_id:
        return {"error": "No target voice — pass a voice_id to convert into"}
    if is_coqui_voice(target_voice_id):
        return {"error": "coqui_needs_transcribe"}  # endpoint handles fallback
    return await _eleven_convert(audio_bytes, mime, target_voice_id, model)


async def _eleven_convert(audio_bytes: bytes, mime: str, target_voice_id: str, model: str = "") -> dict:
    key = eleven_key()
    if not key:
        return {"error": "ElevenLabs API key not configured — add ELEVENLABS_API_KEY to use the voice changer"}
    if not target_voice_id:
        return {"error": "No target voice — pass a voice_id to convert into"}
    try:
        ext = (mime or "audio/webm").split("/")[-1].split(";")[0] or "webm"
        async with httpx.AsyncClient(timeout=120) as client:
            res = await client.post(
                f"{_ELEVEN}/v1/speech-to-speech/{target_voice_id}",
                headers={"xi-api-key": key},
                params={"model_id": model or settings.ELEVENLABS_S2S_MODEL, "output_format": "mp3_44100_128"},
                files={"audio": (f"clip.{ext}", audio_bytes, mime or "audio/webm")},
            )
            if res.status_code == 200:
                return {
                    "mime_type": "audio/mpeg",
                    "data": base64.b64encode(res.content).decode(),
                    "provider": "elevenlabs",
                }
            return {"error": f"Voice conversion failed ({res.status_code}): {res.text[:200]}"}
    except Exception as e:
        return {"error": f"Voice conversion error: {e}"}


async def list_eleven_voices() -> list[dict]:
    """Stock voices available from ElevenLabs' account (GET /v1/voices)."""
    key = eleven_key()
    if not key:
        return []
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.get(f"{_ELEVEN}/v1/voices", headers={"xi-api-key": key})
            if res.status_code == 200:
                return [
                    {"id": v.get("voice_id", ""), "name": v.get("name", ""), "provider": "elevenlabs", "kind": "stock"}
                    for v in res.json().get("voices", [])
                    if v.get("voice_id")
                ]
    except Exception:
        pass
    return []


async def list_coqui_voices() -> list[dict]:
    """Cloned voices available on the local Coqui sidecar."""
    url = coqui_url()
    if not url:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(f"{url}/voices")
            if res.status_code == 200:
                return [
                    {
                        "id": f"{COQUI_PREFIX}{v.get('voice_id', '')}",
                        "name": f"Local clone {v.get('voice_id', '')[:6]}",
                        "provider": "coqui",
                        "kind": "cloned",
                    }
                    for v in res.json().get("voices", [])
                    if v.get("voice_id")
                ]
    except Exception:
        pass
    return []
