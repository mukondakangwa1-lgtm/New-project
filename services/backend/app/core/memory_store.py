"""Universal Memory: persistent, layered memory for KUDOS.

Layers:
  short_term - recent facts/context, expires automatically
  long_term  - promoted facts and preferences, kept indefinitely
  knowledge  - facts learned from connected sources
  system     - operational memory (user settings, errors)

Retrieval prefers semantic (embedding) ranking when pgvector is available
and falls back to keyword + importance + recency scoring everywhere.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.models import KudosMemory

STORAGE_LAYERS = ("short_term", "long_term", "knowledge", "system")
MEMORY_KINDS = ("fact", "preference", "concept", "event", "rule", "error", "success", "context")

SHORT_TERM_TTL_DAYS = 3
CONSOLIDATE_AFTER_ACCESSES = 3
CONSOLIDATE_IMPORTANCE = 0.8


def _now() -> datetime:
    return datetime.now(UTC)


def _try_embed(text: str) -> list[float] | None:
    """Embed text; return None on any failure so callers fall back."""
    if not settings.SEMANTIC_SEARCH_ENABLED:
        return None
    try:
        from app.core.embeddings import get_embedding_provider

        provider = get_embedding_provider()
        embedding = provider.embed(text)
        if not embedding or len(embedding) == 0:
            return None
        return [float(x) for x in embedding]
    except Exception:
        return None


def _not_expired_clause():
    return (KudosMemory.expires_at.is_(None)) | (KudosMemory.expires_at > _now())


def _memory_to_dict(record: KudosMemory) -> dict[str, Any]:
    tags = []
    try:
        tags = json.loads(record.tags or "[]")
    except (TypeError, json.JSONDecodeError):
        tags = []
    return {
        "id": record.id,
        "layer": record.layer,
        "kind": record.kind,
        "content": record.content,
        "summary": record.summary or "",
        "importance": float(record.importance or 0.5),
        "tags": tags,
        "source": record.source or "",
        "access_count": record.access_count or 0,
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def write_memory(
    db,
    user_id: int,
    content: str,
    layer: str = "short_term",
    kind: str = "fact",
    importance: float = 0.5,
    tags: list[str] | None = None,
    source: str = "",
    expires_at: datetime | None = None,
    device_policy: str = "replicated",
) -> KudosMemory:
    """Create a memory entry. Embedding failures degrade gracefully.

    When devices are registered, the entry is replicated to the ring;
    otherwise Postgres alone holds it until devices appear.
    """
    if layer not in STORAGE_LAYERS:
        raise ValueError(f"Invalid layer: {layer}")
    if kind not in MEMORY_KINDS:
        raise ValueError(f"Invalid kind: {kind}")
    if not content or not content.strip():
        raise ValueError("Memory content cannot be empty")
    if device_policy not in ("local", "replicated", "critical"):
        raise ValueError(f"Invalid device_policy: {device_policy}")

    embedding = _try_embed(content)

    # short-term memories expire automatically unless given an explicit TTL
    if expires_at is None and layer == "short_term":
        expires_at = _now() + timedelta(days=SHORT_TERM_TTL_DAYS)

    record = KudosMemory(
        user_id=user_id,
        layer=layer,
        kind=kind,
        content=content.strip(),
        summary="",
        embedding=embedding,
        importance=max(0.0, min(1.0, float(importance))),
        tags=json.dumps(tags or []),
        source=source or "",
        expires_at=expires_at,
        device_policy=device_policy,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    try:
        from app.core.device_storage import assign_replicas

        assign_replicas(db, record)
    except Exception:
        db.rollback()
    return record


def _semantic_rank(db, records: list[KudosMemory], embedding: list[float]) -> list[KudosMemory] | None:
    """Rank memories by embedding distance; None when pgvector is unavailable."""
    try:
        distance = KudosMemory.embedding.cosine_distance(embedding)
    except Exception:
        return None
    try:
        ids = [r.id for r in records]
        rows = db.execute(
            select(KudosMemory.id, distance.label("_dist")).where(KudosMemory.id.in_(ids)).order_by(distance)
        ).all()
        lookup = {r.id: r for r in records}
        return [lookup[row._mapping["id"]] for row in rows if row._mapping["id"] in lookup]
    except Exception:
        return None


def _keyword_score(record: KudosMemory, terms: list[str]) -> float:
    """Fraction of query terms matched, blended with importance. 0 = no match."""
    haystack = f"{record.content} {record.summary or ''}".lower()
    matches = sum(1 for t in terms if t in haystack)
    if matches == 0:
        return 0.0
    return (matches / len(terms)) * 0.6 + float(record.importance or 0.5) * 0.4


def _recency_boost(record: KudosMemory) -> float:
    """Small boost for recently created/accessed memories (max ~0.25)."""
    ref = record.last_access_at or record.created_at
    if not ref:
        return 0.0
    if ref.tzinfo is None:  # SQLite returns naive datetimes
        ref = ref.replace(tzinfo=UTC)
    days = max(0.0, (_now() - ref).total_seconds() / 86400.0)
    return max(0.0, 0.25 - days * 0.01)


def retrieve_memories(
    db,
    user_id: int,
    query: str = "",
    layers: list[str] | None = None,
    limit: int = 8,
    importance_min: float = 0.0,
) -> list[KudosMemory]:
    """Return the most relevant memories for a user.

    Expired short-term memories are excluded; stale rows are lazily deleted.
    """
    statement = select(KudosMemory).where(
        KudosMemory.user_id == user_id,
        _not_expired_clause(),
    )
    if layers:
        statement = statement.where(KudosMemory.layer.in_(layers))
    if importance_min > 0:
        statement = statement.where(KudosMemory.importance >= importance_min)

    records = list(db.scalars(statement).all())
    if not records:
        return []

    # Semantic path when embeddings are available and a query is given
    if query.strip():
        embedding = _try_embed(query)
        if embedding is not None:
            ranked = _semantic_rank(db, records, embedding)
            if ranked is not None:
                ranked = [r for r in ranked if float(r.importance or 0) >= importance_min]
                return ranked[:limit]

    # Keyword + importance + recency path (SQLite-safe)
    terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2] if query else []
    scored: list[tuple[float, KudosMemory]] = []
    for record in records:
        if terms:
            score = _keyword_score(record, terms)
            if score <= 0:
                continue
        else:
            # No query: fresh, important, and frequently tapped memories surface first
            score = _recency_boost(record) + float(record.importance or 0.5) / 5.0
            score += min(1.0, (record.access_count or 0) / 10.0) * 0.15
        scored.append((score, record))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [record for _, record in scored[:limit]]


def record_access(db, memory: KudosMemory) -> None:
    """Bump usage stats for a memory."""
    try:
        memory.access_count = (memory.access_count or 0) + 1
        memory.last_access_at = _now()
        db.add(memory)
        db.commit()
    except Exception:
        db.rollback()


def consolidate_memories(db, user_id: int) -> int:
    """Promote well-used short-term memories into long-term storage.

    Promotion happens after repeated retrieval (>= 3) or when importance
    is high (>= 0.8). Returns the number promoted.
    """
    now = _now()
    candidates = (
        db.execute(
            select(KudosMemory).where(
                KudosMemory.user_id == user_id,
                KudosMemory.layer == "short_term",
                (KudosMemory.expires_at.is_(None)) | (KudosMemory.expires_at > now),
            )
        )
        .scalars()
        .all()
    )

    promoted = 0
    for record in candidates:
        keep = (record.access_count or 0) >= CONSOLIDATE_AFTER_ACCESSES
        if not keep:
            keep = float(record.importance or 0.5) >= CONSOLIDATE_IMPORTANCE
        if keep:
            record.layer = "long_term"
            record.expires_at = None
            record.importance = min(1.0, float(record.importance or 0.5) + 0.1)
            db.add(record)
            promoted += 1
    if promoted:
        db.commit()
    return promoted


def build_memory_context(db, user_id: int, query: str = "", limit: int = 5) -> str:
    """Format the best memories as readable context lines for the LLM prompt."""
    memories = retrieve_memories(db, user_id, query=query, limit=limit)
    if not memories:
        return ""
    lines = ["User memory:"]
    for m in memories:
        record_access(db, m)
        prefix = m.layer if m.layer != "short_term" else "recent"
        extra = f" (source: {m.source})" if m.source else ""
        lines.append(f"- [{prefix}][{m.kind}] {m.content}{extra}")
    return "\n".join(lines)


def clear_memories(db, user_id: int, layer: str | None = None) -> int:
    """Delete a user's memories (optionally one layer). Returns count."""
    statement = select(KudosMemory).where(KudosMemory.user_id == user_id)
    if layer:
        statement = statement.where(KudosMemory.layer == layer)
    records = db.execute(statement).scalars().all()
    from app.core.device_storage import purge_memory_replicas

    for r in records:
        try:
            purge_memory_replicas(db, r.id)
        except Exception:
            db.rollback()
        db.delete(r)
    db.commit()
    return len(records)


def get_memory(db, memory_id: int, user_id: int) -> KudosMemory | None:
    return db.query(KudosMemory).filter(KudosMemory.id == memory_id, KudosMemory.user_id == user_id).first()
