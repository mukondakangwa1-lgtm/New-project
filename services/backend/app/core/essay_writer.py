"""
Digital Campus - KUDOS Essay Writer

When a user asks for a long or "unlimited pages" essay, KUDOS writes up to 50
pages (MAX_PAGES), section by section, grounding each section in the retrieved
knowledge. If the LLM cannot reach the requested length, KUDOS exhausts all the
information it has on the topic and clearly says so.

A page is treated as ~WORDS_PER_PAGE words of prose.
"""
import asyncio

from app.core.llm_engine import query_best_llm
from app.core.privacy_guard import scrub_response

MAX_PAGES = 50
WORDS_PER_PAGE = 400
_MAX_SECTIONS = 50
_LLM_TIMEOUT = 150

_SYSTEM = (
    "You are KUDOS, a brilliant academic writer for Digital Campus. You write "
    "clear, well-structured, accurate prose in the user's requested language. "
    "You never invent facts: if the knowledge provided does not cover something, "
    "you say so. You protect user privacy and never include personal information "
    "about anyone other than the reader. Write flowing paragraphs (no bullet "
    "lists unless truly needed)."
)

_HEADING_PROMPT = (
    "You are KUDOS, outlining a {pages}-page essay titled \"{topic}\".\n"
    "KNOWLEDGE AVAILABLE:\n{knowledge}\n\n"
    "Create a section outline (title + one-line scope) for the essay. Aim for "
    "about {count} sections. Output strictly as:\n"
    "1. Section title::one-line scope\n2. Section title::one-line scope\n...\n"
    "Do not include any other text."
)

_SECTION_PROMPT = (
    "Write section #{idx} of {count} of an essay on \"{topic}\".\n"
    "SECTION TITLE: {title}\n"
    "SCOPE: {scope}\n"
    "TARGET LENGTH: approximately {target_words} words of flowing prose.\n"
    "KNOWLEDGE AVAILABLE (cite inline as [n] when you use a source):\n{knowledge}\n\n"
    "Write only the section body — no title, no intro such as \"In this section\", "
    "no closing remarks about the essay."
)


def _truncate_knowledge(knowledge: str, limit: int = 12000) -> str:
    return knowledge[:limit]


def estimate_pages(words: int) -> int:
    return max(1, round(words / WORDS_PER_PAGE))


async def _llm(prompt: str, system: str) -> str:
    try:
        result = await asyncio.wait_for(query_best_llm(prompt, system), timeout=_LLM_TIMEOUT)
        return (result.get("response") or "").strip()
    except Exception:
        return ""


async def _build_outline(topic: str, pages: int, knowledge: str) -> list[tuple[str, str]]:
    count = min(_MAX_SECTIONS, max(3, pages))
    prompt = _HEADING_PROMPT.format(pages=pages, topic=topic, knowledge=_truncate_knowledge(knowledge), count=count)
    raw = await _llm(prompt, _SYSTEM)
    outline: list[tuple[str, str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line[0].isdigit() is False:
            continue
        m = line.split("::", 1)
        if len(m) == 2:
            outline.append((m[0].strip(), m[1].strip()))
        elif ":" in line:
            title, _, scope = line.partition(":")
            outline.append((title.strip().lstrip("0123456789. "), scope.strip()))
    return outline[:count]


async def write_essay(topic: str, pages: int, knowledge: str = "") -> dict:
    """Write the essay. Returns {essay, sections, page_count, target_pages,
    exhausted}."""
    pages = max(1, min(int(pages or 1), MAX_PAGES))
    target_words_total = pages * WORDS_PER_PAGE

    outline = await _build_outline(topic, pages, knowledge)
    if not outline:
        # No LLM available — fall back to everything KUDOS knows about the topic.
        fallback = _fallback_essay(topic, knowledge)
        return {
            "essay": fallback["essay"],
            "sections": fallback["sections"],
            "page_count": fallback["page_count"],
            "target_pages": pages,
            "exhausted": True,
            "generated_by": "knowledge",
        }

    sections: list[dict] = []
    total_words = 0
    for idx, (title, scope) in enumerate(outline, start=1):
        target_words = max(120, min(1200, round(target_words_total / len(outline))))
        prompt = _SECTION_PROMPT.format(
            idx=idx, count=len(outline), topic=topic, title=title, scope=scope,
            target_words=target_words, knowledge=_truncate_knowledge(knowledge),
        )
        body = await _llm(prompt, _SYSTEM)
        if not body or len(body) < 60:
            body = _section_fallback(topic, title, scope, knowledge)
        body = scrub_response(body, allow_emails=True).strip()
        sections.append({"title": title, "body": body})
        total_words += len(body.split())

    # If even the full outline under-delivers, exhaust remaining knowledge.
    exhausted = total_words < target_words_total * 0.6 and pages > 1
    if exhausted:
        extra = _exhaust_info(topic, knowledge, sections, target_words_total - total_words)
        if extra:
            sections.append({"title": "Additional notes from everything KUDOS knows", "body": extra})
            total_words += len(extra.split())

    essay_parts = [f"# {topic}\n"]
    for s in sections:
        essay_parts.append(f"\n## {s['title']}\n\n{s['body']}\n")
    essay = "\n".join(essay_parts).strip()

    return {
        "essay": essay,
        "sections": sections,
        "page_count": estimate_pages(total_words),
        "target_pages": pages,
        "word_count": total_words,
        "exhausted": exhausted,
        "generated_by": "llm",
    }


async def _exhaust_info(topic: str, knowledge: str, sections: list[dict], remaining_words: int) -> str:
    if not knowledge:
        return ""
    prompt = (
        f"You are completing an essay on \"{topic}\". Below is the remaining "
        "knowledge KUDOS has on the topic. Write as much additional flowing prose "
        f"as possible (up to ~{remaining_words} words) that was not already covered, "
        "covering every remaining source.\n\nKNOWLEDGE:\n" + _truncate_knowledge(knowledge, 14000)
    )
    extra = await _llm(prompt, _SYSTEM)
    return scrub_response(extra, allow_emails=True).strip() if extra else ""


def _section_fallback(topic: str, title: str, scope: str, knowledge: str) -> str:
    """No-LLM fallback: hand back the matching knowledge, summarized."""
    k = knowledge or ""
    lines = [l for l in k.splitlines() if l.strip()]
    matched = [l.strip() for l in lines if any(w in l.lower() for w in title.lower().split()[:4])][:6]
    body = "\n".join(f"- {m[:500]}" for m in matched) if matched else "\n".join(f"- {l[:500]}" for l in lines[:8])
    return f"Regarding \"{scope}\":\n\n{body}\n\nNote: the full essay engine needs an LLM key to write longer prose. Here is the knowledge KUDOS holds on this part of the topic."


def _fallback_essay(topic: str, knowledge: str) -> dict:
    """Fallback when no LLM is reachable: hand over all available knowledge."""
    k = knowledge or f"No knowledge found on \"{topic}\" yet. Upload a document or teach KUDOS a web page about it."
    lines = [l.strip() for l in k.splitlines() if l.strip()][:120]
    essay = f"# {topic}\n\nEverything KUDOS knows about this topic:\n\n" + "\n".join(f"- {l[:600]}" for l in lines)
    sections = [{"title": f"Everything KUDOS knows about {topic}", "body": "\n".join(f"- {l[:600]}" for l in lines)}]
    words = len(essay.split())
    return {"essay": essay, "sections": sections, "page_count": estimate_pages(words), "target_pages": None, "word_count": words, "exhausted": True, "generated_by": "knowledge"}
