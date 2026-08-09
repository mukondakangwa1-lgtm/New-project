"""Personal KUDOS API — per-user style, tone, interests, and avatar."""

import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.core import storage
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.persona import profile_dict, save_profile
from app.models import User, UserProfile
from app.schemas.schemas import ProfileResponse, ProfileUpdate

router = APIRouter()

AVATAR_PREFIX = "avatars/"
IMAGE_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}
MAX_AVATAR_BYTES = 5 * 1024 * 1024


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
    profile = (
        db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    )
    if profile:
        db.delete(profile)
        db.commit()
    return ProfileResponse(**profile_dict(db, current_user.id))


@router.post("/avatar", response_model=ProfileResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload (or replace) the user's profile picture into object storage."""
    ext = os.path.splitext(file.filename or "")[1].lower().lstrip(".")
    media_type = IMAGE_TYPES.get(ext)
    if not media_type:
        raise HTTPException(
            status_code=400, detail="Avatar must be PNG, JPG, GIF or WebP"
        )
    content = await file.read()
    if len(content) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=400, detail="Avatar too large (max 5MB)")

    key = storage.new_key(
        AVATAR_PREFIX, f"user{current_user.id}_{file.filename or 'avatar.png'}"
    )
    try:
        storage.upload_bytes(key, content, content_type=media_type)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Storage unavailable: {exc}")

    # Garbage-collect the previous avatar, then persist the new key.
    profile = (
        db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    )
    if profile and profile.avatar_url:
        try:
            storage.delete(profile.avatar_url)
        except Exception:
            pass
    save_profile(db, current_user.id, {"avatar_url": key})
    return ProfileResponse(**profile_dict(db, current_user.id))


@router.get("/avatar")
def get_avatar(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Stream the user's avatar (fallback 404 when none is set)."""
    profile = (
        db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    )
    key = profile.avatar_url if profile and profile.avatar_url else ""
    if not key:
        raise HTTPException(status_code=404, detail="No avatar set")
    media_type = _media_type_for(key)
    path = storage.local_path(key)
    if path is not None:
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Avatar missing")
        return Response(path.read_bytes(), media_type=media_type)
    try:
        return StreamingResponse(storage.stream(key), media_type=media_type)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Avatar missing")


def _media_type_for(key: str) -> str:
    ext = key.rsplit(".", 1)[-1].lower() if "." in key else ""
    return IMAGE_TYPES.get(ext, "application/octet-stream")
