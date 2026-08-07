"""
KUDOS Arena Engine — Multi-AI Orchestration
Queries multiple AI sources IN PARALLEL for speed.
"""
import asyncio
import json
import re
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Optional

import httpx

# ──────────────────────────────────────────────
# RESPONSE CACHE (LRU) for speed
# ──────────────────────────────────────────────

_RESPONSE_CACHE_MAX = 200
_response_cache: OrderedDict = OrderedDict()
CACHE_TTL = 300  # 5 minutes


def _get_cached_response(query: str, mode: str) -> Optional[dict]:
    key = f"{mode}:{query.lower().strip()}"
    if key in _response_cache:
        entry = _response_cache[key]
        if (datetime.now(timezone.utc) - entry["time"]).total_seconds() < CACHE_TTL:
            _response_cache.move_to_end(key)
            return entry["data"]
        else:
            del _response_cache[key]
    return None


def _set_cached_response(query: str, mode: str, data: dict):
    key = f"{mode}:{query.lower().strip()}"
    _response_cache[key] = {"data": data, "time": datetime.now(timezone.utc)}
    while len(_response_cache) > _RESPONSE_CACHE_MAX:
        _response_cache.popitem(last=False)


# ──────────────────────────────────────────────
# ARENA AI MODES
# ──────────────────────────────────────────────

ARENA_MODES = {
    "battlemode": {
        "name": "Battle Mode",
        "description": "Multiple AIs compete to answer — best answer wins",
        "icon": "⚔️",
        "sources": ["knowledge_base", "cached", "documents", "connectors", "mcp", "llm"],
    },
    "agent": {
        "name": "Agent Mode",
        "description": "AI agent with tools — searches, reads, reasons",
        "icon": "🤖",
        "sources": ["knowledge_base", "cached", "documents", "web_search", "mcp", "llm"],
    },
    "sidebyside": {
        "name": "Side by Side",
        "description": "Compare answers from multiple sources side by side",
        "icon": "📊",
        "sources": ["knowledge_base", "cached", "web_search", "wikipedia", "mcp", "llm"],
    },
    "directchat": {
        "name": "Direct Chat",
        "description": "Direct conversation with KUDOS's full knowledge",
        "icon": "💬",
        "sources": ["knowledge_base", "cached", "mcp", "llm"],
    },
}

# Timeout per source in seconds
SOURCE_TIMEOUT = 5


# ──────────────────────────────────────────────
# ANSWER EVALUATOR
# ──────────────────────────────────────────────

def score_answer(query: str, answer: str, source: str) -> float:
    """
    Score an answer based on relevance, completeness, and quality.
    Returns 0.0 to 1.0.
    """
    if not answer or len(answer) < 20:
        return 0.0

    score = 0.0
    query_words = set(re.findall(r"[a-zA-Z]{3,}", query.lower()))
    answer_lower = answer.lower()

    # 1. Relevance: how many query words appear in answer
    matches = sum(1 for w in query_words if w in answer_lower)
    relevance = matches / len(query_words) if query_words else 0
    score += relevance * 0.4

    # 2. Completeness: longer, more detailed answers score higher
    word_count = len(answer.split())
    if word_count > 200:
        score += 0.2
    elif word_count > 100:
        score += 0.15
    elif word_count > 50:
        score += 0.1

    # 3. Structure: organized answers score higher
    if any(marker in answer for marker in ["**", "##", "-", "1.", "2.", "•"]):
        score += 0.1

    # 4. Source quality
    source_scores = {
        "knowledge_base": 0.8,
        "wikipedia": 0.9,
        "web_search": 0.7,
        "documents": 0.85,
        "llm": 0.95,
        "mcp": 0.9,
        "cached": 0.6,
    }
    score += source_scores.get(source, 0.5) * 0.2

    # 5. Freshness indicator (newer knowledge preferred slightly)
    if "[Search:" in answer or "[Wikipedia]" in answer:
        score += 0.05

    return min(score, 1.0)


def select_best_answer(query: str, answers: list[dict]) -> dict:
    """
    Select the best answer from multiple AI sources.
    Each answer: {source: str, content: str, metadata: dict}
    """
    if not answers:
        return {
            "answer": "I couldn't find an answer from any source.",
            "source": "none",
            "score": 0,
            "alternatives": [],
        }

    if len(answers) == 1:
        return {
            "answer": answers[0]["content"],
            "source": answers[0]["source"],
            "score": score_answer(query, answers[0]["content"], answers[0]["source"]),
            "alternatives": [],
        }

    # Score all answers
    scored = []
    for a in answers:
        s = score_answer(query, a["content"], a["source"])
        scored.append({**a, "score": s})

    # Sort by score
    scored.sort(key=lambda x: -x["score"])

    best = scored[0]
    alternatives = scored[1:]

    # Synthesize: if top answers are close, combine insights
    if len(scored) >= 2 and scored[1]["score"] > scored[0]["score"] * 0.8:
        # Close scores — synthesize
        synthesized = _synthesize_answers(query, scored[:3])
        return {
            "answer": synthesized,
            "source": "synthesized",
            "score": best["score"],
            "alternatives": [
                {"source": a["source"], "score": round(a["score"], 2), "preview": a["content"][:150]}
                for a in alternatives[:2]
            ],
        }

    return {
        "answer": best["content"],
        "source": best["source"],
        "score": round(best["score"], 2),
        "alternatives": [
            {"source": a["source"], "score": round(a["score"], 2), "preview": a["content"][:150]}
            for a in alternatives[:2]
        ],
    }


def _synthesize_answers(query: str, answers: list[dict]) -> str:
    """
    Combine insights from multiple high-scoring answers into one superior answer.
    """
    parts = [f"Here's a comprehensive answer about \"{query}\":\n\n"]

    # Use the best answer as the base
    base = answers[0]["content"]
    parts.append(base)

    # Add unique insights from other answers
    base_words = set(re.findall(r"[a-zA-Z]{4,}", base.lower()))

    for alt in answers[1:]:
        # Find sentences in alt that add new information
        sentences = re.split(r"[.!?]+", alt["content"])
        new_insights = []
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 30:
                continue
            sent_words = set(re.findall(r"[a-zA-Z]{4,}", sent.lower()))
            # If this sentence has significant new words
            new_words = sent_words - base_words
            if len(new_words) > 2:
                new_insights.append(sent)
                base_words.update(sent_words)

        if new_insights:
            parts.append(f"\n\nAdditionally: {'. '.join(new_insights[:2])}.")

    return "".join(parts)


# ──────────────────────────────────────────────
# MULTI-SOURCE QUERY ENGINE — PARALLEL
# ──────────────────────────────────────────────

_SOURCE_FUNCS = {
    "knowledge_base": "_query_knowledge_base",
    "web_search": "_query_web_search",
    "wikipedia": "_query_wikipedia",
    "cached": "_query_cache",
    "documents": "_query_documents",
    "connectors": "_query_connectors",
}


async def query_multiple_sources(
    query: str,
    mode: str,
    db_session=None,
    user_id: int = 0,
) -> list[dict]:
    """
    Query multiple AI sources IN PARALLEL based on Arena mode.
    Uses asyncio.gather with timeouts for speed.
    """
    # Check cache first
    cached = _get_cached_response(query, mode)
    if cached is not None:
        return cached

    mode_config = ARENA_MODES.get(mode, ARENA_MODES["battlemode"])
    sources = mode_config["sources"]

    # Build tasks for parallel execution
    async def _query_source(source: str) -> Optional[dict]:
        try:
            if source == "knowledge_base" and db_session:
                answer = await asyncio.wait_for(_query_knowledge_base(query, db_session), timeout=SOURCE_TIMEOUT)
            elif source == "web_search":
                answer = await asyncio.wait_for(_query_web_search(query), timeout=SOURCE_TIMEOUT)
            elif source == "wikipedia":
                answer = await asyncio.wait_for(_query_wikipedia(query), timeout=SOURCE_TIMEOUT)
            elif source == "cached" and db_session:
                answer = await asyncio.wait_for(asyncio.to_thread(_query_cache, query, db_session), timeout=SOURCE_TIMEOUT)
            elif source == "documents" and db_session:
                answer = await asyncio.wait_for(asyncio.to_thread(_query_documents, query, db_session), timeout=SOURCE_TIMEOUT)
            elif source == "connectors" and db_session:
                answer = await asyncio.wait_for(asyncio.to_thread(_query_connectors, query, db_session), timeout=SOURCE_TIMEOUT)
            elif source == "mcp":
                from app.core.mcp_client import search_mcp_sources
                mcp_results = await asyncio.wait_for(
                    search_mcp_sources(query, limit=3), timeout=SOURCE_TIMEOUT * 2
                )
                answer = "\n\n".join(
                    item.get("content", "")[:600]
                    for item in mcp_results
                    if item.get("content")
                )
            else:
                return None

            if answer and len(answer) > 20:
                return {"source": source, "content": answer, "metadata": {"type": source}}
        except (asyncio.TimeoutError, Exception):
            return None
        return None

    # Run retrieval and web sources in parallel first.
    retrieval_sources = [source for source in sources if source != "llm"]
    tasks = [_query_source(source) for source in retrieval_sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    answers = [r for r in results if isinstance(r, dict) and r.get("content")]

    # Give the configured LLM the retrieved context, then let Arena compare
    # the generated answer with the raw source answers. This keeps the LLM
    # optional: without a provider, keyword/web retrieval still works.
    if "llm" in sources:
        try:
            from app.core.llm_engine import get_llm_response

            knowledge_context = "\n\n".join(
                answer["content"][:1200] for answer in answers[:5]
            )
            llm_answer = await asyncio.wait_for(
                get_llm_response(query, knowledge_context=knowledge_context),
                timeout=SOURCE_TIMEOUT * 2,
            )
            if llm_answer and len(llm_answer) > 20:
                answers.append({
                    "source": "llm",
                    "content": llm_answer,
                    "metadata": {"type": "llm", "context_sources": len(answers)},
                })
        except (asyncio.TimeoutError, Exception):
            pass

    # Cache the results
    _set_cached_response(query, mode, answers)

    return answers


async def _query_knowledge_base(query: str, db) -> Optional[str]:
    """Query KUDOS's internal knowledge base."""
    from app.api.v1.endpoints.kudos import search_chunks
    sources = search_chunks(db, query, limit=3)
    if not sources:
        return None
    return "\n\n".join(s["content"][:300] for s in sources[:3])


async def _query_web_search(query: str) -> Optional[str]:
    """Search DuckDuckGo for answers."""
    try:
        async with httpx.AsyncClient(timeout=4, follow_redirects=True) as client:
            res = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (compatible; KUDOS/1.0)"},
            )
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(res.text, "html.parser")
            snippets = soup.find_all("a", class_="result__snippet")
            if snippets:
                return " ".join(s.get_text(strip=True) for s in snippets[:3] if s.get_text(strip=True))
            links = soup.find_all("a", class_="result__a")
            if links:
                return " ".join(l.get_text(strip=True) for l in links[:5] if l.get_text(strip=True))
    except Exception:
        pass
    return None


async def _query_wikipedia(query: str) -> Optional[str]:
    """Query Wikipedia for answers."""
    try:
        async with httpx.AsyncClient(timeout=4, follow_redirects=True) as client:
            res = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={"action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": 1},
            )
            data = res.json()
            results = data.get("query", {}).get("search", [])
            if results:
                title = results[0]["title"]
                article = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={"action": "query", "titles": title, "prop": "extracts", "exintro": True, "explaintext": True, "format": "json"},
                )
                pages = article.json().get("query", {}).get("pages", {})
                for _, page in pages.items():
                    extract = page.get("extract", "")
                    if len(extract) > 50:
                        return extract[:1500]
    except Exception:
        pass
    return None


def _query_cache(query: str, db) -> Optional[str]:
    try:
        from app.models import KudosWebKnowledge
        items = db.query(KudosWebKnowledge).filter(KudosWebKnowledge.is_approved == True, KudosWebKnowledge.is_active == True).all()
        query_words = set(re.findall(r"[a-zA-Z]{3,}", query.lower()))
        best_score = 0
        best_content = None
        for item in items:
            content_lower = (item.content or "").lower()
            score = sum(1 for w in query_words if w in content_lower)
            if score > best_score:
                best_score = score
                best_content = (item.summary or item.content[:1000])
        return best_content if best_score > 0 else None
    except Exception:
        return None


def _query_documents(query: str, db) -> Optional[str]:
    try:
        from app.models import KudosChunk, KudosDocument
        chunks = db.query(KudosChunk).join(KudosDocument).filter(KudosDocument.is_approved == True, KudosDocument.is_active == True).all()
        query_words = set(re.findall(r"[a-zA-Z]{3,}", query.lower()))
        scored = []
        for chunk in chunks:
            content_lower = chunk.content.lower()
            keywords = set(chunk.keywords.split(",")) if chunk.keywords else set()
            score = sum(3 if w in keywords else 1 for w in query_words if w in content_lower)
            if score > 0:
                scored.append((score, chunk.content))
        scored.sort(key=lambda x: -x[0])
        if scored:
            return "\n\n".join(c[:400] for _, c in scored[:2])
        return None
    except Exception:
        return None


def _query_connectors(query: str, db) -> Optional[str]:
    try:
        from app.models import KudosWebKnowledge
        items = db.query(KudosWebKnowledge).filter(
            KudosWebKnowledge.is_approved == True, KudosWebKnowledge.is_active == True, KudosWebKnowledge.title.contains("]")
        ).all()
        query_words = set(re.findall(r"[a-zA-Z]{3,}", query.lower()))
        scored = []
        for item in items:
            combined = (item.title + " " + (item.summary or "")).lower()
            score = sum(1 for w in query_words if w in combined)
            if score > 0:
                scored.append((score, item.summary or item.content[:500]))
        scored.sort(key=lambda x: -x[0])
        if scored:
            return "\n\n".join(c[:300] for _, c in scored[:2])
        return None
    except Exception:
        return None


def get_arena_modes() -> dict:
    """Return available Arena AI modes."""
    return ARENA_MODES
