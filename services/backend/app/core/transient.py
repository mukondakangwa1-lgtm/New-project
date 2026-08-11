"""
Digital Campus - KUDOS Transient Media

A short-lived, auto-expiring cache for generated media (short videos, images)
that KUDOS streams to the user WITHOUT ever writing them to object storage.
Bytes live in Redis for a few minutes, are downloadable once, and are gone —
so no storage space is consumed by one-off generations.

Security: tokens are cryptographically random; each fetch returns the payload
and revokes it (single-use), so content can't be hot-linked or replayed.
"""

import hashlib
import json
import secrets

from app.core.config import settings

_DEFAULT_TTL = 60 * 15  # 15 minutes

_pool = None


def _get_client():
    """Lazy redis client (redis server is optional; we degrade gracefully)."""
    global _pool
    try:
        import redis as redis_lib
    except Exception:
        return None
    if _pool is None:
        try:
            _pool = redis_lib.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception:
            return None
    try:
        _pool.ping()
        return _pool
    except Exception:
        return None


def _key(token: str) -> str:
    return f"kudos:transient:{token}"


def put(payload_base64: str, mime_type: str, ttl: int = _DEFAULT_TTL) -> str | None:
    """Store bytes (base64) with a TTL. Returns a single-use token or None."""
    client = _get_client()
    if client is None:
        return None
    token = secrets.token_urlsafe(32)
    value = json.dumps(
        {"mime": mime_type, "data": payload_base64, "sha": hashlib.sha256(payload_base64.encode()).hexdigest()[:12]}
    )
    try:
        client.setex(_key(token), max(60, int(ttl)), value)
        return token
    except Exception:
        return None


def get_and_revoke(token: str) -> dict | None:
    """Fetch a transient payload and delete it (single-use download)."""
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(_key(token))
        if not raw:
            return None
        client.delete(_key(token))
        return json.loads(raw)
    except Exception:
        return None


def get(token: str) -> dict | None:
    """Fetch a transient payload WITHOUT deleting it. The Redis TTL still
    expires it automatically, so nothing is ever persisted."""
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(_key(token))
        return json.loads(raw) if raw else None
    except Exception:
        return None


def transient_url(token: str) -> str:
    return f"/api/v1/kudos/transient/{token}"
