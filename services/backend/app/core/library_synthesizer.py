"""
KUDOS Library Synthesizer — turns what KUDOS learns into readable library
documents so the campus library is always populated and never empty.

Every learning cycle hands the newest knowledge it gathered (web, social,
archive, search, crawls, connectors) to ``synthesize_learned_content``, which:
  1. groups the fresh items by topic,
  2. formulates each into a well-structured markdown library document,
  3. asks the best available LLM to write a short "Connections" essay that
     ties the topic to other things KUDOS has learned (falling back to a
     keyword-based related-topics list when no LLM is configured),
  4. files it as an AUTO-APPROVED (public) document, tagged kudos-synthesized.

``ensure_library_seeded`` guarantees the library is never empty: the first
request that finds no public documents triggers a small orientation document.
"""

from __future__ import annotations

import re

from app.core.agent_bridge import _slug

_PREFIX_RE = re.compile(r"^\[[^\]]+\]\s*")  # strips "[Auto-Learn] ", "[Reddit r/x] " etc.


def _topic_from_title(title: str) -> str:
    """Reduce a learned item's title to its bare subject name."""
    t = (title or "").strip()
    t = _PREFIX_RE.sub("", t)
    return t.strip(" -:") or title


def _keywords(text: str, limit: int = 6) -> set[str]:
    return set(
        re.findall(r"[a-zA-Z]{4,}", (text or "").lower())[:limit]
    ) - {"about", "that", "with", "this", "from", "have", "they", "there", "what", "when", "then", "them", "into", "more", "than"}


def _related_documents(db, topic: str, exclude_ids: list[int], limit: int = 5) -> list[tuple[int, str]]:
    """Best-effort related library documents found through shared keywords."""
    from app.models import KudosDocument

    words = _keywords(topic)
    related: list[tuple[int, str]] = []
    docs = (
        db.query(KudosDocument)
        .filter(KudosDocument.is_active, KudosDocument.is_approved)
        .order_by(KudosDocument.created_at.desc())
        .limit(100)
        .all()
    )
    for d in docs:
        if d.id in exclude_ids:
            continue
        shared = words & (_keywords(d.title + " " + (d.tags or "")) | _keywords(d.summary or ""))
        if shared:
            related.append((d.id, d.title))
            if len(related) >= limit:
                break
    return related


async def _write_connections_essay(topic: str, content: str, related: list[tuple[int, str]]) -> str:
    """Ask KUDOS's best LLM for a short 'how this connects' paragraph.

    Falls back to a keyword-driven list of related topics when no LLM is
    configured or the call fails — synthesis must never block the cycle.
    """
    related_titles = [t for _, t in related]
    try:
        from app.core.llm_engine import get_llm_response

        prompt = (
            f"Write a warm, insightful paragraph (3-5 sentences) explaining how the topic "
            f"'{topic}' connects to other subjects, ideas or fields of knowledge. "
            "Mention real, meaningful relationships — shared history, shared concepts, "
            "or how one informs the other. "
            "If some of these recent KUDOS topics are relevant, weave them in naturally: "
            + ", ".join(related_titles[:4])
            + "."
        )
        essay = await get_llm_response(question=prompt, knowledge_context=content[:8000])
        if essay and len(essay.strip()) > 30:
            return essay.strip()
    except Exception:
        pass

    if related_titles:
        return (
            f"This connects to other things KUDOS has been learning — "
            f"{', '.join(related_titles[:4])}. "
            "Exploring them side by side shows how knowledge builds on itself."
        )
    return (
        "Every topic KUDOS learns folds into the wider web of the campus "
        "library — check back as more subjects are added and the links between them grow."
    )


def store_synthesized_library_document(
    db,
    title: str,
    content: str,
    summary: str,
    connections: str,
    actor_id: int | None = None,
    sources: list[str] | None = None,
):
    """File a KUDOS-formulated document as AUTO-APPROVED (public) library doc.

    Idempotent by (title, kudos-synthesized tag): re-learning the same subject
    refreshes the document instead of duplicating it.
    """
    from app.api.v1.endpoints.kudos import chunk_text, extract_keywords, simple_summarize
    from app.models import KudosChunk, KudosDocument

    text = (content or "").strip()
    if not text:
        return None, False

    clean_title = title.strip()
    if not clean_title:
        return None, False

    full = text
    if connections:
        full = f"{full}\n\n## 🔗 Connections\n\n{connections}"

    source_lines = ""
    if sources:
        seen: set[str] = set()
        lines = []
        for s in sources[:8]:
            s = (s or "").strip()
            if s and s not in seen:
                seen.add(s)
                lines.append(f"- {s}")
        if lines:
            source_lines = "\n\n## 📚 Sources\n\n" + "\n".join(lines)

    if source_lines:
        full = f"{full}{source_lines}"

    existing = (
        db.query(KudosDocument)
        .filter(KudosDocument.title == clean_title)
        .filter(KudosDocument.tags.like("%kudos-synthesized%"))
        .first()
    )
    if existing:
        existing.content = full
        existing.summary = summary or simple_summarize(text)
        existing.is_approved = True
        existing.is_active = True
        db.flush()
        db.query(KudosChunk).filter(KudosChunk.document_id == existing.id).delete()
        chunks = chunk_text(full)
        for i, chunk_content in enumerate(chunks):
            db.add(
                KudosChunk(
                    document_id=existing.id,
                    chunk_index=i,
                    content=chunk_content,
                    word_count=len(chunk_content.split()),
                    keywords=extract_keywords(chunk_content),
                )
            )
        existing.chunk_count = len(chunks)
        return existing, False

    doc = KudosDocument(
        uploaded_by=actor_id,
        title=clean_title,
        filename=f"{_slug(clean_title)}.txt",
        file_type="md",
        storage_key="",
        content=full,
        summary=summary or simple_summarize(text),
        tags=f"kudos-synthesized, subject, kudos-learned",
        is_approved=True,  # KUDOS-formulated → public immediately
        is_active=True,
    )
    db.add(doc)
    db.flush()
    chunks = chunk_text(full)
    for i, chunk_content in enumerate(chunks):
        db.add(
            KudosChunk(
                document_id=doc.id,
                chunk_index=i,
                content=chunk_content,
                word_count=len(chunk_content.split()),
                keywords=extract_keywords(chunk_content),
            )
        )
    doc.chunk_count = len(chunks)
    return doc, True


def _group_learned_items(rows: list) -> dict[str, dict]:
    """Group fresh learned items by their bare topic name."""
    groups: dict[str, dict] = {}
    for row in rows:
        topic = _topic_from_title(row.title)
        if not topic:
            continue
        group = groups.setdefault(
            topic,
            {"title": topic, "content_parts": [], "sources": []},
        )
        content = (row.content or "").strip()
        if content:
            group["content_parts"].append(content)
        url = getattr(row, "url", None)
        if url:
            group["sources"].append(url)
    return groups


def _formulate_content(topic: str, content_parts: list[str], related: list[tuple[int, str]]) -> tuple[str, str]:
    """Assemble the markdown body and a local summary from the raw parts."""
    body = "\n\n".join(p[:12000] for p in content_parts)
    summary = " ".join(body.split())[:320].rstrip(" ,.-") + "…" if len(body.split()) > 320 else body[:320]
    if not summary:
        summary = topic

    sections = [
        f"# {topic}",
        "",
        "> KUDOS learned this from the sources below, distilled into a readable summary for the library.",
        "",
        "## 📖 Overview",
        "",
        summary,
        "",
        "## 🧠 Key points",
        "",
    ]
    bullet = _keywords(body, limit=8)
    if bullet:
        for word in sorted(bullet):
            sections.append(f"- **{word.title()}** — a core strand of this topic's study.")
    else:
        sections.append("- A living note KUDOS keeps expanding as it learns more.")
    sections.append("")
    return "\n".join(sections), summary


async def synthesize_learned_content(db, actor_id: int | None = None, limit: int = 12) -> dict:
    """Turn the most recent learned knowledge into public library documents.

    Runs inside the learning cycle. Gathers the newest approved knowledge,
    groups it by topic, formulates each topic into a library document, and
    files it as auto-approved. Returns a small summary dict for the log.
    """
    from app.models import KudosDocument, KudosWebKnowledge

    fresh = (
        db.query(KudosWebKnowledge)
        .filter(KudosWebKnowledge.is_approved)
        .order_by(KudosWebKnowledge.id.desc())
        .limit(limit)
        .all()
    )
    if not fresh:
        return {"documents_added": 0, "documents_updated": 0, "topics": []}

    groups = _group_learned_items(fresh)
    added = 0
    updated = 0
    done_topics = []

    for topic, group in list(groups.items())[:6]:
        existing = (
            db.query(KudosDocument)
            .filter(KudosDocument.title == topic)
            .filter(KudosDocument.tags.like("%kudos-synthesized%"))
            .first()
        )
        # Already synthesized → skip to avoid rewriting the same doc each
        # cycle. Newly learned topics keep flowing into the library.
        if existing:
            continue

        related = _related_documents(db, topic, exclude_ids=[])
        content, summary = _formulate_content(topic, group["content_parts"], related)
        connections = await _write_connections_essay(topic, content, related)
        doc, created = store_synthesized_library_document(
            db,
            title=topic,
            content=content,
            summary=summary,
            connections=connections,
            actor_id=actor_id,
            sources=group["sources"],
        )
        if doc:
            if created:
                added += 1
            else:
                updated += 1
            done_topics.append(topic)

    db.commit()
    return {"documents_added": added, "documents_updated": updated, "topics": done_topics}


async def ensure_library_seeded(db, actor_id: int | None = None) -> dict:
    """Guarantee the library is never empty.

    If there are no approved, active documents at all, write a small
    'KUDOS Library — Getting Started' orientation document (auto-approved) so
    the first visitor always finds a shelf.
    """
    from app.models import KudosDocument

    has_docs = (
        db.query(KudosDocument)
        .filter(KudosDocument.is_active, KudosDocument.is_approved)
        .first()
    )
    if has_docs:
        return {"seeded": False}

    title = "KUDOS Library — Getting Started"
    existing = (
        db.query(KudosDocument)
        .filter(KudosDocument.title == title)
        .filter(KudosDocument.tags.like("%kudos-synthesized%"))
        .first()
    )
    if existing:
        return {"seeded": False}

    content = (
        "# KUDOS Library — Getting Started\n\n"
        "Welcome to the Digital Campus library. This is the collection KUDOS "
        "builds as it learns.\n\n"
        "## How the library grows\n\n"
        "KUDOS learns continuously — from connectors, web pages, Wikipedia, "
        "Reddit, Internet Archive and the searches you ask. Every learning "
        "cycle, the newest knowledge is distilled into readable documents "
        "that land here automatically. You never have to wait for it: the "
        "library is always being written.\n\n"
        "## What you can do\n\n"
        "- Search across every document, book, audio and video.\n"
        "- Open any item to read, listen or watch inside the library.\n"
        "- Follow the **Connections** sections — every document shows how it "
        "links to the rest of what KUDOS has learned.\n\n"
        "Come back often: the shelf fills up as KUDOS learns new things."
    )

    doc, _created = store_synthesized_library_document(
        db,
        title=title,
        content=content,
        summary="How to use the KUDOS library — and how it keeps itself full as KUDOS learns.",
        connections=(
            "This is the gateway to everything KUDOS has learned. As new subjects "
            "are added, they connect back here — every library entry is part of "
            "one growing web of knowledge."
        ),
        actor_id=actor_id,
    )
    db.commit()
    return {"seeded": bool(doc)}
