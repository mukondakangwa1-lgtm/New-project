"""Personal KUDOS API — per-user style, tone, and interests."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.persona import profile_dict, save_profile
from app.models import User, UserProfile
from app.schemas.schemas import ProfileResponse, ProfileUpdate

router = APIRouter()


@router.get("", response_model=ProfileResponse)
def get_profile_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The user's personal KUDOS settings (defaults until customized)."""
    return ProfileResponse(**profile_dict(db, current_user.id))


@router.put("", response_model=ProfileResponse)
def update_profile_endpoint(
    body: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Customize how KUDOS talks to this user."""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        save_profile(db, current_user.id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ProfileResponse(**profile_dict(db, current_user.id))


@router.delete("", response_model=ProfileResponse)
def reset_profile_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revert to platform defaults."""
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if profile:
        db.delete(profile)
        db.commit()
    return ProfileResponse(**profile_dict(db, current_user.id))