"""
Digital Campus - Speaking, Broadcasting, Radio, Video Calls, Journal
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User

router = APIRouter()

# ──────────────────────────────────────────────
# IN-MEMORY STORES (for POC)
# ──────────────────────────────────────────────

# Active broadcasts
_active_broadcasts: dict[int, dict] = {}  # user_id -> broadcast info
_broadcast_counter = 0

# Active calls
_active_calls: dict[int, dict] = {}  # call_id -> call info
_call_counter = 0

# Speaking practice sessions
_practice_sessions: list[dict] = []


# ──────────────────────────────────────────────
# SPEAKING PRACTICE
# ──────────────────────────────────────────────

SPEAKING_PROMPTS = {
    "beginner": [
        "Introduce yourself in 60 seconds — who are you, what do you study, and what are your goals?",
        "Describe your favorite place in the world and why it matters to you.",
        "Explain what you had for breakfast as if you're a food critic.",
        "Tell us about a book or movie that changed your perspective.",
        "Describe your ideal day from morning to night.",
    ],
    "intermediate": [
        "Argue why your favorite subject should be mandatory for all students.",
        "Pitch a business idea in 2 minutes — what problem does it solve?",
        "Explain a complex topic (quantum computing, AI, climate change) to a 10-year-old.",
        "Give a 2-minute motivational speech to students starting university.",
        "Debate: Is social media more harmful than helpful?",
    ],
    "advanced": [
        "Deliver a 3-minute persuasive speech on why remote work is the future.",
        "Defend an unpopular opinion with logical arguments for 3 minutes.",
        "Give a TED-style talk about a lesson you learned the hard way.",
        "Moderate a mock debate between two opposing viewpoints on education.",
        "Deliver a closing argument as if you're a lawyer in court.",
    ],
    "debate": [
        "AI will replace most jobs within 20 years — agree or disagree?",
        "University education is overrated — agree or disagree?",
        "Social media should be banned for users under 16 — agree or disagree?",
        "Climate change is the most important issue of our time — agree or disagree?",
        "Privacy is more important than security — agree or disagree?",
    ],
}


class PracticeSession(BaseModel):
    prompt: str
    duration_seconds: int = 120
    difficulty: str = "beginner"


class PracticeResult(BaseModel):
    session_id: int
    duration_spoken: int
    self_rating: int  # 1-5
    notes: str = ""


@router.get("/speaking/prompts")
def get_prompts(difficulty: str = "beginner"):
    """Get speaking practice prompts by difficulty."""
    prompts = SPEAKING_PROMPTS.get(difficulty, SPEAKING_PROMPTS["beginner"])
    return {"difficulty": difficulty, "prompts": prompts, "count": len(prompts)}


@router.get("/speaking/random-prompt")
def random_prompt(difficulty: str = "beginner"):
    """Get a random speaking prompt."""
    import random
    prompts = SPEAKING_PROMPTS.get(difficulty, SPEAKING_PROMPTS["beginner"])
    return {"prompt": random.choice(prompts), "difficulty": difficulty}


@router.post("/speaking/session", status_code=201)
def start_practice(body: PracticeSession, user: User = Depends(get_current_user)):
    """Start a speaking practice session."""
    global _practice_sessions
    session = {
        "id": len(_practice_sessions) + 1,
        "user_id": user.id,
        "user_name": user.full_name,
        "prompt": body.prompt,
        "duration_seconds": body.duration_seconds,
        "difficulty": body.difficulty,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    }
    _practice_sessions.append(session)
    return session


@router.post("/speaking/session/{session_id}/complete")
def complete_practice(session_id: int, body: PracticeResult, user: User = Depends(get_current_user)):
    """Complete a speaking practice session with self-assessment."""
    for s in _practice_sessions:
        if s["id"] == session_id and s["user_id"] == user.id:
            s["status"] = "completed"
            s["duration_spoken"] = body.duration_spoken
            s["self_rating"] = body.self_rating
            s["notes"] = body.notes
            s["completed_at"] = datetime.now(timezone.utc).isoformat()
            return s
    raise HTTPException(404, "Session not found")


@router.get("/speaking/history")
def practice_history(user: User = Depends(get_current_user)):
    """Get user's speaking practice history."""
    sessions = [s for s in _practice_sessions if s["user_id"] == user.id]
    total_time = sum(s.get("duration_spoken", 0) for s in sessions)
    avg_rating = sum(s.get("self_rating", 0) for s in sessions if s.get("self_rating")) / max(len(sessions), 1)
    return {
        "sessions": sessions[-20:],
        "total_sessions": len(sessions),
        "total_time_seconds": total_time,
        "average_rating": round(avg_rating, 1),
    }


# ──────────────────────────────────────────────
# LIVE BROADCASTING (Radio-style)
# ──────────────────────────────────────────────

class BroadcastCreate(BaseModel):
    title: str
    description: str = ""
    duration_minutes: int = 30
    is_public: bool = True


@router.post("/broadcast/start", status_code=201)
def start_broadcast(body: BroadcastCreate, user: User = Depends(get_current_user)):
    """Start a live radio-style broadcast."""
    global _broadcast_counter, _active_broadcasts
    if user.id in _active_broadcasts:
        raise HTTPException(400, "You already have an active broadcast")

    _broadcast_counter += 1
    broadcast = {
        "id": _broadcast_counter,
        "host_id": user.id,
        "host_name": user.full_name,
        "title": body.title,
        "description": body.description,
        "duration_minutes": body.duration_minutes,
        "is_public": body.is_public,
        "listeners": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "live",
    }
    _active_broadcasts[user.id] = broadcast
    return broadcast


@router.post("/broadcast/stop")
def stop_broadcast(user: User = Depends(get_current_user)):
    """Stop your active broadcast."""
    if user.id not in _active_broadcasts:
        raise HTTPException(404, "No active broadcast")
    broadcast = _active_broadcasts.pop(user.id)
    broadcast["status"] = "ended"
    broadcast["ended_at"] = datetime.now(timezone.utc).isoformat()
    return broadcast


@router.get("/broadcast/active")
def list_broadcasts():
    """List all active broadcasts."""
    return {
        "broadcasts": list(_active_broadcasts.values()),
        "count": len(_active_broadcasts),
    }


@router.post("/broadcast/{broadcast_id}/join")
def join_broadcast(broadcast_id: int, user: User = Depends(get_current_user)):
    """Join a live broadcast as a listener."""
    for b in _active_broadcasts.values():
        if b["id"] == broadcast_id:
            b["listeners"] += 1
            return {"status": "joined", "broadcast": b}
    raise HTTPException(404, "Broadcast not found or ended")


# ──────────────────────────────────────────────
# LIVE VIDEO CALLS (P2P + Group)
# ──────────────────────────────────────────────

class CallCreate(BaseModel):
    title: str = "Video Call"
    is_group: bool = False
    max_participants: int = 10
    enable_whiteboard: bool = True
    enable_screen_share: bool = True


@router.post("/calls/create", status_code=201)
def create_call(body: CallCreate, user: User = Depends(get_current_user)):
    """Create a video call room."""
    global _call_counter, _active_calls
    _call_counter += 1
    call = {
        "id": _call_counter,
        "host_id": user.id,
        "host_name": user.full_name,
        "title": body.title,
        "is_group": body.is_group,
        "max_participants": body.max_participants,
        "enable_whiteboard": body.enable_whiteboard,
        "enable_screen_share": body.enable_screen_share,
        "participants": [{"user_id": user.id, "name": user.full_name, "role": "host"}],
        "whiteboard_data": [],  # Canvas drawing data
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _active_calls[_call_counter] = call
    return call


@router.get("/calls/active")
def list_calls():
    """List active video calls."""
    return {"calls": list(_active_calls.values()), "count": len(_active_calls)}


@router.post("/calls/{call_id}/join")
def join_call(call_id: int, user: User = Depends(get_current_user)):
    """Join a video call."""
    if call_id not in _active_calls:
        raise HTTPException(404, "Call not found")
    call = _active_calls[call_id]
    if len(call["participants"]) >= call["max_participants"]:
        raise HTTPException(400, "Call is full")
    call["participants"].append({"user_id": user.id, "name": user.full_name, "role": "participant"})
    return {"status": "joined", "call": call}


@router.post("/calls/{call_id}/leave")
def leave_call(call_id: int, user: User = Depends(get_current_user)):
    """Leave a video call."""
    if call_id not in _active_calls:
        raise HTTPException(404, "Call not found")
    call = _active_calls[call_id]
    call["participants"] = [p for p in call["participants"] if p["user_id"] != user.id]
    if not call["participants"]:
        del _active_calls[call_id]
        return {"status": "call ended (no participants)"}
    return {"status": "left", "call": call}


@router.post("/calls/{call_id}/whiteboard/save")
def save_whiteboard(call_id: int, data: dict, user: User = Depends(get_current_user)):
    """Save whiteboard drawing data."""
    if call_id not in _active_calls:
        raise HTTPException(404, "Call not found")
    _active_calls[call_id]["whiteboard_data"] = data.get("strokes", [])
    return {"status": "saved", "strokes": len(data.get("strokes", []))}


@router.get("/calls/{call_id}/whiteboard")
def get_whiteboard(call_id: int):
    """Get whiteboard data for a call."""
    if call_id not in _active_calls:
        raise HTTPException(404, "Call not found")
    return {"strokes": _active_calls[call_id]["whiteboard_data"]}


# ──────────────────────────────────────────────
# JOURNALIST JOURNAL PAGE
# ──────────────────────────────────────────────

class JournalBlock(BaseModel):
    title: str
    block_type: str  # video, photo, webpage, social, youtube, text
    url: str = ""
    content: str = ""
    position: int = 0


# In-memory journal blocks per user
_journal_blocks: dict[int, list[dict]] = {}


@router.get("/journal/my")
def get_journal(user: User = Depends(get_current_user)):
    """Get user's journal page blocks."""
    return {
        "blocks": _journal_blocks.get(user.id, []),
        "user": user.full_name,
        "occupation": "journalist" if user.is_admin else "student",  # POC: admin = journalist
    }


@router.post("/journal/blocks", status_code=201)
def add_journal_block(body: JournalBlock, user: User = Depends(get_current_user)):
    """Add a block to journal page."""
    if user.id not in _journal_blocks:
        _journal_blocks[user.id] = []

    block = {
        "id": len(_journal_blocks[user.id]) + 1,
        "user_id": user.id,
        "title": body.title,
        "block_type": body.block_type,
        "url": body.url,
        "content": body.content,
        "position": body.position or len(_journal_blocks[user.id]),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _journal_blocks[user.id].append(block)
    return block


@router.delete("/journal/blocks/{block_id}", status_code=204)
def delete_journal_block(block_id: int, user: User = Depends(get_current_user)):
    """Delete a journal block."""
    if user.id in _journal_blocks:
        _journal_blocks[user.id] = [b for b in _journal_blocks[user.id] if b["id"] != block_id]


@router.get("/journal/{user_id}")
def view_journal(user_id: int):
    """View another user's public journal page."""
    return {
        "blocks": _journal_blocks.get(user_id, []),
        "user_id": user_id,
    }
