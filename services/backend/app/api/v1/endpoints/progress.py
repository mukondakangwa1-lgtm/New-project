"""
Digital Campus - Content Progress Endpoints
Tracks "continue where you left off" for movies, books, audio and documents,
and exposes the user's most-recent activity for the dashboard.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.models_extended import ContentProgress

router = APIRouter()


@router.post("/")
def save_progress(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upsert a user's position in a movie/book/audio item."""
    content_key = str(body.get("content_key") or "").strip()
    if not content_key:
        raise HTTPException(status_code=422, detail="content_key is required")

    entry = (
        db.query(ContentProgress)
        .filter(
            ContentProgress.user_id == current_user.id,
            ContentProgress.content_key == content_key,
        )
        .first()
    )
    if entry is None:
        entry = ContentProgress(
            user_id=current_user.id,
            content_key=content_key,
        )
        db.add(entry)

    entry.kind = str(body.get("kind") or entry.kind or "movie")
    entry.title = str(body.get("title") or entry.title or "")[:300]
    entry.url = str(body.get("url") or entry.url or "")[:600]
    entry.position_pct = min(100.0, max(0.0, float(body.get("position_pct") or entry.position_pct or 0.0)))
    entry.detail = str(body.get("detail") or entry.detail or "")[:600]
    entry.source = str(body.get("source") or entry.source or "library")[:60]

    db.commit()
    db.refresh(entry)
    return {
        "id": entry.id,
        "content_key": entry.content_key,
        "kind": entry.kind,
        "title": entry.title,
        "position_pct": entry.position_pct,
        "detail": entry.detail,
        "updated_at": entry.updated_at,
    }


@router.get("/recent")
def recent_progress(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Most recently touched items, newest first — the dashboard resume strip."""
    rows = (
        db.query(ContentProgress)
        .filter(ContentProgress.user_id == current_user.id)
        .order_by(ContentProgress.updated_at.desc())
        .limit(min(max(limit, 1), 50))
        .all()
    )
    return [
        {
            "id": r.id,
            "content_key": r.content_key,
            "kind": r.kind,
            "title": r.title,
            "url": r.url,
            "position_pct": r.position_pct,
            "detail": r.detail,
            "source": r.source,
            "updated_at": r.updated_at,
        }
        for r in rows
    ]


@router.delete("/{content_key}")
def clear_progress(
    content_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a progress entry (e.g. when a title is finished)."""
    entry = (
        db.query(ContentProgress)
        .filter(
            ContentProgress.user_id == current_user.id,
            ContentProgress.content_key == content_key,
        )
        .first()
    )
    if entry:
        db.delete(entry)
        db.commit()
    return {"status": "cleared"}
