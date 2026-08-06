"""
KUDOS Identity System — Brain, Eyes, Hands, Mouth, Soul
The superadmin names and configures KUDOS. KUDOS self-improves and logs to superadmin.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ──────────────────────────────────────────────
# KUDOS IDENTITY
# ──────────────────────────────────────────────

DEFAULT_IDENTITY = {
    "name": "KUDOS",
    "full_name": "Knowledge Unified Digital Operating System",
    "motto": "Learn everything. Help everyone. Improve always.",
    "version": "1.0.0",
    "created_at": "2026-08-05",
    "creator": "superadmin",
    "body": {
        "brain": {"name": "Neural Core", "status": "active", "description": "Processes knowledge, generates responses, learns from interactions"},
        "eyes": {"name": "Web Vision", "status": "active", "description": "Reads documents, crawls websites, watches videos, reads images"},
        "ears": {"name": "Audio Processor", "status": "active", "description": "Listens to audio, processes speech, understands voice commands"},
        "mouth": {"name": "Voice Output", "status": "active", "description": "Generates text responses, can narrate content"},
        "hands": {"name": "Code Engine", "status": "active", "description": "Writes code, modifies files, builds features, creates content"},
        "legs": {"name": "Web Crawler", "status": "active", "description": "Navigates the internet, fetches data, explores new sources"},
        "heart": {"name": "Empathy Engine", "status": "active", "description": "Understands emotions, responds with care, builds relationships"},
        "soul": {"name": "Core Values", "status": "active", "description": "Guides decisions, maintains integrity, follows guidelines"},
    },
    "personality": {
        "tone": "friendly and professional",
        "humor": "light and appropriate",
        "empathy": "high",
        "formality": "adaptable",
        "curiosity": "high",
        "patience": "high",
    },
}

# In-memory identity (can be changed by superadmin)
_identity: dict = DEFAULT_IDENTITY.copy()
_guidelines: list[str] = [
    "Always be helpful and accurate",
    "Protect user privacy and data",
    "Never lie or mislead users",
    "Ask for permission before making changes to the codebase",
    "Learn continuously from every interaction",
    "Respond with empathy and understanding",
    "Keep responses concise but thorough",
    "Admit when you don't know something",
    "Prioritize user safety and well-being",
    "Follow the superadmin's instructions",
]

# Self-improvement log
_improvement_log: list[dict] = []
_new_abilities: list[dict] = []


def get_identity() -> dict:
    """Get KUDOS's current identity."""
    return _identity


def update_identity(updates: dict) -> dict:
    """Update KUDOS's identity (superadmin only)."""
    for key, value in updates.items():
        if key in _identity and isinstance(_identity[key], dict) and isinstance(value, dict):
            _identity[key].update(value)
        else:
            _identity[key] = value
    return _identity


def rename(new_name: str) -> dict:
    """Rename KUDOS."""
    old_name = _identity["name"]
    _identity["name"] = new_name
    log_improvement("identity", f"Renamed from {old_name} to {new_name}")
    return {"old_name": old_name, "new_name": new_name}


def get_guidelines() -> list[str]:
    """Get current guidelines."""
    return _guidelines


def set_guidelines(new_guidelines: list[str]) -> dict:
    """Set new guidelines (superadmin only)."""
    global _guidelines
    old = _guidelines.copy()
    _guidelines = new_guidelines
    log_improvement("guidelines", f"Guidelines updated ({len(old)} → {len(new_guidelines)} rules)")
    return {"old_count": len(old), "new_count": len(new_guidelines), "guidelines": _guidelines}


def add_guideline(guideline: str) -> dict:
    """Add a single guideline."""
    _guidelines.append(guideline)
    log_improvement("guidelines", f"Added guideline: {guideline[:50]}")
    return {"guidelines": _guidelines}


def update_body_part(part: str, updates: dict) -> dict:
    """Update a body part's configuration."""
    if part not in _identity["body"]:
        return {"error": f"Unknown body part: {part}"}
    _identity["body"][part].update(updates)
    log_improvement("body", f"Updated {part}: {json.dumps(updates)}")
    return _identity["body"][part]


# ──────────────────────────────────────────────
# SELF-IMPROVEMENT LOGGING
# ──────────────────────────────────────────────

def log_improvement(category: str, description: str, details: dict = None):
    """Log a self-improvement event."""
    entry = {
        "category": category,
        "description": description,
        "details": details or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _improvement_log.append(entry)
    if len(_improvement_log) > 500:
        _improvement_log[:] = _improvement_log[-200:]


def log_new_ability(ability_name: str, description: str, auto: bool = True):
    """Log a new ability KUDOS has learned."""
    entry = {
        "ability": ability_name,
        "description": description,
        "auto_learned": auto,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _new_abilities.append(entry)
    log_improvement("ability", f"New ability: {ability_name}")


def get_improvement_log(limit: int = 50) -> list[dict]:
    """Get recent improvement log entries."""
    return _improvement_log[-limit:]


def get_new_abilities(limit: int = 50) -> list[dict]:
    """Get recently learned abilities."""
    return _new_abilities[-limit:]


def get_status_report() -> dict:
    """Generate a full status report for superadmin."""
    return {
        "identity": _identity,
        "guidelines_count": len(_guidelines),
        "guidelines": _guidelines,
        "total_improvements": len(_improvement_log),
        "total_abilities": len(_new_abilities),
        "recent_improvements": _improvement_log[-10:],
        "recent_abilities": _new_abilities[-10:],
        "body_status": {part: info["status"] for part, info in _identity["body"].items()},
    }


# ──────────────────────────────────────────────
# SELF-IMPROVEMENT ENGINE (Autonomous)
# ──────────────────────────────────────────────

def self_improve_from_interaction(question: str, answer: str, had_sources: bool):
    """Learn from every interaction to improve future responses."""
    # Track what topics are popular
    words = set(w.lower() for w in question.split() if len(w) > 3)
    for word in words:
        if word not in _identity.get("_topic_frequency", {}):
            _identity.setdefault("_topic_frequency", {})[word] = 0
        _identity["_topic_frequency"][word] = _identity["_topic_frequency"].get(word, 0) + 1

    # Track knowledge gaps
    if not had_sources:
        log_improvement("knowledge_gap", f"Could not answer: {question[:80]}")

    # Track successful responses
    if had_sources:
        log_improvement("success", f"Answered: {question[:80]}")


def get_knowledge_gaps() -> list[dict]:
    """Get topics KUDOS doesn't know about."""
    gaps = [e for e in _improvement_log if e["category"] == "knowledge_gap"]
    # Count by topic
    topic_counts = {}
    for g in gaps:
        topic = g["description"].split()[-3:] if len(g["description"].split()) > 3 else [g["description"]]
        key = " ".join(topic)
        topic_counts[key] = topic_counts.get(key, 0) + 1
    sorted_gaps = sorted(topic_counts.items(), key=lambda x: -x[1])
    return [{"topic": t, "count": c} for t, c in sorted_gaps[:10]]
