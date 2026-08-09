"""KUDOS Sandbox API — review proposals, browse the web securely, knowledge base."""

import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.sandbox import (
    recommend_proposal,
    seed_sandbox_knowledge,
)
from app.core.secure_web import fetch_url
from app.models import User

router = APIRouter()

BROWSE_RATE_WINDOW = 60.0
BROWSE_RATE_MAX = 5
_browse_history: list[float] = []


class RecommendRequest(BaseModel):
    proposal_id: int


class BrowseRequest(BaseModel):
    url: str = Field(min_length=4, max_length=2000)


@router.post("/recommend")
def recommend_endpoint(
    body: RecommendRequest,
    admin: User = Depends(require_admin),
):
    """KUDOS reviews a tested proposal and issues a recommendation."""
    result = recommend_proposal(body.proposal_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/knowledge")
def sandbox_knowledge_endpoint(db: Session = Depends(get_db),
                               current_user: User = Depends(get_current_user)):
    """KUDOS's knowledge base about how sandboxes and the internet work."""
    try:
        seeded = seed_sandbox_knowledge(db)
    except Exception:
        seeded = 0
    from app.core.memory_store import retrieve_memories

    entries = retrieve_memories(db, user_id=0, layers=["knowledge"], limit=50)
    return {
        "seeded_now": seeded,
        "entries": [{"kind": e.kind, "content": e.content} for e in entries],
    }


@router.post("/browse")
def sandbox_browse_endpoint(
    body: BrowseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    admin: User = Depends(require_admin),
):
    """Fetch a web page through the secure bridge (SSRF-guarded).

    KUDOS uses this to gather external knowledge inside the sandbox before
    recommending a feature to the platform.
    """
    now = time.monotonic()
    while _browse_history and now - _browse_history[0] > BROWSE_RATE_WINDOW:
        _browse_history.pop(0)
    if len(_browse_history) >= BROWSE_RATE_MAX:
        raise HTTPException(
            status_code=429,
            detail="Sandbox browsing rate limit exceeded — retry soon",
        )
    _browse_history.append(now)

    result = fetch_url(body.url)
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail=result["error"])
    return {
        "url": result["url"],
        "status_code": result["status_code"],
        "content": result["content"],
        "bytes": result["bytes"],
        "latency_ms": result["latency_ms"],
    }