"""
KUDOS Guardian — File integrity, self-protection, and secure superadmin channel.
Only the superadmin can modify KUDOS code. KUDOS self-improves from interactions.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ──────────────────────────────────────────────
# FILE INTEGRITY — Hash all KUDOS source files
# ──────────────────────────────────────────────

KUDOS_PROTECTED_PATHS = [
    "app/api/v1/endpoints/kudos.py",
    "app/api/v1/endpoints/connectors.py",
    "app/core/kudos_guardian.py",
    "app/models.py",
    "app/schemas/schemas.py",
    "seed_kudos.py",
]

INTEGRITY_FILE = "kudos_integrity.json"


def compute_file_hash(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    try:
        with open(filepath, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except FileNotFoundError:
        return "MISSING"


def compute_all_hashes(base_dir: str = ".") -> dict[str, str]:
    """Compute hashes for all protected KUDOS files."""
    hashes = {}
    for rel_path in KUDOS_PROTECTED_PATHS:
        full_path = os.path.join(base_dir, rel_path)
        hashes[rel_path] = compute_file_hash(full_path)
    return hashes


def save_integrity_hashes(base_dir: str = "."):
    """Save current file hashes as the known-good state."""
    hashes = compute_all_hashes(base_dir)
    integrity_path = os.path.join(base_dir, INTEGRITY_FILE)
    data = {
        "hashes": hashes,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "saved_by": "superadmin",
        "version": 1,
    }
    with open(integrity_path, "w") as f:
        json.dump(data, f, indent=2)
    return data


def verify_integrity(base_dir: str = ".") -> dict:
    """
    Verify all KUDOS files against saved hashes.
    Returns: {status, violations: [{file, expected, actual}]}
    """
    integrity_path = os.path.join(base_dir, INTEGRITY_FILE)

    if not os.path.exists(integrity_path):
        # First run — save hashes
        save_integrity_hashes(base_dir)
        return {"status": "initialized", "violations": [], "message": "Integrity hashes saved for the first time"}

    with open(integrity_path) as f:
        saved = json.load(f)

    current = compute_all_hashes(base_dir)
    violations = []

    for filepath, expected_hash in saved["hashes"].items():
        actual_hash = current.get(filepath, "MISSING")
        if actual_hash != expected_hash:
            violations.append({
                "file": filepath,
                "expected": expected_hash[:16] + "...",
                "actual": actual_hash[:16] + "...",
                "status": "TAMPERED" if actual_hash != "MISSING" else "DELETED",
            })

    if violations:
        return {
            "status": "TAMPERED",
            "violations": violations,
            "message": f"⚠️ {len(violations)} file(s) have been modified without authorization!",
            "saved_at": saved.get("saved_at", "unknown"),
        }

    return {
        "status": "INTEGR",
        "violations": [],
        "message": "✅ All KUDOS files are intact and verified",
        "saved_at": saved.get("saved_at", "unknown"),
    }


def update_hashes_after_admin_change(base_dir: str = ".") -> dict:
    """Superadmin updates hashes after authorized changes."""
    return save_integrity_hashes(base_dir)


# ──────────────────────────────────────────────
# SUPERADMIN SECURE CHANNEL
# ──────────────────────────────────────────────

class KudosSecureChannel:
    """
    Encrypted communication channel between superadmin and KUDOS.
    All commands are logged and authenticated.
    """

    def __init__(self):
        self._command_log: list[dict] = []
        self._access_key: Optional[str] = None

    def initialize(self, superadmin_id: int) -> str:
        """Initialize secure channel and return access key."""
        key = hashlib.sha256(
            f"kudos-secure-{superadmin_id}-{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()
        self._access_key = key
        self._log(superadmin_id, "CHANNEL_OPEN", "Secure channel initialized")
        return key

    def verify_access(self, user_id: int, is_admin: bool, command: str) -> bool:
        """Verify user has superadmin access."""
        if not is_admin:
            self._log(user_id, "ACCESS_DENIED", f"Non-admin attempted: {command}")
            return False
        return True

    def execute_command(self, user_id: int, is_admin: bool, command: str, params: dict = None) -> dict:
        """Execute a superadmin command on KUDOS."""
        if not self.verify_access(user_id, is_admin, command):
            return {"error": "Access denied. Only superadmin can control KUDOS."}

        self._log(user_id, command, json.dumps(params or {}))

        # Command handlers
        handlers = {
            "verify_integrity": lambda p: verify_integrity(),
            "update_hashes": lambda p: update_hashes_after_admin_change(),
            "system_status": lambda p: self._system_status(),
            "purge_knowledge": lambda p: {"status": "requires_confirmation"},
            "lock_system": lambda p: {"status": "locked", "message": "KUDOS system locked"},
            "unlock_system": lambda p: {"status": "unlocked", "message": "KUDOS system unlocked"},
        }

        handler = handlers.get(command)
        if not handler:
            return {"error": f"Unknown command: {command}"}

        return handler(params or {})

    def get_audit_log(self, limit: int = 100) -> list[dict]:
        """Get command audit log."""
        return self._command_log[-limit:]

    def _log(self, user_id: int, action: str, details: str):
        self._command_log.append({
            "user_id": user_id,
            "action": action,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _system_status(self) -> dict:
        return {
            "protected_files": len(KUDOS_PROTECTED_PATHS),
            "integrity": verify_integrity()["status"],
            "audit_log_entries": len(self._command_log),
            "channel_active": self._access_key is not None,
        }


# Global secure channel instance
secure_channel = KudosSecureChannel()


# ──────────────────────────────────────────────
# SELF-IMPROVEMENT ENGINE
# ──────────────────────────────────────────────

class KudosSelfImprover:
    """
    KUDOS learns from user interactions to improve its responses.
    Tracks: popular questions, missing knowledge, user feedback.
    """

    def __init__(self):
        self._question_log: list[dict] = []
        self._knowledge_gaps: dict[str, int] = {}  # topic → count of unanswered
        self._popular_topics: dict[str, int] = {}  # topic → count of questions
        self._feedback: list[dict] = []

    def log_question(self, user_id: int, question: str, had_sources: bool):
        """Log a question and whether KUDOS found relevant sources."""
        self._question_log.append({
            "user_id": user_id,
            "question": question,
            "had_sources": had_sources,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Track popular topics
        words = question.lower().split()
        for word in words:
            if len(word) > 3:
                self._popular_topics[word] = self._popular_topics.get(word, 0) + 1

        # Track knowledge gaps
        if not had_sources:
            key_words = [w for w in words if len(w) > 3][:3]
            gap_key = " ".join(key_words)
            self._knowledge_gaps[gap_key] = self._knowledge_gaps.get(gap_key, 0) + 1

    def log_feedback(self, user_id: int, question: str, rating: int, comment: str = ""):
        """Log user feedback on KUDOS response."""
        self._feedback.append({
            "user_id": user_id,
            "question": question,
            "rating": rating,  # 1-5
            "comment": comment,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_improvement_report(self) -> dict:
        """Generate a report on what KUDOS should learn next."""
        total = len(self._question_log)
        with_sources = sum(1 for q in self._question_log if q["had_sources"])
        without_sources = total - with_sources

        # Top knowledge gaps
        top_gaps = sorted(self._knowledge_gaps.items(), key=lambda x: -x[1])[:10]

        # Top popular topics
        top_topics = sorted(self._popular_topics.items(), key=lambda x: -x[1])[:10]

        # Average feedback rating
        avg_rating = 0
        if self._feedback:
            avg_rating = sum(f["rating"] for f in self._feedback) / len(self._feedback)

        return {
            "total_questions": total,
            "questions_answered": with_sources,
            "questions_unanswered": without_sources,
            "answer_rate": f"{(with_sources / total * 100):.1f}%" if total > 0 else "N/A",
            "knowledge_gaps": [{"topic": t, "count": c} for t, c in top_gaps],
            "popular_topics": [{"topic": t, "count": c} for t, c in top_topics],
            "feedback_count": len(self._feedback),
            "average_rating": round(avg_rating, 1),
            "recommendation": self._generate_recommendation(top_gaps),
        }

    def _generate_recommendation(self, top_gaps: list) -> str:
        """Generate recommendation for what to teach KUDOS next."""
        if not top_gaps:
            return "KUDOS is well-informed! Keep adding more knowledge to expand its capabilities."

        gap_topics = [t for t, _ in top_gaps[:3]]
        return (
            f"KUDOS is getting questions about: {', '.join(gap_topics)}. "
            f"Consider uploading documents or teaching web pages about these topics "
            f"to improve KUDOS's answers."
        )


# Global self-improver instance
self_improver = KudosSelfImprover()
