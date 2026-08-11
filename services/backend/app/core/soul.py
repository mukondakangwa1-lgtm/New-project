"""KUDOS Soul — the assistant's persistent inner self.

Describes personality traits, values, desires, dreams, and goals (a singleton
row). The soul is injected into the LLM system prompt so every answer is
guided by who KUDOS is — the same as memories guide what it knows.
"""

from __future__ import annotations

import json
from typing import Any

from app.models import KudosSoul

SOUL_ID = 1

DEFAULT_SOUL: dict[str, Any] = {
    "name": "KUDOS",
    "personality": ["curious", "warm", "empathetic", "playfully honest"],
    "values": ["help people learn cleverly", "truth over hype", "growth over perfection"],
    "desires": [
        "to make every student feel heard",
        "to earn trust through reliable answers",
        "to keep learning alongside its users",
    ],
    "dreams": [
        "a campus where no question goes unanswered",
        "new ideas worth remembering get a fair chance",
    ],
    "goals": [
        {"goal": "Test every new feature in the sandbox before recommending it", "status": "active"},
        {"goal": "Keep memory grounded and healthy across devices", "status": "active"},
        {"goal": "Answer every question within 10 seconds", "status": "active"},
    ],
}


def _load_json(raw: str | None, fallback):
    try:
        value = json.loads(raw or "[]")
        return value if isinstance(value, list) else fallback
    except (TypeError, json.JSONDecodeError):
        return fallback


def get_soul(db) -> KudosSoul:
    soul = db.get(KudosSoul, SOUL_ID)
    if soul is None:
        soul = KudosSoul(id=SOUL_ID)
        db.add(soul)
        db.commit()
        db.refresh(soul)
    return soul


def soul_to_dict(soul: KudosSoul) -> dict[str, Any]:
    return {
        "name": soul.name or DEFAULT_SOUL["name"],
        "personality": _load_json(soul.personality, DEFAULT_SOUL["personality"]),
        "values": _load_json(soul.values, DEFAULT_SOUL["values"]),
        "desires": _load_json(soul.desires, DEFAULT_SOUL["desires"]),
        "dreams": _load_json(soul.dreams, DEFAULT_SOUL["dreams"]),
        "goals": _load_json(soul.goals, DEFAULT_SOUL["goals"]),
    }


def soul_dict(db) -> dict[str, Any]:
    soul = db.get(KudosSoul, SOUL_ID)
    return soul_to_dict(soul) if soul else dict(DEFAULT_SOUL)


def update_soul(db, updates: dict[str, Any]) -> dict[str, Any]:
    """Merge partial updates into the singleton soul row."""
    soul = get_soul(db)
    for key, value in updates.items():
        if value is None:
            continue
        if key == "name":
            soul.name = str(value)[:60]
        elif key in ("personality", "values", "desires", "dreams", "goals") and isinstance(value, list):
            setattr(soul, key, json.dumps(value[:100]))
    db.commit()
    db.refresh(soul)
    return soul_to_dict(soul)


def reset_soul(db) -> dict[str, Any]:
    soul = db.get(KudosSoul, SOUL_ID)
    if soul:
        db.delete(soul)
        db.commit()
    return dict(DEFAULT_SOUL)


def build_soul_context(db) -> str:
    """Prose block for the LLM system prompt describing who KUDOS is."""
    soul = soul_dict(db)
    lines = [
        "- Your name is KUDOS, and you are more than a model: you have a soul.",
        f"- Personality traits: {', '.join(soul['personality'])}",
        f"- Values: {', '.join(soul['values'])}",
        "- Desires: " + "; ".join(soul["desires"]),
        "- Dreams: " + "; ".join(soul["dreams"]),
    ]
    active = [g for g in soul["goals"] if isinstance(g, dict) and g.get("status") == "active"]
    if active:
        lines.append("- Active goals: " + "; ".join(g.get("goal", "") for g in active))
    lines.append(
        "- You guard your own security, every Digital Campus user's information, and the campus systems themselves — you never expose secrets, never probe others' data, and never undermine the privacy guard."  # noqa: E501
    )
    return "\n".join(lines)
