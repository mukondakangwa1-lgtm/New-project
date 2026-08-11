"""
Digital Campus - KUDOS Voice

Lets users talk to KUDOS with their voice and hear KUDOS talk back. The
superadmin can capture their OWN voice (recording + calibration scripts) and
turn it into KUDOS's signature voice, which is then used for every spoken reply
across the platform.

Backends (auto-detected, in preference order):
  - Speech-to-text : OpenAI Whisper, falling back to Google Gemini.
  - Text-to-speech : ElevenLabs (supports voice cloning), falling back to
                     OpenAI TTS voices.
"""

import base64

import httpx

from app.core.config import settings
from app.core.llm_engine import get_api_key

_ELEVEN = "https://api.elevenlabs.io"
_OPENAI_AUDIO = "https://api.openai.com/v1/audio"

# OpenAI TTS stock voices (fallback voices KUDOS can speak with).
OPENAI_TTS_VOICES = ["alloy", "ash", "ballad", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer"]


def _eleven_key() -> str | None:
    return settings.ELEVENLABS_API_KEY or get_api_key("elevenlabs") or None


# ──────────────────────────────────────────────
# SPEECH-TO-TEXT
# ──────────────────────────────────────────────


async def transcribe(audio_bytes: bytes, mime: str = "audio/webm") -> str:
    """Transcribe speech to text (OpenAI Whisper, then Gemini)."""
    text = await _whisper(audio_bytes, mime)
    if text:
        return text
    return await _gemini_stt(audio_bytes, mime)


async def _whisper(audio_bytes: bytes, mime: str) -> str:
    key = get_api_key("openai")
    if not key:
        return ""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.post(
                f"{_OPENAI_AUDIO}/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                data={"model": "whisper-1", "response_format": "json"},
                files={"file": ("speech.webm", audio_bytes, mime or "audio/webm")},
            )
            if res.status_code == 200:
                return (res.json().get("text") or "").strip()
    except Exception:
        pass
    return ""


async def _gemini_stt(audio_bytes: bytes, mime: str) -> str:
    key = get_api_key("google_gemini")
    if not key:
        return ""
    model = getattr(settings, "GEMINI_MODEL", "") or "gemini-2.0-flash"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": key},
                json={
                    "contents": [
                        {
                            "parts": [
                                {"text": "Transcribe the speech in this audio exactly. Return only the transcript."},
                                {
                                    "inline_data": {
                                        "mime_type": mime or "audio/webm",
                                        "data": base64.b64encode(audio_bytes).decode(),
                                    }
                                },
                            ]
                        }
                    ],
                },
            )
            if res.status_code == 200:
                parts = res.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
                return "".join(p.get("text", "") for p in parts).strip()
    except Exception:
        pass
    return ""


# ──────────────────────────────────────────────
# TEXT-TO-SPEECH
# ──────────────────────────────────────────────


async def synthesize(text: str, voice_id: str = "", default_voice: str = "") -> dict:
    """Speak text. Prefers a cloned signature voice via ElevenLabs; falls back
    to OpenAI TTS. Returns {"mime_type", "data"(base64)} or {"error": ...}."""
    text = (text or "").strip()
    if not text:
        return {"error": "Nothing to speak"}

    if _eleven_key() and (voice_id or default_voice):
        out = await _eleven_tts(text, voice_id or default_voice)
        if out:
            return out
    if get_api_key("openai"):
        out = await _openai_tts(text, default_voice or settings.OPENAI_TTS_VOICE)
        if out:
            return out
    return {"error": "No TTS provider configured (ElevenLabs or OpenAI key needed)"}


async def _openai_tts(text: str, voice: str) -> dict:
    key = get_api_key("openai")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.post(
                f"{_OPENAI_AUDIO}/speech",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": settings.OPENAI_TTS_MODEL, "voice": voice, "input": text},
            )
            if res.status_code == 200:
                return {"mime_type": "audio/mpeg", "data": base64.b64encode(res.content).decode(), "provider": "openai"}
    except Exception:
        pass
    return {}


async def _eleven_tts(text: str, voice_id: str) -> dict:
    """Copy of ElevenLabs' text-to-speech API: POST /v1/text-to-speech/{voice_id}
    with full voice_settings (stability, similarity_boost, style, use_speaker_boost,
    speed). Returns audio bytes base64-encoded."""
    key = _eleven_key()
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


async def convert_voice(audio_bytes: bytes, mime: str, target_voice_id: str, model: str = "") -> dict:
    """KUDOS's voice changer — copy of ElevenLabs' speech-to-speech API:
    POST /v1/speech-to-speech/{voice_id} turns any spoken clip into the
    target voice (e.g. KUDOS's signature voice). Returns audio base64."""
    key = _eleven_key()
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
    key = _eleven_key()
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


# ──────────────────────────────────────────────
# SIGNATURE VOICE CLONING
# ──────────────────────────────────────────────

_FALLBACK_SCRIPT = (
    "1. Hello! My name is KUDOS. Welcome to Digital Campus, where every question deserves an answer.\n"
    "2. Today is a beautiful day, and I am excited to learn something new together with you.\n"
    "3. Could you please help me find my classes on the timetable before noon?\n"
    "4. The library opens at eight in the morning and closes at nine at night.\n"
    "5. Artificial intelligence helps students understand big ideas quickly and clearly.\n"
    "6. Physics, chemistry, mathematics and biology are the foundations of science.\n"
    "7. I love reading, writing, speaking and listening in every language I can learn.\n"
    "8. Thirty-three students gathered around the large wooden table in the hall.\n"
    "9. Where is the nearest computer lab, and how can I print my assignment?\n"
    "10. Practice makes progress, so keep asking questions and never stop exploring."
)


async def calibration_script(focus: str = "") -> str:
    """KUDOS writes a calibration script for the superadmin to read aloud so it
    fully captures their pronunciations and word formulation. Falls back to a
    phonetic-coverage script when no LLM is available."""
    focus = (focus or "").strip()
    system = (
        "You are KUDOS. Write a short calibration script for someone to read "
        "aloud so a text-to-speech voice can be trained on their pronunciations "
        "and word formulation. Include: varied vowel and consonant sounds, "
        "numbers, common Digital Campus words (classes, timetable, library, "
        "assignments, exam, wifi, email), questions and statements, and a couple "
        "of sentences in a natural conversational tone. 10 short lines. Plain text."
    )
    user = f"Focus areas: {focus}" if focus else "General calibration script."
    try:
        from app.core.llm_engine import query_best_llm

        result = await query_best_llm(user, system)
        script = (result.get("response") or "").strip()
        if len(script) > 120:
            return script
    except Exception:
        pass
    return _FALLBACK_SCRIPT


async def add_cloned_voice(samples: list[dict], name: str = "KUDOS") -> dict:
    """Clone a voice from recordings — copy of ElevenLabs' IVC voice creation:
    POST /v1/voices/add (multipart files + name + remove_background_noise).
    Returns {"voice_id", "name"} or {"error": ...}."""
    key = _eleven_key()
    if not key:
        return {"error": "ElevenLabs API key not configured — add ELEVENLABS_API_KEY to enable voice cloning"}
    if not samples:
        return {"error": "No voice samples recorded yet"}

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
                    return {"voice_id": voice_id, "name": name}
                return {"error": "ElevenLabs did not return a voice id"}
            return {"error": f"ElevenLabs clone failed ({res.status_code}): {res.text[:200]}"}
    except Exception as e:
        return {"error": f"ElevenLabs clone error: {e}"}


async def clone_signature_voice(samples: list[dict], name: str = "KUDOS") -> dict:
    """Clone the superadmin's voice from recordings (bytes + mime). Requires
    ~1-3 minutes of clear speech total for a good clone. This is the original
    signature-voice entry point; it delegates to add_cloned_voice."""
    return await add_cloned_voice(samples, name=name)
