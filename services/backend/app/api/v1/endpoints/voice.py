"""
Digital Campus - KUDOS Voice API

Users can talk to KUDOS with their voice and hear it answer. The superadmin
captures their OWN voice (samples + calibration scripts) which becomes KUDOS's
signature voice, used for every spoken reply across all platforms.

Endpoints:
  GET  /voice/status                 — TTS state + signature voice readiness
  POST /voice/toggle                 — (admin) turn KUDOS speech on/off
  POST /voice/sample                 — (admin) upload a voice sample recording
  GET  /voice/samples                — (admin) list captured samples
  POST /voice/script                 — (admin) generate a calibration script to read
  POST /voice/feed                   — (admin) feed an audio file; first-ever feed becomes the signature voice
  POST /voice/clone                  — (admin) clone the signature voice from samples
  POST /voice/adopt                  — (admin) make any library voice the signature voice
  GET  /voice/voices                 — the KUDOS voice library (signature + cloned + stock)
  POST /voice/convert                — voice changer: re-speak any clip in the target voice
  POST /voice/tts                    — text in -> spoken audio (any authenticated user)
  POST /voice/chat                   — audio in -> transcript + answer + spoken reply
"""

import contextlib
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import storage
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models import KudosDevice, User
from app.models_extended import KudosVoice, VoiceProfile, VoiceSample

router = APIRouter()

VOICE_PREFIX = "audio/voice_samples/"


def _get_profile(db: Session) -> VoiceProfile:
    profile = db.get(VoiceProfile, 1)
    if not profile:
        profile = VoiceProfile(id=1)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def _signature_voice(db: Session, profile: VoiceProfile) -> dict:
    """The designated library voice KUDOS speaks with, if any."""
    if profile.signature_voice_id:
        v = db.get(KudosVoice, profile.signature_voice_id)
        if v:
            return {"id": v.id, "name": v.name, "provider": v.provider, "provider_voice_id": v.provider_voice_id}
    return {}


def _status(profile: VoiceProfile, user: User, db: Session) -> dict:
    sample_count = db.query(VoiceSample).count()
    signature = _signature_voice(db, profile)
    device_name = ""
    if profile.owner_device_id:
        dev = db.get(KudosDevice, profile.owner_device_id)
        device_name = dev.name if dev else ""
    return {
        "tts_enabled": bool(profile.tts_enabled),
        "signature_active": bool(profile.signature_active) and bool(profile.cloned_voice_id),
        "has_cloned_voice": bool(profile.cloned_voice_id),
        "signature_state": profile.signature_state or "none",
        "signature_voice": signature,
        "owner_device_id": profile.owner_device_id,
        "owner_device_name": device_name,
        "default_voice": profile.default_voice or "",
        "sample_count": sample_count,
        "can_manage": bool(user.is_admin),
        "providers": {
            "elevenlabs": bool(__import__("app.core.config", fromlist=["settings"]).settings.ELEVENLABS_API_KEY),
            "openai": bool(__import__("app.core.llm_engine", fromlist=["get_api_key"]).get_api_key("openai")),
        },
    }


@router.get("/voice/status")
def voice_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Current voice state: can KUDOS talk, and is the signature voice ready?"""
    return _status(_get_profile(db), user, db)


# ──────────────────────────────────────────────
# VOICE LIBRARY HELPERS
# ──────────────────────────────────────────────


def _gather_samples(db: Session, profile_id: int) -> list[dict]:
    """Download every captured sample from object storage as {data, mime}."""
    payload = []
    samples = (
        db.query(VoiceSample).filter(VoiceSample.profile_id == profile_id).order_by(VoiceSample.created_at.asc()).all()
    )
    for s in samples:
        try:
            data = storage.download(s.storage_key)
            payload.append({"data": data, "mime": s.mime or "audio/webm"})
        except Exception:
            continue
    return payload


def _total_sample_seconds(db: Session, profile_id: int) -> int:
    samples = db.query(VoiceSample).filter(VoiceSample.profile_id == profile_id).all()
    return sum(s.duration_seconds or 0 for s in samples)


def _register_signature(
    db: Session, profile: VoiceProfile, voice_id: str, name: str, device_id: int | None = None, kind: str = "signature"
) -> KudosVoice:
    """Store a cloned voice in the library and make it KUDOS's signature voice."""
    entry = KudosVoice(
        name=name or "KUDOS",
        kind=kind,
        provider="elevenlabs",
        provider_voice_id=voice_id,
        source_device_id=device_id or profile.owner_device_id,
        is_signature=True,
    )
    db.add(entry)
    db.flush()
    profile.cloned_voice_id = voice_id
    profile.signature_voice_id = entry.id
    profile.signature_active = True
    profile.signature_state = "active"
    if device_id:
        profile.owner_device_id = device_id
    db.commit()
    return entry


async def _auto_clone_if_ready(db: Session, profile: VoiceProfile) -> dict:
    """If a clone key exists and the superadmin has enough clear speech, clone
    the voice from all captured samples and activate it as the signature voice.
    Returns a status dict."""
    from app.core.voice import add_cloned_voice

    if profile.signature_active:
        return {"auto_cloned": False, "reason": "already_active"}
    if not (settings.ELEVENLABS_API_KEY or "").strip():
        return {"auto_cloned": False, "reason": "no_key"}
    total = _total_sample_seconds(db, profile.id)
    if total < settings.KUDOS_SIGNATURE_MIN_SAMPLE_SECONDS:
        return {"auto_cloned": False, "reason": "not_enough_audio", "total_seconds": total}

    payload = _gather_samples(db, profile.id)
    if not payload:
        return {"auto_cloned": False, "reason": "no_samples"}
    result = await add_cloned_voice(payload, name="KUDOS")
    if result.get("error"):
        return {"auto_cloned": False, "reason": "clone_error", "error": result["error"]}
    _register_signature(db, profile, result["voice_id"], "KUDOS")
    return {"auto_cloned": True, "voice_id": result["voice_id"]}


class VoiceToggle(BaseModel):
    enabled: bool = True


@router.post("/voice/toggle")
def voice_toggle(body: VoiceToggle, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Superadmin: turn KUDOS speech on/off (the admin button)."""
    profile = _get_profile(db)
    profile.tts_enabled = bool(body.enabled)
    if not profile.owner_id:
        profile.owner_id = admin.id
    db.commit()
    return _status(profile, admin, db)


async def _store_sample(content: bytes, mime: str, admin: User, db: Session, device_id: int | None = None) -> dict:
    """Persist a voice sample, mark the signature state, and auto-clone when
    the first feed is ready. Returns a status dict (may include preview audio)."""
    from app.core.voice import synthesize, transcribe

    if len(content) < 8 * 1024:
        raise HTTPException(status_code=422, detail="Recording is too small — record at least a few seconds of speech")
    mime = (mime or "audio/webm").split(";")[0].strip()
    ext = mime.split("/")[-1] or "webm"

    key = storage.new_key(VOICE_PREFIX, f"{admin.id}_{uuid.uuid4().hex[:8]}.{ext}")
    storage.upload_bytes(key, content, content_type=mime)

    transcript = ""
    try:
        transcript = await transcribe(content, mime)
    except Exception:
        transcript = ""

    profile = _get_profile(db)
    if not profile.owner_id:
        profile.owner_id = admin.id
    if device_id:
        profile.owner_device_id = device_id
    if not profile.signature_state or profile.signature_state == "none":
        profile.signature_state = "pending"  # first feed — this voice becomes the signature
    db.add(
        VoiceSample(
            profile_id=profile.id,
            storage_key=key,
            mime=mime,
            transcribed=transcript[:400],
            duration_seconds=max(1, len(content) // 32000),
        )
    )
    db.commit()

    # Auto-clone once enough clear speech is captured.
    auto = await _auto_clone_if_ready(db, profile)

    status = _status(profile, admin, db)
    status["auto_cloned"] = auto.get("auto_cloned", False)
    if auto.get("reason"):
        status["auto_clone_reason"] = auto["reason"]
    if auto.get("error"):
        status["auto_clone_error"] = auto["error"]

    # Preview: let the superadmin hear KUDOS in the new signature voice.
    if auto.get("auto_cloned") and profile.tts_enabled:
        try:
            speech = await synthesize(
                "Hello! I am KUDOS. This is my signature voice, and it's yours.", voice_id=profile.cloned_voice_id
            )
            if speech.get("data"):
                status["preview_b64"] = speech["data"]
                status["preview_mime"] = speech.get("mime_type", "audio/mpeg")
        except Exception:
            pass
    return status


@router.post("/voice/sample")
async def upload_voice_sample(
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Superadmin: upload a recording of themselves reading (the KUDOS script
    or anything in their own words) to build the signature voice."""
    content = await file.read()
    mime = file.content_type or "audio/webm"
    return await _store_sample(content, mime, admin, db)


@router.post("/voice/feed")
async def feed_voice(
    file: UploadFile = File(...),
    device_id: int = Form(0),
    name: str = Form(""),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Superadmin: feed an audio recording (typically recorded on a connected
    phone). The FIRST-ever feed becomes KUDOS's signature voice automatically
    once it has enough clear speech — and KUDOS previews itself in that voice."""
    content = await file.read()
    mime = file.content_type or "audio/webm"

    device = None
    if device_id:
        device = db.query(KudosDevice).filter(KudosDevice.id == device_id, KudosDevice.user_id == admin.id).first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

    result = await _store_sample(content, mime, admin, db, device_id=device.id if device else None)
    if result.get("auto_cloned"):
        result["message"] = "🎙️ Signature voice is READY — KUDOS now speaks with your voice across every platform."
    else:
        reason = result.get("auto_clone_reason", "")
        if reason == "no_key":
            result["message"] = (
                "Voice captured and designated as the signature source. Add an ElevenLabs key to activate cloning."
            )
        elif reason == "not_enough_audio":
            result["message"] = (
                f"Voice captured ({result.get('total_seconds', 0)}s). Keep feeding — KUDOS auto-clones once enough clear speech is captured."  # noqa: E501
            )
        else:
            result["message"] = "Voice captured and designated as the signature source."
    return result


@router.get("/voice/samples")
def list_voice_samples(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Superadmin: list captured voice samples with transcripts."""
    samples = db.query(VoiceSample).order_by(VoiceSample.created_at.asc()).all()
    return {
        "samples": [
            {
                "id": s.id,
                "mime": s.mime,
                "transcribed": s.transcribed,
                "duration_seconds": s.duration_seconds,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in samples
        ],
        "count": len(samples),
    }


class ScriptRequest(BaseModel):
    focus: str = ""


@router.post("/voice/script")
async def generate_calibration_script(body: ScriptRequest, admin: User = Depends(require_admin)):
    """Superadmin: KUDOS writes a calibration script to read aloud so it fully
    captures the user's pronunciations and word formulation."""
    from app.core.voice import calibration_script

    script = await calibration_script(body.focus)
    return {"script": script, "note": "Read this aloud clearly, record it, and upload it as a voice sample."}


@router.post("/voice/clone")
async def clone_signature(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Superadmin: clone the signature voice from all captured samples."""
    from app.core.voice import add_cloned_voice

    profile = _get_profile(db)
    samples = db.query(VoiceSample).order_by(VoiceSample.created_at.asc()).all()
    if not samples:
        raise HTTPException(status_code=422, detail="No voice samples yet — record and upload some first")

    payload = _gather_samples(db, profile.id)
    if not payload:
        raise HTTPException(status_code=422, detail="Could not read any voice samples from storage")

    result = await add_cloned_voice(payload, name=f"KUDOS-{admin.full_name or admin.id}")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    _register_signature(db, profile, result["voice_id"], "KUDOS", kind="signature")
    profile.tts_enabled = True
    profile.owner_id = admin.id
    db.commit()
    return {"status": "signature voice ready", **_status(profile, admin, db)}


class AdoptVoiceRequest(BaseModel):
    voice_id: str = Field(..., description="Provider voice id of a library voice to make the signature")
    name: str = ""


@router.post("/voice/adopt")
def adopt_signature(body: AdoptVoiceRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Superadmin: make any voice in the library the signature voice — so KUDOS
    can 'make any other voice' its own."""
    voice_id = (body.voice_id or "").strip()
    if not voice_id:
        raise HTTPException(status_code=422, detail="voice_id is required")

    entry = db.query(KudosVoice).filter(KudosVoice.provider_voice_id == voice_id).first()
    profile = _get_profile(db)
    if entry:
        db.query(KudosVoice).update({KudosVoice.is_signature: False})
        entry.is_signature = True
        profile.cloned_voice_id = entry.provider_voice_id
        profile.signature_voice_id = entry.id
        profile.signature_active = True
        profile.signature_state = "active"
        db.commit()
        return {"status": "signature voice updated", **_status(profile, admin, db)}

    # Stock voice (OpenAI / ElevenLabs premade): no library row yet.
    profile.cloned_voice_id = voice_id
    profile.signature_active = True
    profile.signature_state = "active"
    db.commit()
    return {"status": "signature voice updated", "note": "stock voice", **_status(profile, admin, db)}


@router.get("/voice/voices")
async def list_voices_endpoint(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The KUDOS voice library: signature + cloned voices (owned by KUDOS) plus
    stock voices from the configured providers. Lets KUDOS speak in any voice."""
    from app.core.voice import list_eleven_voices

    library = db.query(KudosVoice).order_by(KudosVoice.created_at.asc()).all()
    voices = [
        {
            "id": v.id,
            "name": v.name,
            "kind": v.kind,
            "provider": v.provider,
            "provider_voice_id": v.provider_voice_id,
            "is_signature": bool(v.is_signature),
            "source_device_id": v.source_device_id,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in library
    ]

    stock = [
        {
            "id": -i,
            "name": name,
            "kind": "stock",
            "provider": "openai",
            "provider_voice_id": name,
            "is_signature": False,
        }
        for i, name in enumerate(__import__("app.core.voice", fromlist=["OPENAI_TTS_VOICES"]).OPENAI_TTS_VOICES)
    ]
    with contextlib.suppress(Exception):
        stock += await list_eleven_voices()

    profile = _get_profile(db)
    return {
        "voices": voices + stock,
        "signature": _signature_voice(db, profile),
        "signature_state": profile.signature_state or "none",
    }


@router.post("/voice/convert")
async def voice_convert(
    file: UploadFile = File(...),
    voice_id: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Voice changer — KUDOS 'makes any other voice': re-speak any spoken clip
    in the target voice (defaults to KUDOS's signature voice)."""
    from app.core.voice import convert_voice

    profile = _get_profile(db)
    target = (voice_id or "").strip() or (profile.cloned_voice_id if profile.signature_active else "")
    content = await file.read()
    if len(content) < 4 * 1024:
        raise HTTPException(status_code=422, detail="Audio is too small — upload a spoken clip")
    mime = (file.content_type or "audio/webm").split(";")[0].strip()

    result = await convert_voice(content, mime, target)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return {
        "audio_b64": result["data"],
        "mime_type": result["mime_type"],
        "provider": result.get("provider", ""),
        "voice_id": target,
    }


class TTSRequest(BaseModel):
    text: str
    voice_id: str = ""


@router.post("/voice/tts")
async def speak_endpoint(body: TTSRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Speak any text (used by the 🔊 button on KUDOS messages). KUDOS uses the
    superadmin's signature voice when it is active, otherwise a fallback voice."""
    from app.core.voice import synthesize

    profile = _get_profile(db)
    if not profile.tts_enabled:
        return {"tts_disabled": True, "message": "KUDOS speech is currently off"}
    result = await synthesize(
        body.text,
        voice_id=profile.cloned_voice_id if profile.signature_active else body.voice_id,
        default_voice=profile.default_voice or "",
    )
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return {"audio_b64": result["data"], "mime_type": result["mime_type"], "provider": result.get("provider", "")}


class VoiceChatRequest(BaseModel):
    conversation_id: int = 0
    text: str = ""


@router.post("/voice/chat")
async def voice_chat(
    file: UploadFile = File(...),
    conversation_id: int = Form(0),
    text: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The full voice loop: user speaks -> KUDOS transcribes, answers, and
    speaks the answer back in its signature voice."""
    from app.core.privacy_guard import scrub_response
    from app.core.quick_answers import get_short_answer, is_short_question
    from app.core.voice import synthesize, transcribe

    content = await file.read()
    mime = (file.content_type or "audio/webm").split(";")[0].strip()

    question = text.strip()
    if not question:
        question = await transcribe(content, mime)
        question = (question or "").strip()
    if not question:
        raise HTTPException(
            status_code=422, detail="Could not understand the audio — please speak clearly or type your question"
        )

    # Reuse the short-answer fast path when appropriate.
    if is_short_question(question):
        answer = await get_short_answer(question, user.full_name.split()[0] if user.full_name else "")
    else:
        answer = await _full_answer(db, user, question)
    answer = scrub_response(answer, allow_emails=True)

    profile = _get_profile(db)
    speech = {"mime_type": "", "audio_b64": ""}
    if profile.tts_enabled:
        try:
            speech = await synthesize(
                answer,
                voice_id=profile.cloned_voice_id if profile.signature_active else "",
                default_voice=profile.default_voice or "",
            )
        except Exception:
            speech = {"mime_type": "", "audio_b64": ""}

    return {
        "transcript": question,
        "answer": answer,
        "audio_b64": speech.get("audio_b64", ""),
        "mime_type": speech.get("mime_type", ""),
        "signature_voice": bool(profile.signature_active),
    }


async def _full_answer(db: Session, user: User, question: str) -> str:
    """Mirror of the main ask pipeline (knowledge + LLM + fallback)."""
    from app.api.v1.endpoints.kudos import search_chunks
    from app.core.llm_engine import get_llm_response
    from app.core.memory_store import build_memory_context
    from app.core.persona import build_persona_instructions, profile_dict
    from app.core.soul import build_soul_context

    sources = []
    with contextlib.suppress(Exception):
        sources = search_chunks(db, question)
    knowledge_context = "\n".join(f"[{i}] {s.get('content', '')[:300]}" for i, s in enumerate(sources[:3], start=1))
    memory_context = ""
    with contextlib.suppress(Exception):
        memory_context = build_memory_context(db, user.id, query=question)
    soul_context = ""
    with contextlib.suppress(Exception):
        soul_context = build_soul_context(db)
    persona_instructions = ""
    with contextlib.suppress(Exception):
        persona_instructions = build_persona_instructions(profile_dict(db, user.id))

    answer = ""
    try:
        answer = await get_llm_response(
            question=question,
            knowledge_context=knowledge_context,
            user_name=user.full_name.split()[0] if user.full_name else "",
            memory_context=memory_context,
            persona_instructions=persona_instructions,
            soul_context=soul_context,
        )
    except Exception:
        answer = ""
    if not answer or len(answer) < 10:
        from app.core.conversation_engine import generate_answer

        answer = generate_answer(question, sources)
    return answer or "I couldn't find a clear answer to that — could you rephrase it?"
