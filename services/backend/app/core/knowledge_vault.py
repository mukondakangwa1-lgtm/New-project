"""KUDOS Knowledge Vault — one searchable place for everything KUDOS knows.

The vault holds superadmin-curated canonical articles (source_type="curated")
plus indexed mirrors of approved documents, web knowledge and memories
(source_type="document" | "web" | "memory"). Search is an in-Python BM25 over
title + content + tags — exactly the kind of deterministic retrieval the
offline brain runs, so curation and retrieval work with zero external LLM.

Policies honoured:
  * Curated entries are global to every user.
  * Indexed document/web entries are global (they are shared knowledge).
  * Indexed memories are scoped to their owner — the vault never leaks one
    user's private knowledge to another.
  * Only is_approved + is_active entries are ever retrievable or searched.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.kudos_brain import brain_terms
from app.models_extended import KudosVaultEntry
from app.models import KudosDocument, KudosWebKnowledge, KudosMemory

_SLUG_REGEX = re.compile(r"[^a-z0-9]+")
_BM25_K1 = 1.2
_BM25_B = 0.75

# How to mirror each external source into a vault entry.
_SOURCE_ORDER = {"curated": 0, "document": 1, "document_chunk": 1, "web": 2, "memory": 3}


def slugify(text: str, fallback: str = "entry") -> str:
    slug = _SLUG_REGEX.sub("-", (text or "").lower()).strip("-")
    return slug[:120] or fallback


def _search_text(title: str, summary: str, content: str, tags: str) -> str:
    return " ".join([
        (title or "")[:300],
        (summary or "")[:700],
        (content or ""),
        (tags or "").replace(",", " "),
    ])


def _bm25_score(terms: list[str], doc_tokens: list[str], avgdl: float, doc_len: float, idf: dict[str, float]) -> float:
    """BM25 (Okapi) score for a document given precomputed idf values."""
    if not doc_tokens or not terms:
        return 0.0
    freq: dict[str, int] = {}
    for t in doc_tokens:
        freq[t] = freq.get(t, 0) + 1
    score = 0.0
    for term in terms:
        tf = freq.get(term, 0)
        if tf <= 0 or term not in idf:
            continue
        denom = tf + _BM25_K1 * (1 - _BM25_B + _BM25_B * (doc_len / max(avgdl, 1.0)))
        score += idf[term] * (tf * (_BM25_K1 + 1)) / denom
    return score


def vault_search(
    db: Session,
    query: str = "",
    user_id: Optional[int] = None,
    category: str = "",
    source_type: str = "",
    q: str = "",  # alias for query
    limit: int = 10,
    offset: int = 0,
) -> list[dict]:
    """BM25 search over active, approved vault entries.

    Visibility: curated + document + web entries are global; memory entries
    are only visible to their owner. Returns serialized dicts sorted by score
    (then importance), with ``score`` when a query is given.
    """
    q = (query or q or "").strip()
    try:
        rows = (
            db.query(KudosVaultEntry)
            .filter(
                KudosVaultEntry.is_active.is_(True),
                KudosVaultEntry.is_approved.is_(True),
            )
            .limit(8000)
            .all()
        )
    except Exception:
        return []

    # Scope memories to their owner; everything else is shared.
    visible = [r for r in rows if r.source_type != "memory" or (user_id and r.user_id == user_id)]
    if category:
        visible = [r for r in visible if r.category == category]
    if source_type:
        visible = [r for r in visible if r.source_type == source_type]

    results: list[dict] = []
    if q:
        terms = brain_terms(q)
        if not terms:
            return []
        corpus_terms: dict[str, int] = {}
        docs: list[dict] = []
        for r in visible:
            toks = brain_terms((r.search_text or "") + " " + (r.title or ""))
            docs.append({"row": r, "toks": toks})
            for t in set(toks):
                corpus_terms[t] = corpus_terms.get(t, 0) + 1
        n = len(docs)
        idf = {
            t: math.log(1 + (n - df + 0.5) / (df + 0.5))
            for t, df in corpus_terms.items()
        }
        avgdl = sum(len(d["toks"]) for d in docs) / max(n, 1)
        scored = []
        for d in docs:
            sc = _bm25_score(terms, d["toks"], avgdl, len(d["toks"]), idf)
            if sc > 0:
                scored.append((sc, d["row"]))
        scored.sort(key=lambda x: (-x[0], -x[1].importance))
        for sc, row in scored[offset: offset + limit]:
            d = _as_dict(row)
            d["score"] = round(sc, 4)
            results.append(d)
    else:
        ordered = sorted(visible, key=lambda r: (-(r.importance or 0), -((r.updated_at or datetime.min).timestamp() or r.id)))
        for row in ordered[offset: offset + limit]:
            results.append(_as_dict(row))

    return results


def _as_dict(row: KudosVaultEntry) -> dict:
    return {
        "id": row.id,
        "key": row.key,
        "title": row.title or "",
        "slug": row.slug or "",
        "summary": row.summary or "",
        "content": row.content or "",
        "category": row.category or "general",
        "tags": row.tags or "",
        "source_type": row.source_type,
        "source_id": row.source_id,
        "author_id": row.author_id,
        "user_id": row.user_id,
        "importance": row.importance or 0,
        "version": row.version or 1,
        "parent_id": row.parent_id,
        "is_approved": bool(row.is_approved),
        "is_active": bool(row.is_active),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def get_entry(db: Session, entry_id: int) -> Optional[KudosVaultEntry]:
    return db.query(KudosVaultEntry).filter(KudosVaultEntry.id == entry_id).first()


def upsert_curated(
    db: Session,
    *,
    title: str,
    content: str,
    category: str = "general",
    tags: str = "",
    summary: str = "",
    importance: int = 0,
    author_id: Optional[int] = None,
    key: str = "",
    source_id: Optional[int] = None,
    is_approved: bool = True,
    entry_id: Optional[int] = None,
) -> Optional[KudosVaultEntry]:
    """Create or update a curated vault entry. Editing bumps the version."""
    title = (title or "").strip()
    if not title:
        return None
    key = (key or "").strip() or f"curated-{slugify(title)}-{source_id or 0}"

    if entry_id:
        row = get_entry(db, entry_id)
        if row:
            row.title = title
            row.slug = slugify(title)
            row.summary = summary
            row.content = content or ""
            row.category = category or "general"
            row.tags = tags or ""
            row.importance = importance or 0
            row.author_id = author_id
            row.search_text = _search_text(title, summary, content, tags)
            row.version = (row.version or 1) + 1
            row.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(row)
            return row

    existing = db.query(KudosVaultEntry).filter(KudosVaultEntry.key == key).first()
    if existing:
        return upsert_curated(
            db, title=title, content=content, category=category, tags=tags,
            summary=summary, importance=importance, author_id=author_id,
            key=key, source_id=source_id, is_approved=is_approved,
            entry_id=existing.id,
        )

    row = KudosVaultEntry(
        key=key,
        title=title,
        slug=slugify(title),
        summary=summary,
        content=content or "",
        category=category or "general",
        tags=tags or "",
        source_type="curated",
        source_id=source_id,
        author_id=author_id,
        importance=importance or 0,
        version=1,
        is_approved=is_approved,
        is_active=True,
        search_text=_search_text(title, summary, content, tags),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        approved_at=datetime.now(timezone.utc) if is_approved else None,
    )
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        return None


def delete_entry(db: Session, entry_id: int) -> bool:
    row = get_entry(db, entry_id)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


# ──────────────────────────────────────────────
# INDEXING — mirror external sources into the vault
# ──────────────────────────────────────────────

def index_source(db: Session, source_type: str, source_id: int, *, force: bool = False) -> Optional[KudosVaultEntry]:
    """Create (or refresh) the vault mirror of one external source.

    source_type: document | web | memory
    """
    key = f"{source_type}-{source_id}"
    existing = db.query(KudosVaultEntry).filter(KudosVaultEntry.key == key).first()

    title = summary = content = tags = ""
    category, user_id = "document", None

    if source_type == "document":
        src = db.get(KudosDocument, source_id)
        if not src or not src.is_approved or not src.is_active:
            return None
        title, summary, content = src.title or src.filename or "Document", src.summary or "", src.content or ""
        tags, category, user_id = src.tags or "", "document", src.uploaded_by
    elif source_type == "web":
        src = db.get(KudosWebKnowledge, source_id)
        if not src or not src.is_approved or not src.is_active:
            return None
        title = src.title or src.url or "Web knowledge"
        content = src.content or src.summary or ""
        summary = src.summary or ""
        tags, category = getattr(src, "tags", None) or "", "web"
    elif source_type == "memory":
        src = db.get(KudosMemory, source_id)
        if not src:
            return None
        title = f"Memory: {src.content[:80]}"
        content, summary = src.content or "", src.content[:200]
        tags, category, user_id = src.tags or "", "memory", src.user_id
    else:
        return None

    if not content and not title:
        return None

    if existing:
        existing.title = (title or "")[:300]
        existing.summary = (summary or "")[:600]
        existing.content = content or ""
        existing.tags = (tags or "")[:500]
        existing.user_id = user_id
        existing.search_text = _search_text(title, summary, content, tags)
        existing.updated_at = datetime.now(timezone.utc)
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    row = KudosVaultEntry(
        key=key,
        title=(title or "")[:300],
        slug=slugify(title),
        summary=(summary or "")[:600],
        content=content or "",
        category=category,
        tags=(tags or "")[:500],
        source_type=source_type,
        source_id=source_id,
        user_id=user_id,
        importance=10 if source_type == "document" else 0,
        version=1,
        is_approved=True,
        is_active=True,
        search_text=_search_text(title, summary, content, tags),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        approved_at=datetime.now(timezone.utc),
    )
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        return None


def reindex_all(db: Session, limit_docs: int = 500, limit_web: int = 500, limit_memories: int = 500) -> dict[str, int]:
    """Mirror every approved/active document, web knowledge item and memory
    into the vault. Idempotent (keyed upserts); safe to re-run."""
    indexed = {"document": 0, "web": 0, "memory": 0}
    try:
        for doc in db.query(KudosDocument).filter(
            KudosDocument.is_approved.is_(True), KudosDocument.is_active.is_(True)
        ).limit(limit_docs).all():
            if index_source(db, "document", doc.id):
                indexed["document"] += 1
    except Exception:
        pass
    try:
        for item in db.query(KudosWebKnowledge).filter(
            KudosWebKnowledge.is_approved.is_(True), KudosWebKnowledge.is_active.is_(True)
        ).limit(limit_web).all():
            if index_source(db, "web", item.id):
                indexed["web"] += 1
    except Exception:
        pass
    try:
        for mem in db.query(KudosMemory).filter(
            KudosMemory.layer.in_(("knowledge", "long_term", "system"))
        ).limit(limit_memories).all():
            if mem.user_id and index_source(db, "memory", mem.id):
                indexed["memory"] += 1
    except Exception:
        pass
    return indexed


# ──────────────────────────────────────────────
# STATUS & HELPERS
# ──────────────────────────────────────────────

def vault_stats(db: Session) -> dict[str, Any]:
    stats = {"total": 0, "by_source_type": {}, "by_category": {}, "approved": 0, "active": 0}
    try:
        rows = db.query(KudosVaultEntry).all()
    except Exception:
        return stats
    stats["total"] = len(rows)
    for r in rows:
        st = r.source_type or "curated"
        cat = r.category or "general"
        stats["by_source_type"][st] = stats["by_source_type"].get(st, 0) + 1
        stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
        if r.is_approved:
            stats["approved"] += 1
        if r.is_active:
            stats["active"] += 1
    return stats


def vault_context(db: Session, query: str = "", user_id: Optional[int] = None, limit: int = 3) -> str:
    """Prompt-injection block: the top vault entries for a question. Empty
    string when nothing relevant is found — never forces content in."""
    entries = vault_search(db, query=query, user_id=user_id, limit=limit) if query else []
    if not entries:
        return ""
    lines = []
    for i, e in enumerate(entries, start=1):
        kind = e["source_type"]
        body = (e.get("summary") or e.get("content") or "")[:300]
        lines.append(f"[{i}] ({kind}) {e['title']}: {body}")
    return (
        "Knowledge vault top hits for this question:\n"
        + "\n".join(lines)
        + "\nThese come from KUDOS's own curated/indexed vault — prefer them over guessing."
    )