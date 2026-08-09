"""Personal KUDOS: per-user tone, verbosity, and interests.

Defaults are applied lazily in memory — a user with no saved profile gets
the platform defaults without creating a row; writing preferences persists
it and keeps KUDOS's memory in sync (system-layer preference memories).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from app.models import UserProfile

TONE_STYLES = ("concise", "friendly", "detailed", "formal")
VERBOSITY_LEVELS = ("brief", "normal", "detailed")

DEFAULT_PROFILE: Dict[str, Any] = {
    "tone": "friendly",
    "verbosity": "normal",
    "emoji_enabled": False,
    "interests": [],
    "greeting": "",
}


def default_profile() -> Dict[str, Any]:
    return dict(DEFAULT_PROFILE)


def get_profile(db, user_id: int) -> UserProfile:
    """Profile row or None; callers use profile_dict() for defaults."""
    return db.query(UserProfile).filter(UserProfile.user_id == user_id).first()


def profile_dict(db, user_id: int) -> Dict[str, Any]:
    """Merged effective profile — defaults overlaid with saved values."""
    profile = get_profile(db, user_id)
    merged = default_profile()
    if profile is None:
        return merged
    merged.update(profile_to_dict(profile))
    return merged


def profile_to_dict(profile: UserProfile) -> Dict[str, Any]:
    interests = []
    try:
        interests = json.loads(profile.interests or "[]")
    except (TypeError, json.JSONDecodeError):
        interests = []
    return {
        "tone": profile.tone or DEFAULT_PROFILE["tone"],
        "verbosity": profile.verbosity or DEFAULT_PROFILE["verbosity"],
        "emoji_enabled": bool(profile.emoji_enabled),
        "interests": interests,
        "greeting": profile.greeting or "",
        "avatar_url": profile.avatar_url or "",
    }


def save_profile(db, user_id: int, updates: Dict[str, Any]) -> UserProfile:
    """Create or update the user's profile. Unknown keys are ignored."""
    profile = get_profile(db, user_id)
    if profile is None:
        profile = UserProfile(user_id=user_id)
        db.add(profile)

    if "tone" in updates:
        tone = updates["tone"]
        if tone not in TONE_STYLES:
            raise ValueError(f"Invalid tone: {tone}")
        profile.tone = tone
    if "verbosity" in updates:
        verbosity = updates["verbosity"]
        if verbosity not in VERBOSITY_LEVELS:
            raise ValueError(f"Invalid verbosity: {verbosity}")
        profile.verbosity = verbosity
    if "emoji_enabled" in updates:
        profile.emoji_enabled = bool(updates["emoji_enabled"])
    if "interests" in updates:
        interests = updates["interests"]
        if not isinstance(interests, list) or len(interests) > 50:
            raise ValueError("interests must be a list of at most 50 tags")
        tags = [str(i)[:60] for i in interests]
        profile.interests = json.dumps(tags)
    if "greeting" in updates:
        greeting = str(updates["greeting"] or "")[:120]
        profile.greeting = greeting
    if "avatar_url" in updates:
        profile.avatar_url = str(updates["avatar_url"] or "")[:255]

    db.commit()
    db.refresh(profile)
    return profile


def build_persona_instructions(profile: Dict[str, Any]) -> str:
    """System-prompt-ready instructions from an effective profile."""
    sections: List[str] = []

    tone = profile.get("tone", "friendly")
    tone_lines = {
        "concise": "Be brief and direct; skip pleasantries, lead with the answer.",
        "friendly": "Be warm and approachable, like a knowledgeable friend.",
        "detailed": "Give thorough, structured explanations with examples.",
        "formal": "Be professional, precise, and courteous.",
    }
    sections.append(f"TONE: {tone_lines.get(tone, tone_lines['friendly'])}")

    verbosity = profile.get("verbosity", "normal")
    verbosity_lines = {
        "brief": "Keep answers short — a few lines at most.",
        "normal": "Keep answers moderately sized (1-3 short paragraphs).",
        "detailed": "Feel free to go deep, with structure and detail.",
    }
    sections.append(f"VERBOSITY: {verbosity_lines.get(verbosity, verbosity_lines['normal'])}")

    if profile.get("emoji_enabled"):
        sections.append("EMOJI: Use light emoji where natural.")
    else:
        sections.append("EMOJI: Do not use emoji.")

    interests = profile.get("interests") or []
    if interests:
        joined = ", ".join(str(i) for i in interests[:10])
        sections.append(f"INTERESTS: {joined} — surface these topics when relevant.")

    greeting = profile.get("greeting") or ""
    if greeting:
        sections.append(f"GREETING: Prefer opening with “{greeting}” when greeting the user.")

    return "\n".join(f"- {s}" for s in sections)