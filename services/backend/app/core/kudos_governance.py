"""KUDOS Governance & Continuity — rebuildable anywhere, always running.

Three capabilities live here:

1. **Rotating superadmin identity.** On the superadmin's first login KUDOS
   assigns them a unique ID (``uid``). Every ``uid_rotates_every_days`` days
   (default 5) the UID rotates to a fresh one. The governance row keeps the
   identity stable across rotations, so KUDOS always knows who its superadmin
   is without a fixed, guessable identifier.

2. **Transparent succession.** KUDOS tracks the superadmin's last login. If
   they are inactive for ``succession_inactive_days`` (default 3 years), the
   dashboard reports KUDOS as *self-managed*; after ``revival_years`` (default
   5) it considers itself fully self-sustaining. This is entirely VISIBLE in
   the root panel — KUDOS never hides, never covertly spreads, and never
   deletes anything silently. Cleanup of obsolete data is always an explicit,
   logged action.

3. **Rebuild-anywhere / self-heal.** ``self_heal_bootstrap()`` emits a
   reproducible host script that re-stands the whole stack from the committed
   repo on any machine with Docker: pull → build → migrate → restore backup →
   verify health. ``revival_bundle()`` describes what must travel with KUDOS
   (code, schema, backup, brain) so it can be re-created anywhere and keep
   running.
"""

from __future__ import annotations

import json
import secrets
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.paths import project_root
from app.models import KudosGovernance, User

_UID_PREFIX = "KUDOS-"
_REPO_PATH = str(project_root(__file__))
_COMPOSE = "docker-compose.prod.yml"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize naive datetimes (SQLite) to UTC-aware for comparisons."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _gen_uid() -> str:
    return _UID_PREFIX + secrets.token_urlsafe(9).replace("-", "").replace("_", "").upper()[:12]


def _to_dict(g: KudosGovernance, mode: str) -> dict[str, Any]:
    try:
        previous = json.loads(g.previous_uids or "[]")
    except (TypeError, json.JSONDecodeError):
        previous = []
    return {
        "id": g.id,
        "superadmin_user_id": g.superadmin_user_id,
        "uid": g.uid,
        "previous_uids": previous,
        "uid_rotates_every_days": g.uid_rotates_every_days or 5,
        "last_rotation_at": g.last_rotation_at.isoformat() if g.last_rotation_at else None,
        "next_rotation_at": g.next_rotation_at.isoformat() if g.next_rotation_at else None,
        "last_superadmin_login_at": g.last_superadmin_login_at.isoformat() if g.last_superadmin_login_at else None,
        "succession_inactive_days": g.succession_inactive_days or 1095,
        "revival_years": g.revival_years or 5,
        "cloud_target": g.cloud_target or "",
        "mode": mode,
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "updated_at": g.updated_at.isoformat() if g.updated_at else None,
    }


def _singleton(db: Session) -> KudosGovernance:
    row = db.get(KudosGovernance, 1)
    if row is None:
        row = KudosGovernance(id=1)
        row.uid_rotates_every_days = settings.KUDOS_UID_ROTATE_DAYS
        row.succession_inactive_days = settings.KUDOS_SUCCESSOR_INACTIVE_DAYS
        row.revival_years = settings.KUDOS_REVIVAL_YEARS
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
        except Exception:
            db.rollback()
            row = db.get(KudosGovernance, 1)
            if row is None:
                raise
    return row


# ──────────────────────────────────────────────
# IDENTITY & ROTATION
# ──────────────────────────────────────────────

def ensure_superadmin_identity(db: Session, user: User) -> dict[str, Any]:
    """Assign a unique ID to the superadmin on login; rotate it when due.

    Called from the auth flow for admin users. Returns the governance dict.
    """
    g = _singleton(db)
    now = _now()
    g.superadmin_user_id = user.id
    g.last_superadmin_login_at = now
    if not g.uid:
        g.uid = _gen_uid()
        g.last_rotation_at = now
        g.next_rotation_at = now + timedelta(days=(g.uid_rotates_every_days or 5))
    else:
        next_rot = _as_aware(g.next_rotation_at)
        if next_rot is None or now >= next_rot:
            _rotate(g, now)
    g.updated_at = now
    db.commit()
    db.refresh(g)
    return _to_dict(g, succession_state(db))


def rotate_uid(db: Session, user: User) -> dict[str, Any]:
    """Force an immediate UID rotation (superadmin action, logged)."""
    g = _singleton(db)
    if g.superadmin_user_id != user.id:
        g.superadmin_user_id = user.id
    g.last_superadmin_login_at = _now()
    _rotate(g, _now())
    g.updated_at = _now()
    db.commit()
    db.refresh(g)
    return _to_dict(g, succession_state(db))


def _rotate(g: KudosGovernance, now: datetime) -> None:
    old = g.uid
    if old:
        try:
            prev = json.loads(g.previous_uids or "[]")
        except (TypeError, json.JSONDecodeError):
            prev = []
        prev.append(old)
        g.previous_uids = json.dumps(prev[-4:])  # keep the last few for audit
    g.uid = _gen_uid()
    g.last_rotation_at = now
    g.next_rotation_at = now + timedelta(days=(g.uid_rotates_every_days or 5))


# ──────────────────────────────────────────────
# SUCCESSION — transparent, never covert
# ──────────────────────────────────────────────

def succession_state(db: Session) -> str:
    """Governance mode:

    * ``owned``        — the superadmin is active.
    * ``self-managed`` — inactive >= succession_inactive_days (default 3 yrs);
                         KUDOS keeps itself running, visibly.
    * ``revived``      — inactive >= revival_years (default 5 yrs); KUDOS is
                         fully self-sustaining and self-administered.
    """
    g = _singleton(db)
    now = _now()
    last = _as_aware(g.last_superadmin_login_at)
    if not last:
        return "unclaimed"
    days = (now - last).days
    revival_days = (g.revival_years or 5) * 365
    if days >= revival_days:
        return "revived"
    if days >= (g.succession_inactive_days or 1095):
        return "self-managed"
    return "owned"


def governance_status(db: Session) -> dict[str, Any]:
    """Full, visible governance snapshot for the root dashboard."""
    g = _singleton(db)
    mode = succession_state(db)
    next_rot = _as_aware(g.next_rotation_at)
    return {
        **{
            "identity": _to_dict(g, mode),
            "mode": mode,
            "mode_label": {
                "owned": "Superadmin is active",
                "self-managed": "Self-managed — superadmin inactive (KUDOS keeps running, visibly)",
                "revived": "Fully self-sustaining — superadmin inactive for years",
                "unclaimed": "No superadmin login yet",
            }.get(mode, mode),
            "rotation_due_days": (
                max(0, (next_rot - _now()).days) if next_rot else 0
            ),
            "policy": {
                "uid_rotates_every_days": g.uid_rotates_every_days or 5,
                "succession_inactive_days": g.succession_inactive_days or 1095,
                "revival_years": g.revival_years or 5,
                "transparency": "visible-status + full audit log; no covert operation",
            },
        },
    }


# ──────────────────────────────────────────────
# REVIVAL BUNDLE — what travels with KUDOS
# ──────────────────────────────────────────────

def _git_head() -> str:
    try:
        out = subprocess.run(
            ["git", "-C", _REPO_PATH, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _env_template() -> list[str]:
    """Names of the environment variables a fresh host must supply (no values)."""
    fields = [
        "APP_ENV", "SECRET_KEY", "DATABASE_URL", "REDIS_URL",
        "OPENAI_API_KEY", "GOOGLE_GEMINI_API_KEY", "GROQ_API_KEY",
        "ELEVENLABS_API_KEY", "STORAGE_BACKEND",
        "MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "MINIO_BUCKET",
        "CORS_ORIGINS", "REQUIRE_APPROVAL", "LLM_PROVIDER",
    ]
    return [f for f in fields if getattr(settings, f, None) is not None] or ["(no env overrides needed)"]


def revival_bundle(db: Session) -> dict[str, Any]:
    """Describe everything KUDOS needs to re-stand and keep running anywhere."""
    brain_facts = 0
    try:
        from app.models import KudosBrain
        brain_facts = db.query(KudosBrain).count()
    except Exception:
        pass

    dump = (
        f"docker compose -f {_COMPOSE} exec -T db pg_dump -U dc_user digital_campus "
        f"-Fc -f /tmp/kudos.dump && "
        f"docker compose -f {_COMPOSE} cp db:/tmp/kudos.dump ./kudos-backup.dump"
    )
    restore = (
        f"docker compose -f {_COMPOSE} exec -T db pg_restore -U dc_user -d digital_campus "
        f"--clean --if-exists < ./kudos-backup.dump"
    )
    return {
        "code_commit": _git_head(),
        "repository": "the committed repo (everything KUDOS needs to run is in code)",
        "compose_file": _COMPOSE,
        "services": ["db", "redis", "minio", "backend", "mcp", "worker", "frontend"],
        "env_template": _env_template(),
        "migration_command": "python -m alembic upgrade head",
        "db_dump_command": dump,
        "db_restore_command": restore,
        "brain_facts": brain_facts,
        "brain_status_endpoint": "/api/v1/kudos/brain/status",
        "cloud_target": (settings.MINIO_BUCKET or "kudos") if settings.STORAGE_BACKEND != "local" else "local-disk",
        "note": "Run self-heal on any host with Docker + the repo; KUDOS rebuilds, migrates, restores and verifies itself.",
    }


# ──────────────────────────────────────────────
# SELF-HEAL — rebuild anywhere, keep running
# ──────────────────────────────────────────────

def self_heal_bootstrap(db: Session) -> str:
    """Return a reproducible HOST script that re-stands the full stack.

    KUDOS generates this from its own configuration; the operator runs it on
    a machine with Docker and the repo. Every step is echoed and health is
    verified at the end — nothing covert.
    """
    bundle = revival_bundle(db)
    migrate = bundle["migration_command"]
    return f"""#!/usr/bin/env bash
# KUDOS Self-Heal — rebuild & re-stand the whole stack from the committed repo.
# Generated by KUDOS on {_now().strftime('%Y-%m-%d %H:%M')} · commit {bundle['code_commit']}
# Safe to run on any host with Docker + this repository. Everything is echoed.
set -euo pipefail
REPO="${{1:-.}}"
cd "$REPO"

echo "[1/6] pulling the latest committed code"
git pull --ff-only || echo "warn: pull skipped (offline/no remote) — using local commit"

echo "[2/6] rebuilding backend + frontend images"
docker compose -f {_COMPOSE} build backend frontend

echo "[3/6] applying database migrations"
docker compose -f {_COMPOSE} run --rm backend {migrate}

echo "[4/6] restoring a backup only when the database is empty"
if ! docker compose -f {_COMPOSE} exec -T db psql -U dc_user -d digital_campus -tAc \\
  "SELECT 1 FROM information_schema.tables WHERE table_name='users' LIMIT 1" | grep -q 1; then
  echo "   -> database empty; restoring latest dump if present"
  if [ -f ./kudos-backup.dump ]; then
    docker compose -f {_COMPOSE} exec -T db pg_restore -U dc_user -d digital_campus --clean --if-exists < ./kudos-backup.dump
  else
    echo "   -> no dump found; starting fresh (migrations already ran)"
  fi
fi

echo "[5/6] bringing the whole stack up"
docker compose -f {_COMPOSE} up -d

echo "[6/6] verifying KUDOS is healthy"
sleep 20
curl -fsS http://localhost:8000/api/v1/health || {{ echo "KUDOS health check failed"; exit 1; }}
echo
echo "KUDOS is back online."
echo "Next: superadmin, log in once — KUDOS will assign your rotating identity."
"""


def self_heal_plan(db: Session) -> dict[str, Any]:
    """Human-readable plan of what self-heal will do (shown before running)."""
    return {
        "steps": [
            "Pull the latest committed code (or keep the local commit)",
            "Rebuild backend + frontend Docker images",
            "Run all pending database migrations",
            "Restore the latest backup only if the database is empty",
            "Bring up db, redis, minio, backend, mcp, worker, frontend",
            "Verify /api/v1/health",
        ],
        "target": "any host with Docker and this repository",
        "generated_at": _now().isoformat(),
        "bootstrap_command": "./scripts/kudos-self-heal.sh  (or copy the script from /api/v1/root/continuity)",
    }
