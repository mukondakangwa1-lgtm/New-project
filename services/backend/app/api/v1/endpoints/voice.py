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
  POST /voice/clone                  — (admin) clone the signature voice from samples
  POST /voice/chat                   — audio in -> transcript + answer + spoken reply
  POST /voice/tts                    — text in -> spoken audio (any authenticated user)
"""
import base64
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import storage
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models import User
from app.models_extended import VoiceProfile, VoiceSample

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


def _status(profile: VoiceProfile, user: User, db: Session) -> dict:
    sample_count = db.query(VoiceSample).count()
    return {
        "tts_enabled": bool(profile.tts_enabled),
        "signature_active": bool(profile.signature_active) and bool(profile.cloned_voice_id),
        "has_cloned_voice": bool(profile.cloned_voice_id),
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


@router.post("/voice/sample")
async def upload_voice_sample(
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Superadmin: upload a recording of themselves reading (the KUDOS script
    or anything in their own words) to build the signature voice."""
    from app.core.voice import transcribe

    content = await file.read()
    if len(content) < 8 * 1024:
        raise HTTPException(status_code=422, detail="Recording is too small — record at least a few seconds of speech")
    mime = (file.content_type or "audio/webm").split(";")[0].strip()
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
    db.add(VoiceSample(profile_id=profile.id, storage_key=key, mime=mime,
                       transcribed=transcript[:400], duration_seconds=max(1, len(content) // 32000)))
    db.commit()
    return _status(profile, admin, db)


@router.get("/voice/samples")
def list_voice_samples(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Superadmin: list captured voice samples with transcripts."""
    samples = db.query(VoiceSample).order_by(VoiceSample.created_at.asc()).all()
    return {
        "samples": [
            {
                "id": s.id, "mime": s.mime, "transcribed": s.transcribed,
                "duration_seconds": s.duration_seconds, "created_at": s.created_at.isoformat() if s.created_at else None,
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
    from app.core.voice import clone_signature_voice

    profile = _get_profile(db)
    samples = db.query(VoiceSample).order_by(VoiceSample.created_at.asc()).all()
    if not samples:
        raise HTTPException(status_code=422, detail="No voice samples yet — record and upload some first")

    payload = []
    for s in samples:
        try:
            data = storage.download(s.storage_key)
            payload.append({"data": data, "mime": s.mime or "audio/webm"})
        except Exception:
            continue
    if not payload:
        raise HTTPException(status_code=422, detail="Could not read any voice samples from storage")

    result = await clone_signature_voice(payload, name=f"KUDOS-{admin.full_name or admin.id}")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    profile.cloned_voice_id = result["voice_id"]
    profile.signature_active = True
    profile.tts_enabled = True
    profile.owner_id = admin.id
    db.commit()
    return {"status": "signature voice ready", **_status(profile, admin, db)}


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
    result = await synthesize(body.text, voice_id=profile.cloned_voice_id if profile.signature_active else body.voice_id,
                              default_voice=profile.default_voice or "")
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
    from app.core.quick_answers import is_short_question, get_short_answer
    from app.core.voice import synthesize, transcribe

    content = await file.read()
    mime = (file.content_type or "audio/webm").split(";")[0].strip()

    question = text.strip()
    if not question:
        question = await transcribe(content, mime)
        question = (question or "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="Could not understand the audio — please speak clearly or type your question")

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
            speech = await synthesize(answer,
                                      voice_id=profile.cloned_voice_id if profile.signature_active else "",
                                      default_voice=profile.default_voice or "")
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
    from app.core.soul import build_soul_context
    from app.core.persona import build_persona_instructions, profile_dict
    from app.core.memory_store import build_memory_context

    sources = []
    try:
        sources = search_chunks(db, question)
    except Exception:
        pass
    knowledge_context = "\n".join(
        f"[{i}] {s.get('content', '')[:300]}" for i, s in enumerate(sources[:3], start=1)
    )
    memory_context = ""
    try:
        memory_context = build_memory_context(db, user.id, query=question)
    except Exception:
        pass
    soul_context = ""
    try:
        soul_context = build_soul_context(db)
    except Exception:
        pass
    persona_instructions = ""
    try:
        persona_instructions = build_persona_instructions(profile_dict(db, user.id))
    except Exception:
        pass

    answer = ""
    try:
        answer = await get_llm_response(
            question=question, knowledge_context=knowledge_context,
            user_name=user.full_name.split()[0] if user.full_name else "",
            memory_context=memory_context, persona_instructions=persona_instructions,
            soul_context=soul_context,
        )
    except Exception:
        answer = ""
    if not answer or len(answer) < 10:
        from app.core.conversation_engine import generate_answer
        answer = generate_answer(question, sources)
    return answer or "I couldn't find a clear answer to that — could you rephrase it?"
