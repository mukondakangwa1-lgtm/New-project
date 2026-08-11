"""
Digital Campus - KUDOS Quick Answers & Summarization

KUDOS gives short, friendly answers to short, casual, non-deep questions
instead of running the heavy retrieval pipeline every time. It also summarizes
long text so users can get the gist fast.

Two strategies, in order:
  1. Canned replies for pure small-talk / greetings.
  2. A concise LLM call (brevity-instructed) for short-but-real questions.
  3. Extractive fallback if no LLM is configured or reachable.
"""

import heapq
import re

from app.core.llm_engine import query_best_llm

_DEEP_HINTS = [
    "explain",
    "how do i",
    "how to",
    "why is",
    "why do",
    "what is the difference",
    "compare",
    "write an essay",
    "essay",
    "essay about",
    "detailed",
    "in depth",
    "analyze",
    "analyze",
    "summarize",
    "summarise",
    "research",
    "report on",
    "describe",
    "steps to",
    "guide me",
    "tutorial",
    "outline",
    "long",
    "50 pages",
    "full",
    "everything you know",
    "teach me",
    "learn about",
    "advantages and",
    "pros and cons",
    "formula",
    "equation",
    "code",
    "program",
    "fix",
    "debug",
    "why didn't",
    "what happens if",
]

# Questions that KUDOS can answer instantly without an LLM at all.
_CANNED = [
    (
        re.compile(r"^(hi|hey|hello|yo|howdy|sup|good (morning|afternoon|evening))\b.*$", re.IGNORECASE),
        "Hey there! 👋 I'm KUDOS — ask me about courses, assignments, campus life, "
        "or anything you're curious about. What's on your mind?",
    ),
    (
        re.compile(
            r"^(how are you|how r u|how do you do|whats up|what's up|wassup|hows it going|how's it going)\b.*$",
            re.IGNORECASE,
        ),
        "I'm doing great, thanks for asking! 🧠 Always learning, always curious. What can I help you with today?",
    ),
    (
        re.compile(r"^(who are you|what are you|tell me about yourself|what is kudos)\b.*$", re.IGNORECASE),
        "I'm KUDOS — Digital Campus' friendly AI assistant. I learn from documents, "
        "web pages, and conversations, remember things you tell me, and can even "
        "write essays, create images, and play radio from anywhere in the world. "
        "How can I help?",
    ),
    (
        re.compile(r"^(thank(s| you)?|thanks a lot|thx|ty|much appreciated)\b.*$", re.IGNORECASE),
        "You're welcome! 😊 Glad to help. Anything else you'd like to know?",
    ),
    (
        re.compile(r"^(ok|okay|fine|sure|got it|alright|nice|great|cool|good)\b\.?$", re.IGNORECASE),
        "Great! Let me know if you need anything else. 👍",
    ),
    (
        re.compile(r"^(bye|goodbye|see you|see ya|later|gn|good night)\b.*$", re.IGNORECASE),
        "Bye! 👋 Come back any time — I'll be right here when you need me.",
    ),
    (
        re.compile(r"^(what can you do|what do you do|help me|what are your features)\b.*$", re.IGNORECASE),
        "I can answer questions from documents and web pages I've learned, remember "
        "what you tell me, write long essays (up to 50 pages), summarize text, "
        "generate images, play live radio from anywhere on Earth, and help with "
        "everyday campus questions. Just ask!",
    ),
]


def is_short_question(text: str) -> bool:
    """Heuristic: is this a short, casual, non-deep question KUDOS can answer
    quickly instead of running the full retrieval pipeline?"""
    t = (text or "").strip()
    if not t:
        return False
    if len(t) > 80:
        return False
    low = t.lower()
    if any(hint in low for hint in _DEEP_HINTS):
        return False
    # A question that is 1-2 short clauses and not a knowledge probe.
    return "?" in t or _is_smalltalk(low)


def _is_smalltalk(low: str) -> bool:
    return any(pattern.match(low) for pattern, _ in _CANNED)


def _canned_reply(text: str) -> str | None:
    low = (text or "").strip().lower()
    for pattern, reply in _CANNED:
        if pattern.match(low):
            return reply
    return None


async def get_short_answer(question: str, user_name: str = "") -> str:
    """Answer a short, casual question fast. Returns a concise reply."""
    canned = _canned_reply(question)
    if canned:
        return canned

    system = (
        "You are KUDOS, the friendly Digital Campus AI assistant. The user asked "
        "a SHORT, SIMPLE question. Answer in 1-3 short sentences only — no lists, "
        "no citations, no long explanations. Be warm and natural."
    )
    if user_name:
        system += f" The user's name is {user_name}."
    user = f"Short question: {question}\n\nGive a brief, friendly answer."
    try:
        result = await query_best_llm(user, system)
        reply = (result.get("response") or "").strip()
        if 3 <= len(reply) <= 300:
            return reply
    except Exception:
        pass

    # Fallback: a neutral, helpful short answer.
    return (
        f"Short answer: {question.strip().rstrip('?.')}. "
        "Happy to go deeper — just ask and I'll pull up everything I know! 🙂"
    )


# ──────────────────────────────────────────────
# SUMMARIZATION
# ──────────────────────────────────────────────

_STOP = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "has",
    "have",
    "he",
    "her",
    "his",
    "i",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "they",
    "this",
    "to",
    "was",
    "were",
    "will",
    "with",
    "you",
    "your",
    "we",
    "our",
    "do",
    "does",
    "did",
    "not",
    "so",
    "such",
    "than",
    "then",
    "there",
    "these",
    "those",
    "when",
    "where",
    "which",
    "who",
    "whom",
    "why",
    "how",
    "all",
    "any",
    "because",
    "before",
    "between",
    "each",
    "few",
    "more",
    "most",
    "other",
    "some",
    "no",
    "nor",
    "too",
    "very",
    "just",
    "about",
}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text.lower())


def extractive_summary(text: str, max_sentences: int = 5) -> str:
    """Rank sentences by word frequency (classic extractive summarization)."""
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 30]
    if not sentences:
        return text.strip()[:600]
    words = [w for w in _tokenize(text) if w not in _STOP and len(w) > 2]
    freq: dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    max_freq = max(freq.values(), default=1)

    scored: list[tuple[float, int, str]] = []
    for i, s in enumerate(sentences):
        score = sum(freq.get(w, 0) / max_freq for w in set(_tokenize(s)) if w in freq)
        scored.append((score, -i, s))
    top = heapq.nlargest(min(max_sentences, len(scored)), scored)

    # Present in original order.
    order = sorted(top, key=lambda x: x[1])
    return " ".join(s for _, _, s in order)


async def summarize_text(text: str, max_sentences: int = 5, user_name: str = "") -> str:
    """Summarize text with the LLM, falling back to extractive summarization."""
    text = (text or "").strip()
    if not text:
        return ""
    if len(text) < 200:
        return text[:800]

    system = (
        "You are KUDOS, a skilled summarizer. Write a tight summary of the text "
        f"in about {max(2, min(max_sentences, 8))} sentences. Capture the key "
        "facts and the main point. Do not add opinions or information that is not "
        "in the text. Plain text only."
    )
    user = f"SUMMARIZE THIS TEXT:\n\n{text[:12000]}\n\nSummary:"
    try:
        result = await query_best_llm(user, system)
        summary = (result.get("response") or "").strip()
        if len(summary) > 30:
            return summary
    except Exception:
        pass
    return extractive_summary(text, max_sentences=max_sentences)
