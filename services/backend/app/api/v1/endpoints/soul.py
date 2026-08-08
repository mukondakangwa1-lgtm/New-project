"""KUDOS Soul API — read the soul, shape it as superadmin."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.soul import build_soul_context, reset_soul, soul_dict, update_soul
from app.models import User
from app.schemas.schemas import SoulResponse, SoulUpdate

router = APIRouter()


@router.get("", response_model=SoulResponse)
def get_soul_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """KUDOS's current soul: personality, desires, dreams, goals, values."""
    return SoulResponse(**soul_dict(db))


@router.get("/voice", response_model=str)
def get_soul_voice_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The soul as KUDOS hears it — the prompt block guiding every answer."""
    return build_soul_context(db)


@router.put("", response_model=SoulResponse)
def update_soul_endpoint(
    body: SoulUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Shape KUDOS's soul (superadmin): desires, dreams, goals, personality."""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return SoulResponse(**update_soul(db, updates))


@router.delete("", response_model=SoulResponse)
def reset_soul_endpoint(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Return KUDOS's soul to its default self."""
    return SoulResponse(**reset_soul(db))