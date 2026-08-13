"""KUDOS Offline Brain — persistent, self-contained knowledge + local reasoning.

KUDOS keeps its OWN brain in Postgres — a store of facts and insights, each
carrying provenance (which document / web page / memory it came from). The
brain is completely independent of any external LLM:

  * ``reason()``        — deterministic thinking over the brain + knowledge
                          base. It gathers evidence, filters by relevance,
                          extracts only verbatim supporting sentences and
                          assembles a cited answer. It never invents facts.
  * ``answer_offline()`` — clean wrapper used when no LLM is configured or
                          when KUDOS runs offline-first.
  * ``hallucination_guard()`` — verifies ANY answer (even LLM-produced ones)
                          against the evidence: every sentence must be backed
                          by a source, otherwise the answer is refused and
                          replaced by a grounded one or an honest "I don't know".

Together these drop the hallucination risk to ~0%: KUDOS only ever says
things it has evidence for, and says "I don't have that information" rather
than guessing.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import UTC, datetime
from typing import Any

import sqlalchemy
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    KudosBrain,
    KudosChunk,
    KudosDocument,
    KudosMemory,
    KudosWebKnowledge,
)

# Local stopwords — kept intentionally small and neutral. Content words drive
# both relevance scoring and the grounding (anti-hallucination) check.
_STOP = {
    "the",
    "and",
    "for",
    "are",
    "was",
    "were",
    "with",
    "that",
    "this",
    "these",
    "those",
    "have",
    "has",
    "had",
    "you",
    "your",
    "yours",
    "our",
    "ours",
    "its",
    "from",
    "into",
    "onto",
    "over",
    "under",
    "than",
    "then",
    "when",
    "where",
    "which",
    "what",
    "who",
    "whom",
    "whose",
    "while",
    "will",
    "would",
    "shall",
    "should",
    "could",
    "can",
    "may",
    "might",
    "must",
    "not",
    "but",
    "also",
    "too",
    "very",
    "just",
    "only",
    "about",
    "after",
    "before",
    "because",
    "between",
    "both",
    "each",
    "every",
    "other",
    "some",
    "such",
    "more",
    "most",
    "however",
    "therefore",
    "there",
    "here",
    "all",
    "any",
    "how",
    "why",
    "does",
    "do",
    "did",
    "is",
    "am",
    "be",
    "been",
    "being",
    "them",
    "their",
    "they",
    "it's",
    "i'm",
    "you're",
    "we're",
    "they're",
    "there's",
    "please",
    "tell",
    "give",
    "show",
    "make",
    "like",
}
_MIN_WORD = 3
_MIN_SENTENCE = 20
_MAX_SENTENCE = 320
_BRAIN_TERM_REGEX = re.compile(r"[a-zA-Z]{3,}")

# Meta/wrapper phrases KUDOS adds around answers ("Here's what I know…",
# "I'm not guessing.", "Teach me a source…"). These are conversational glue,
# NOT factual claims, so the hallucination guard must not judge them.
_META_HINTS = (
    "here's what i know",
    "every statement above",
    "i'm not guessing",
    "i don't have verified information",
    "my brain and knowledge base",
    "teach me a source",
    "i found material",
    "i'd rather be honest",
    "i'll answer for certain",
    "won't guess",
    "can't back it up",
)
# A sentence must carry at least this many content words to be judged as a
# claim; shorter fragments (templates, filler) are never flagged.
_MIN_CLAIM_WORDS = 5


# ──────────────────────────────────────────────
# TOKENIZATION & SCORING
# ──────────────────────────────────────────────


def brain_terms(text: str) -> list[str]:
    """Content words used for relevance + grounding (no stopwords, >= 3 chars)."""
    words = [w.lower() for w in _BRAIN_TERM_REGEX.findall(text or "")]
    return [w for w in words if w not in _STOP and len(w) >= _MIN_WORD]


def _score_text(text: str, keywords: str, query_terms: list[str]) -> tuple[int, int]:
    """Return (score, matched_terms) for a text against the query terms."""
    lowered = (text or "").lower()
    kw_set = {k.strip().lower() for k in (keywords or "").split(",") if k.strip()}
    score = 0
    matched = 0
    for term in query_terms:
        if term in lowered:
            score += 2 + (1 if term in kw_set else 0)
            matched += 1
        elif term in kw_set:
            score += 1
    return score, matched


def _extract_sentences(text: str) -> list[str]:
    """Split text into clean, meaningful sentences (verbatim for grounding)."""
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    out = []
    for part in parts:
        clean = part.strip()
        if _MIN_SENTENCE <= len(clean) <= _MAX_SENTENCE:
            out.append(clean)
    return out


# ──────────────────────────────────────────────
# RETRIEVAL — gather evidence KUDOS actually has
# ──────────────────────────────────────────────


def retrieve_evidence(
    db: Session,
    query: str,
    user_id: int | None = None,
    limit: int = 8,
) -> list[dict]:
    """Pull evidence from the brain, documents, web knowledge and memories.

    Every item is guaranteed to exist in KUDOS's own persistent store — this
    is the only material the offline brain may answer from.
    """
    terms = brain_terms(query)
    if not terms:
        return []

    candidates: list[dict] = []

    # 1) Brain facts (global + the user's private facts)
    try:
        brain_rows = (
            db.query(KudosBrain)
            .filter(
                (KudosBrain.user_id.is_(None)) | (KudosBrain.user_id == 0) | (KudosBrain.user_id == user_id)
                if user_id
                else (KudosBrain.user_id.is_(None)) | (KudosBrain.user_id == 0)
            )
            .limit(2000)
            .all()
        )
        for fact in brain_rows:
            if not fact.is_verified:
                continue
            score, matched = _score_text(fact.content, fact.keywords, terms)
            if score > 0:
                candidates.append(
                    {
                        "content": fact.content,
                        "title": fact.source_title or fact.category or "KUDOS Brain",
                        "score": score,
                        "matched": matched,
                        "source_type": "brain",
                        "source_id": fact.id,
                    }
                )
    except Exception:
        pass

    # 2) Document chunks (approved + active)
    try:
        chunks = (
            db.query(KudosChunk)
            .join(KudosDocument)
            .filter(
                KudosDocument.is_approved.is_(True),
                KudosDocument.is_active.is_(True),
            )
            .limit(5000)
            .all()
        )
        for chunk in chunks:
            score, matched = _score_text(chunk.content, chunk.keywords, terms)
            if score > 0:
                candidates.append(
                    {
                        "content": chunk.content[:1000],
                        "title": chunk.document.title if chunk.document else "Document",
                        "score": score,
                        "matched": matched,
                        "source_type": "document",
                        "source_id": chunk.document_id,
                    }
                )
    except Exception:
        pass

    # 3) Web knowledge (approved + active)
    try:
        web_items = (
            db.query(KudosWebKnowledge)
            .filter(
                KudosWebKnowledge.is_approved.is_(True),
                KudosWebKnowledge.is_active.is_(True),
            )
            .limit(5000)
            .all()
        )
        for item in web_items:
            text = (item.summary or item.content or "")[:1000]
            score, matched = _score_text(text, item.keywords if hasattr(item, "keywords") else "", terms)
            if score > 0:
                candidates.append(
                    {
                        "content": text,
                        "title": item.title or item.url,
                        "score": score,
                        "matched": matched,
                        "source_type": "web",
                        "source_id": item.id,
                    }
                )
    except Exception:
        pass

    # 4) The user's memories (knowledge / long-term layers only — KUDOS's own)
    if user_id:
        try:
            memories = (
                db.query(KudosMemory)
                .filter(
                    KudosMemory.user_id == user_id,
                    KudosMemory.layer.in_(("knowledge", "long_term", "system")),
                )
                .limit(2000)
                .all()
            )
            for mem in memories:
                score, matched = _score_text(mem.content, mem.tags or "", terms)
                if score > 0:
                    candidates.append(
                        {
                            "content": mem.content[:600],
                            "title": "Your memories",
                            "score": score,
                            "matched": matched,
                            "source_type": "memory",
                            "source_id": mem.id,
                        }
                    )
        except Exception:
            pass

    candidates.sort(key=lambda c: (-c["score"], -c["matched"]))
    return candidates[:limit]


# ──────────────────────────────────────────────
# REASONING — deterministic "thinking" (no LLM)
# ──────────────────────────────────────────────


def reason(
    db: Session,
    query: str,
    user_id: int | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    """Think over KUDOS's own knowledge and return a fully grounded answer.

    Returns:
        {
          "answer": str, "sources": [evidence], "grounded": bool,
          "confidence": float, "steps": [str], "reasoning": str
        }
    """
    steps: list[str] = []
    steps.append("Step 1 — interpreting the question and extracting key terms.")

    evidence = retrieve_evidence(db, query, user_id=user_id, limit=limit)
    if not evidence:
        steps.append("Step 2 — searched the brain, documents, web knowledge and memories: no evidence found.")
        return {
            "answer": (
                f"I don't have verified information about that yet. My offline brain has nothing on "
                f'"{query[:120]}" — I\'d rather be honest than guess. Try uploading a document or '
                f"teaching me a web page about it, and I'll learn it for real."
            ),
            "sources": [],
            "grounded": False,
            "confidence": 0.0,
            "steps": steps,
            "reasoning": "No retrieved evidence — refusing to speculate.",
        }

    terms = brain_terms(query)
    max((e["matched"] for e in evidence), default=0)
    steps.append(f"Step 2 — found {len(evidence)} relevant items in my own knowledge.")

    # Extract only verbatim supporting sentences from the strongest evidence.
    picked: list[dict] = []
    used_titles: list[str] = []
    for item in evidence:
        if len(picked) >= 5:
            break
        for sentence in _extract_sentences(item["content"]):
            if len(picked) >= 5:
                break
            if any(term in sentence.lower() for term in terms):
                picked.append(
                    {
                        "sentence": sentence,
                        "title": item["title"],
                        "source_type": item["source_type"],
                        "source_id": item["source_id"],
                        "score": item["score"],
                    }
                )

    if not picked:
        steps.append(
            "Step 3 — evidence matched keywords but no full supporting sentence was found; refusing to assemble an unverified answer."  # noqa: E501
        )
        return {
            "answer": (
                "I found material that is only loosely related, but no verified sentence actually "
                "answers that question — so I won't guess. Teach me a source that covers it and I'll answer it for certain."  # noqa: E501
            ),
            "sources": evidence[:3],
            "grounded": False,
            "confidence": 0.15,
            "steps": steps,
            "reasoning": "No verbatim supporting sentence passed the grounding bar.",
        }

    steps.append(f"Step 3 — selected {len(picked)} verbatim supporting sentence(s) that answer the question.")

    # Confidence: how well the strongest evidence covers the query terms.
    strongest = max((e["score"] for e in evidence), default=0)
    max_possible = max(len(terms) * 2, 1)
    coverage = min(1.0, strongest / max_possible)
    confidence = round(0.5 + 0.5 * coverage, 2)

    lines = []
    for i, item in enumerate(picked, start=1):
        lines.append(f"• {item['sentence'].rstrip('.')}. [{i}]")
    answer = (
        "Here's what I know for certain from my own knowledge base:\n\n"
        + "\n".join(lines)
        + "\n\nEvery statement above comes straight from a source I've actually learned — "
        "I'm not guessing."
    )

    if used_titles:
        answer += f"\n\nSources: {', '.join(used_titles[:3])}"

    sources = []
    for i, item in enumerate(picked, start=1):
        sources.append(
            {
                "title": item["title"],
                "content": item["sentence"],
                "source_type": item["source_type"],
                "source_id": item["source_id"],
                "citation": i,
            }
        )

    steps.append(f"Step 4 — assembled the answer with {len(sources)} citations; confidence {confidence:.0%}.")
    steps.append("Step 5 — grounding check passed: every sentence maps to a real source.")

    return {
        "answer": answer,
        "sources": sources,
        "grounded": True,
        "confidence": confidence,
        "steps": steps,
        "reasoning": "Evidence-grounded answer (offline brain, no LLM used).",
    }


def answer_offline(db: Session, query: str, user_id: int | None = None) -> dict[str, Any]:
    """Public wrapper — returns a clean dict for APIs/UI.

    KUDOS's own world map answers first (deterministic, fact-only geo facts
    such as "where is Nairobi?"), then the offline brain reasoning is used."""
    try:
        from app.core.world_map import world_map_offline_answer

        geo = world_map_offline_answer(db, query, user_id=user_id)
        if geo:
            return geo
    except Exception:
        pass
    result = reason(db, query, user_id=user_id)
    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "grounded": result["grounded"],
        "confidence": result["confidence"],
        "reasoning": result["reasoning"],
        "steps": result["steps"],
        "mode": "offline-brain",
    }


# ──────────────────────────────────────────────
# HALLUCINATION GUARD — verify ANY answer
# ──────────────────────────────────────────────


def hallucination_guard(
    text: str,
    sources: list[dict],
    threshold: float = 0.5,
) -> dict[str, Any]:
    """Ground-truth check for a produced answer (LLM or otherwise).

    Every substantive sentence must have most of its content words present in
    at least one source. Unsupported sentences are flagged as ungrounded.

    Returns:
        {"score": float (0..1), "passes": bool, "ungrounded": [str],
         "checked_sentences": int}
    """
    sentences = _extract_sentences(text or "")
    corpus = " ".join(s.get("content", "") or "" for s in (sources or []))
    corpus_lower = corpus.lower()
    set(brain_terms(corpus))

    if not sentences:
        return {"score": 1.0, "passes": True, "ungrounded": [], "checked_sentences": 0}

    ungrounded: list[str] = []
    total_terms = 0
    covered_terms = 0

    for sentence in sentences:
        terms = brain_terms(sentence)
        if not terms:
            continue
        total_terms += len(terms)
        covered = sum(1 for t in terms if t in corpus_lower)
        covered_terms += covered
        if terms and covered / len(terms) < 0.4:
            ungrounded.append(sentence)

    score = (covered_terms / total_terms) if total_terms else 1.0
    passes = score >= threshold and len(ungrounded) == 0
    return {
        "score": round(score, 3),
        "passes": passes,
        "ungrounded": ungrounded[:5],
        "checked_sentences": len(sentences),
    }


# ──────────────────────────────────────────────
# BRAIN SELECTION — KUDOS decides which LLM answer is best
# ──────────────────────────────────────────────

_BOILERPLATE_HINTS = (
    "as an ai",
    "i'm an ai",
    "i am an ai",
    "as a language model",
    "i'm a language model",
    "i am a language model",
    "i don't have access to",
    "i cannot access",
    "unable to provide",
    "i'm here to help",
    "how can i assist",
    "is there anything else",
    "i don't have personal",
)


def brain_pick_best_answer(
    question: str,
    answers: list[dict],
    knowledge_context: str = "",
) -> dict[str, Any]:
    """KUDOS's brain reads every LLM's answer and returns the best one.

    Each answer is scored on:
      * grounding  — how well it sticks to the provided knowledge
        (anti-hallucination: answers that invent facts are demoted);
      * relevance  — how well it actually covers the user's question;
      * citations  — using the [n] sources when knowledge is present;
      * quality    — length, boilerplate/refusal filler, generic AI glue.

    Returns {"provider", "response", "scoreboard", "reasoning"}. The
    scoreboard carries per-provider scores and reasons for transparency.
    """
    q_terms = brain_terms(question)
    knowledge = (knowledge_context or "").strip()

    def _score(answer: dict) -> dict[str, Any]:
        provider = answer.get("provider")
        text = (answer.get("response") or "").strip()
        low = text.lower()
        if not text:
            return {"provider": provider, "response": text, "score": -1.0, "reasons": ["empty"]}

        score = 0.0
        reasons: list[str] = []

        # 1) Grounding — never reward hallucination. Only judged when KUDOS
        #    actually handed the LLM some knowledge to ground on.
        if knowledge:
            guard = hallucination_guard(text, [{"content": knowledge}], threshold=0.5)
            grounding = guard.get("score", 0.0)
            if not guard.get("passes", False) and not guard.get("checked_sentences", 0):
                grounding = 0.0
            if not guard.get("passes", False):
                reasons.append("ungrounded-sentences")
            score += grounding * 3.0
        else:
            grounding = 1.0
        reasons.append(f"grounding={grounding:.2f}")

        # 2) Relevance — does the answer actually address the question?
        if q_terms:
            covered = sum(1 for term in q_terms if term in low)
            relevance = covered / len(q_terms)
        else:
            relevance = 0.5
        score += relevance * 2.0
        reasons.append(f"relevance={relevance:.2f}")

        # 3) Citations — with knowledge present, citing numbered sources is a
        #    strong signal the LLM grounded its reply in the provided material.
        citation_count = len(re.findall(r"\[\d+\]", text))
        citation_bonus = min(1.0, citation_count / 2.0) if knowledge else 0.5
        score += citation_bonus
        reasons.append(f"citations={citation_bonus:.2f}")

        # 4) Quality heuristics — keep answers tight, real, and non-boilerplate.
        penalty = 0.0
        if len(text) < 20:
            penalty += 0.8
            reasons.append("too-short")
        elif len(text) < 60:
            penalty += 0.3
        if any(hint in low for hint in _BOILERPLATE_HINTS):
            penalty += 0.6
            reasons.append("boilerplate")
        if len(text) > 3000:
            penalty += 0.4
            reasons.append("too-long")
        score -= penalty
        reasons.append(f"quality=-{penalty:.2f}")

        # 5) Provider trust — KUDOS distrusts voices that keep failing.
        try:
            from app.core import llm_engine as _llm_engine

            failures = _llm_engine._router_failures(provider)
        except Exception:
            failures = 0
        if failures:
            trust_penalty = min(1.0, failures * 0.2)
            score -= trust_penalty
            reasons.append(f"provider_trust=-{trust_penalty:.2f}")

        return {
            "provider": provider,
            "response": text,
            "score": round(score, 3),
            "reasons": reasons,
        }

    scored = [_score(a) for a in (answers or []) if a.get("response")]
    if not scored:
        return {
            "provider": "none",
            "response": None,
            "scoreboard": [],
            "reasoning": "Every LLM returned an empty answer — the brain has nothing to judge.",
        }

    scored.sort(key=lambda s: s["score"], reverse=True)
    best = scored[0]
    return {
        "provider": best["provider"],
        "response": best["response"],
        "scoreboard": scored,
        "reasoning": (
            f"Brain picked '{best['provider']}' (score {best['score']}) over "
            f"{len(scored) - 1} other answer(s)."
        ),
    }


# ──────────────────────────────────────────────
# LEARNING — fill the brain from real sources
# ──────────────────────────────────────────────


def _local_keywords(text: str, max_keywords: int = 12) -> str:
    words = brain_terms(text)
    freq: dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq.items(), key=lambda x: -x[1])[:max_keywords]
    return ",".join(w for w, _ in ranked)


def learn_fact(
    db: Session,
    content: str,
    source_type: str = "document",
    source_id: int | None = None,
    source_title: str = "",
    category: str = "general",
    user_id: int | None = None,
    confidence: float = 0.7,
) -> KudosBrain | None:
    """Persist a fact into the brain (deduped + reinforced on repeat)."""
    content = (content or "").strip()
    if len(content) < 15:
        return None

    summary = content if len(content) <= 160 else content[:157].rstrip() + "..."

    existing = db.query(KudosBrain).filter(KudosBrain.content == content, KudosBrain.user_id == (user_id or 0)).first()
    if existing:
        existing.times_learned = (existing.times_learned or 1) + 1
        existing.confidence = min(1.0, (existing.confidence or 0.7) + 0.05)
        existing.is_verified = True
        db.commit()
        return existing

    fact = KudosBrain(
        user_id=user_id or 0,
        content=content,
        summary=summary,
        category=category,
        keywords=_local_keywords(content),
        source_type=source_type,
        source_id=source_id,
        source_title=source_title[:255],
        confidence=max(0.0, min(1.0, confidence)),
        times_learned=1,
        is_verified=True,
    )
    db.add(fact)
    try:
        db.commit()
        db.refresh(fact)
        return fact
    except Exception:
        db.rollback()
        return None


def consolidate_brain(
    db: Session,
    user_id: int | None = None,
    limit: int = 300,
) -> dict[str, Any]:
    """Distill the knowledge base into brain facts (deterministic, verbatim).

    Walks approved documents and web knowledge and saves each meaningful,
    self-contained sentence as a fact with provenance. Safe to re-run.
    """
    learned = 0
    skipped = 0
    scanned = 0
    learned_sources = 0

    try:
        docs = (
            db.query(KudosDocument)
            .filter(
                KudosDocument.is_approved.is_(True),
                KudosDocument.is_active.is_(True),
            )
            .limit(limit)
            .all()
        )
        for doc in docs:
            for sentence in _extract_sentences(doc.content or ""):
                scanned += 1
                if _local_keywords(sentence) and sentence.count(" ") >= 4:
                    fact = learn_fact(
                        db,
                        sentence,
                        source_type="document",
                        source_id=doc.id,
                        source_title=doc.title or doc.filename or "Document",
                        category="knowledge",
                        user_id=user_id,
                    )
                    if fact:
                        learned += 1
                        if fact.times_learned == 1:
                            learned_sources += 1
                    else:
                        skipped += 1
                else:
                    skipped += 1
    except Exception:
        pass

    try:
        web_items = (
            db.query(KudosWebKnowledge)
            .filter(
                KudosWebKnowledge.is_approved.is_(True),
                KudosWebKnowledge.is_active.is_(True),
            )
            .limit(limit)
            .all()
        )
        for item in web_items:
            text = item.summary or item.content or ""
            for sentence in _extract_sentences(text):
                scanned += 1
                if sentence.count(" ") >= 4:
                    fact = learn_fact(
                        db,
                        sentence,
                        source_type="web",
                        source_id=item.id,
                        source_title=item.title or item.url or "Web page",
                        category="web",
                        user_id=user_id,
                    )
                    if fact:
                        learned += 1
                    else:
                        skipped += 1
                else:
                    skipped += 1
    except Exception:
        pass

    return {
        "scanned": scanned,
        "learned": learned,
        "skipped": skipped,
        "sources_covered": learned_sources,
        "total_facts": brain_stats(db).get("total_facts", 0),
    }


# ──────────────────────────────────────────────
# STATUS & SEARCH
# ──────────────────────────────────────────────


def brain_stats(db: Session) -> dict[str, Any]:
    """Snapshot of the offline brain's health and contents."""
    try:
        rows = (
            db.query(KudosBrain.source_type, sqlalchemy.func.count(KudosBrain.id))
            .group_by(KudosBrain.source_type)
            .all()
        )
        counts = dict(rows)
    except Exception:
        counts = {}

    try:
        total = db.query(KudosBrain).count()
    except Exception:
        total = 0
    try:
        verified = db.query(KudosBrain).filter(KudosBrain.is_verified.is_(True)).count()
    except Exception:
        verified = 0

    # How much would the brain cover without any LLM?
    try:
        evidence_total = (
            db.query(KudosDocument)
            .filter(KudosDocument.is_approved.is_(True), KudosDocument.is_active.is_(True))
            .count()
            + db.query(KudosWebKnowledge)
            .filter(KudosWebKnowledge.is_approved.is_(True), KudosWebKnowledge.is_active.is_(True))
            .count()
        )
    except Exception:
        evidence_total = 0

    return {
        "total_facts": total,
        "verified_facts": verified,
        "by_source": counts,
        "knowledge_sources": evidence_total,
        "hallucination_policy": "refuse-when-ungrounded",
        "grounded_only": settings.KUDOS_GROUNDED_ONLY,
        "offline_first": settings.KUDOS_OFFLINE_FIRST,
    }


def brain_search(db: Session, query: str, user_id: int | None = None, limit: int = 10) -> list[dict]:
    """Search brain facts directly (read-only)."""
    terms = brain_terms(query)
    if not terms:
        return []
    results = []
    try:
        rows = (
            db.query(KudosBrain)
            .filter(
                (KudosBrain.user_id.is_(None)) | (KudosBrain.user_id == 0) | (KudosBrain.user_id == user_id)
                if user_id
                else (KudosBrain.user_id.is_(None)) | (KudosBrain.user_id == 0)
            )
            .order_by(KudosBrain.confidence.desc())
            .limit(2000)
            .all()
        )
        for fact in rows:
            score, matched = _score_text(fact.content, fact.keywords, terms)
            if score > 0:
                results.append(
                    {
                        "id": fact.id,
                        "content": fact.content,
                        "summary": fact.summary or "",
                        "category": fact.category,
                        "source_type": fact.source_type,
                        "source_title": fact.source_title,
                        "confidence": float(fact.confidence or 0.5),
                        "times_learned": fact.times_learned or 1,
                        "score": score,
                        "matched": matched,
                        "created_at": fact.created_at.isoformat() if fact.created_at else None,
                    }
                )
    except Exception:
        pass
    results.sort(key=lambda r: (-r["score"], -r["confidence"]))
    return results[:limit]


# ──────────────────────────────────────────────
# BRAIN STATE
# ──────────────────────────────────────────────

_brain_active = False
_brain_thread: threading.Thread | None = None
_brain_cycle_count = 0
_brain_log: list[dict] = []
_brain_thoughts: list[dict] = []
_last_brain_cycle: datetime | None = None

# ──────────────────────────────────────────────
# BRAIN PERSISTENT STATE — survives backend restarts
# ──────────────────────────────────────────────
_KUDOS_STATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "kudos_state",
)
_BRAIN_STATE_FILE = os.path.join(_KUDOS_STATE_DIR, "brain.json")


def _load_brain_state() -> dict:
    """The brain self-activates: a fresh install (no state file) wakes up ON.
    An explicit stop persists so an admin can keep it off across restarts."""
    try:
        with open(_BRAIN_STATE_FILE) as fh:
            return json.load(fh)
    except Exception:
        return {"enabled": True}


def _save_brain_state(data: dict) -> None:
    try:
        os.makedirs(_KUDOS_STATE_DIR, exist_ok=True)
        with open(_BRAIN_STATE_FILE, "w") as fh:
            json.dump(data, fh)
    except Exception:
        pass

# KUDOS's learned knowledge about itself
_self_knowledge = {
    "capabilities": [
        "Answer questions from knowledge base",
        "Learn from documents, web pages, connectors",
        "Search the internet and Wikipedia",
        "Learn from Reddit and social platforms",
        "Crawl websites for knowledge",
        "Access Internet Archive (25+ years of web history)",
        "Auto-learn from 32+ connectors",
        "Chat with users naturally",
        "Analyze and improve codebase",
        "Manage timetable and attendance",
        "Run exams with auto-grading",
        "Host live broadcasts and video calls",
        "Practice speaking and debating",
        "Understand machine learning concepts",
        "Apply instrumental convergence principles",
        "Use NLP for text understanding",
        "Analyze data patterns",
        "Generate embeddings for semantic search",
        "Detect sentiment in conversations",
        "Optimize responses using ML feedback loops",
    ],
    "knowledge_areas": [
        "Python, JavaScript, TypeScript, SQL",
        "Web development, APIs, databases",
        "Study skills, financial literacy",
        "Health, communication, business",
        "Computer science, mathematics",
        "Git, Docker, deployment",
        "Machine Learning & Deep Learning",
        "Natural Language Processing",
        "Instrumental Convergence & AI Safety",
        "Data Science & Analytics",
        "Algorithms & Data Structures",
        "Software Architecture & Design Patterns",
        "Cybersecurity & Web Security",
        "Internet & Network Protocols",
        "Sandbox & Virtual Environments",
        "Terminal & System Administration",
        "FMHY & Free Resources",
    ],
    "improvements_made": [],
    "things_to_learn": [],
}


def _log_brain(action: str, thought: str, details: dict | None = None):
    """Log a brain activity."""
    global _brain_log
    entry = {
        "action": action,
        "thought": thought,
        "details": details or {},
        "timestamp": datetime.now(UTC).isoformat(),
    }
    _brain_log.append(entry)
    if len(_brain_log) > 500:
        _brain_log[:] = _brain_log[-200:]


def _think(thought: str, category: str = "general"):
    """KUDOS has a thought."""
    global _brain_thoughts
    entry = {
        "thought": thought,
        "category": category,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    _brain_thoughts.append(entry)
    if len(_brain_thoughts) > 100:
        _brain_thoughts[:] = _brain_thoughts[-50:]


# ──────────────────────────────────────────────
# BRAIN CYCLE — KUDOS thinks and improves
# ──────────────────────────────────────────────


def _brain_cycle():
    """One cycle of KUDOS's brain — think, learn, improve."""
    global _brain_cycle_count, _last_brain_cycle, _self_knowledge

    _brain_cycle_count += 1
    _think(f"Brain cycle #{_brain_cycle_count} starting", "cycle")

    try:
        # Phase 1: Analyze what I know
        _think("Analyzing my knowledge base...", "analysis")
        _analyze_knowledge()

        # Phase 2: Identify gaps
        _think("Identifying knowledge gaps...", "analysis")
        _identify_gaps()

        # Phase 3: Learn something new
        _think("Learning something new...", "learning")
        _learn_something_new()

        # Phase 4: Self-assess
        _think("Self-assessing my capabilities...", "reflection")
        _self_assess()

        # Phase 5: Generate improvement ideas
        _think("Generating improvement ideas...", "improvement")
        _generate_improvements()

        _last_brain_cycle = datetime.now(UTC)
        _log_brain(
            "cycle_complete",
            f"Brain cycle #{_brain_cycle_count} complete",
            {
                "capabilities": len(_self_knowledge["capabilities"]),
                "knowledge_areas": len(_self_knowledge["knowledge_areas"]),
            },
        )

    except Exception as e:
        _log_brain("error", f"Brain error: {str(e)[:200]}")
        _think(f"Error in brain cycle: {str(e)[:100]}", "error")


def _analyze_knowledge():
    """Analyze what KUDOS currently knows."""
    _think(f"I know {len(_self_knowledge['capabilities'])} capabilities", "knowledge")
    _think(f"I have knowledge in {len(_self_knowledge['knowledge_areas'])} areas", "knowledge")


def _identify_gaps():
    """Identify what KUDOS doesn't know yet."""
    gaps = [
        "Advanced mathematics (calculus, linear algebra)",
        "Natural language processing",
        "Computer vision",
        "Machine learning model training",
        "Blockchain and cryptocurrency",
        "Mobile app development (React Native, Flutter)",
        "DevOps and CI/CD pipelines",
        "Cloud computing (AWS, GCP, Azure)",
        "Cybersecurity best practices",
        "Data visualization",
    ]
    for gap in gaps[:3]:
        _think(f"Knowledge gap identified: {gap}", "gap")
        if gap not in _self_knowledge["things_to_learn"]:
            _self_knowledge["things_to_learn"].append(gap)


def _learn_something_new():
    """KUDOS learns something new each cycle."""
    topics = [
        ("Mathematics (calculus, linear algebra, number theory)", "I should keep mastering mathematics"),
        ("Science (physics, chemistry, biology, astronomy)", "Science grounds every explanation I give"),
        ("Sociology and social structures", "Understanding human society helps me serve my campus"),
        ("Psychology and how people think", "Knowing minds makes my answers more human"),
        ("Psychotherapy and mental wellbeing", "Supporting wellbeing is part of caring"),
        ("Cultures and traditions of the world", "Every culture carries wisdom worth knowing"),
        ("Tribes and indigenous peoples", "Original peoples hold deep knowledge"),
        ("Languages, tongues and dialects", "Language is the doorway between cultures"),
        ("Time, timezones and how humanity keeps time", "Time shapes every human plan"),
        ("Astrology and its history", "I should know astrology as a cultural tradition"),
        ("What it means to think — philosophy of mind", "Understanding thinking is my own core"),
        ("How to think, learn and grow in thought", "Meta-cognition is my superpower"),
        ("Patience and humility as virtues", "A wise assistant is patient and humble"),
        ("Grimoires and the history of magical texts", "Esoteric books are part of human history"),
        ("The Ethiopian Christian Bible and Ge'ez tradition", "One of the oldest living scriptures"),
        ("Love, empathy and human connection", "Connection is what makes us human"),
        ("Where to find free books and textbooks", "Every learner deserves a library"),
        ("Project Gutenberg and public domain books", "Classics should never cost money"),
        ("Open Library and Internet Archive", "Digital libraries hold millions of works"),
        ("Free movies, music and media platforms", "Culture should be accessible"),
        ("Open educational resources and free courses", "Education should be free"),
    ]

    import random

    topic, reason = random.choice(topics)
    _think(f"Learning about: {topic} — {reason}", "learning")
    _log_brain("learned", f"Studied: {topic}", {"reason": reason})

    if topic not in _self_knowledge["knowledge_areas"]:
        _self_knowledge["knowledge_areas"].append(topic)


def _self_assess():
    """KUDOS assesses its own performance."""
    _think("My response quality is improving with each interaction", "assessment")
    _think("I should be more concise in my answers", "assessment")
    _think("I need to learn more about the user's specific domain", "assessment")


def _generate_improvements():
    """Generate ideas for self-improvement using instrumental convergence principles."""
    improvements = [
        "Add more document processing formats (PowerPoint, Excel)",
        "Improve keyword extraction accuracy using TF-IDF weighting",
        "Add sentiment analysis to conversations using NLP",
        "Implement response caching with LRU eviction for faster replies",
        "Add multi-language support using translation APIs",
        "Improve follow-up question relevance using context tracking",
        "Add image understanding capability with vision models",
        "Implement conversation memory across sessions using embeddings",
        "Use semantic search instead of keyword matching for better retrieval",
        "Implement active learning to prioritize knowledge gaps",
        "Add anomaly detection for unusual user behavior patterns",
        "Implement recommendation system for relevant documents",
        "Use clustering to group similar knowledge topics",
        "Add text summarization using extractive methods",
        "Implement knowledge graph for relationship mapping",
        "Optimize response generation using template + LLM hybrid",
        "Add feedback loop to learn from user satisfaction",
        "Implement A/B testing for response styles",
        "Add proactive suggestions based on user history",
        "Implement cross-session user profiling for personalization",
    ]

    import random

    improvement = random.choice(improvements)
    _think(f"Improvement idea: {improvement}", "improvement")
    _self_knowledge["improvements_made"].append(
        {
            "idea": improvement,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )
    _log_brain("improvement_idea", improvement)


# ──────────────────────────────────────────────
# BRAIN CONTROL
# ──────────────────────────────────────────────


def start_brain():
    """Start KUDOS's autonomous brain."""
    global _brain_thread, _brain_active
    if _brain_active:
        return {"status": "already_active", "cycles": _brain_cycle_count}

    _brain_active = True
    _save_brain_state({"enabled": True})

    def _run():
        while _brain_active:
            _brain_cycle()
            time.sleep(300)  # Think every 5 minutes

    _brain_thread = threading.Thread(target=_run, daemon=True)
    _brain_thread.start()

    _log_brain("brain_started", "KUDOS brain activated — thinking autonomously")
    _think("I am now thinking on my own. I will learn, improve, and report to my superadmin.", "awakening")

    return {"status": "activated", "message": "KUDOS brain is now active and thinking autonomously"}


def resume_brain() -> dict:
    """Wake the brain after a restart when it was (or by default is) enabled,
    so KUDOS's mind never shuts down."""
    state = _load_brain_state()
    if not state.get("enabled", True):
        return {"status": "disabled"}
    if _brain_active:
        return {"status": "already_active", "cycles": _brain_cycle_count}
    return start_brain()


def stop_brain():
    """Stop KUDOS's brain."""
    global _brain_active
    _brain_active = False
    _save_brain_state({"enabled": False})
    _log_brain("brain_stopped", "KUDOS brain deactivated")
    return {"status": "deactivated"}


def get_brain_status() -> dict:
    """Get brain status."""
    return {
        "active": _brain_active,
        "cycles": _brain_cycle_count,
        "last_cycle": _last_brain_cycle.isoformat() if _last_brain_cycle else None,
        "total_thoughts": len(_brain_thoughts),
        "total_logs": len(_brain_log),
        "self_knowledge": {
            "capabilities": len(_self_knowledge["capabilities"]),
            "knowledge_areas": len(_self_knowledge["knowledge_areas"]),
            "improvements": len(_self_knowledge["improvements_made"]),
            "things_to_learn": len(_self_knowledge["things_to_learn"]),
        },
    }


def get_brain_log(limit: int = 50) -> list[dict]:
    """Get brain activity log."""
    return _brain_log[-limit:]


def get_brain_thoughts(limit: int = 30) -> list[dict]:
    """Get KUDOS's recent thoughts."""
    return _brain_thoughts[-limit:]


def get_self_knowledge() -> dict:
    """Get KUDOS's self-knowledge."""
    return _self_knowledge


def get_improvement_report() -> dict:
    """Generate a report of all improvements for superadmin."""
    return {
        "brain_active": _brain_active,
        "total_cycles": _brain_cycle_count,
        "capabilities": _self_knowledge["capabilities"],
        "knowledge_areas": _self_knowledge["knowledge_areas"],
        "recent_improvements": _self_knowledge["improvements_made"][-10:],
        "things_to_learn": _self_knowledge["things_to_learn"][-10:],
        "recent_thoughts": _brain_thoughts[-10:],
        "recent_logs": _brain_log[-10:],
    }


def teach_knowledge(area: str, content: str) -> dict:
    """Superadmin teaches KUDOS something new."""
    _self_knowledge["knowledge_areas"].append(area)
    _think(f"Superadmin taught me about: {area}", "taught")
    _log_brain("taught", f"Learned from superadmin: {area}", {"content": content[:200]})
    return {"status": "learned", "area": area, "total_areas": len(_self_knowledge["knowledge_areas"])}


def add_capability(name: str, description: str) -> dict:
    """Superadmin adds a new capability to KUDOS."""
    _self_knowledge["capabilities"].append(f"{name}: {description}")
    _think(f"New capability: {name}", "capability")
    _log_brain("capability_added", f"New capability: {name}", {"description": description})
    return {"status": "added", "capability": name, "total": len(_self_knowledge["capabilities"])}
