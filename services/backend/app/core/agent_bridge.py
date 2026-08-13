"""KUDOS ↔ opencode agent bridge.

KUDOS delegates domain research to opencode subagents through the
opencode-agent sidecar — covering mathematics, every branch of science,
climatology and anything else a campus could want to know. Every finished
run is stored as a WELL-LABELLED library FILE in a PENDING state
(is_approved=False): only the superadmin can see and approve it, after
which it becomes public to the whole Digital Campus.
"""

from __future__ import annotations

import re

import httpx

from app.core.config import settings

# ──────────────────────────────────────────────
# THE SUBJECT UNIVERSE — everything KUDOS can learn
# ──────────────────────────────────────────────

PLANETARY_SUBJECTS = [
    # Mathematics
    "Mathematics",
    "Algebra",
    "Geometry",
    "Calculus",
    "Statistics",
    "Number theory",
    "Topology",
    "Probability",
    # Exact sciences
    "Physics",
    "Chemistry",
    "Biology",
    "Astronomy",
    "Cosmology",
    # Earth & climate sciences
    "Earth science",
    "Geology",
    "Geography",
    "Climatology",
    "Meteorology",
    "Oceanography",
    "Ecology",
    "Environmental science",
    "Hydrology",
    "Volcanology",
    "Seismology",
    # Life sciences
    "Genetics",
    "Neuroscience",
    "Evolutionary biology",
    "Microbiology",
    "Botany",
    "Zoology",
    "Anatomy",
    "Physiology",
    "Immunology",
    "Epidemiology",
    "Nutrition",
    "Medicine",
    "Pharmacology",
    # Human sciences
    "Psychology",
    "Sociology",
    "Anthropology",
    "Economics",
    "Political science",
    "Linguistics",
    "History",
    "Archaeology",
    "Law",
    "Education",
    "Communication studies",
    # Humanities & spirit
    "Philosophy",
    "Logic",
    "Ethics",
    "Theology",
    "Religious studies",
    "Literature",
    "Poetry",
    "Art history",
    "Music theory",
    "World cultures",
    "Languages",
    "Folklore",
    "Mythology",
    # Technology & applied
    "Computer science",
    "Artificial intelligence",
    "Robotics",
    "Engineering",
    "Aerospace engineering",
    "Materials science",
    "Electronic engineering",
    "Biotechnology",
    "Agriculture",
    "Forestry",
    "Science of consciousness",
]

_LOG_RE = re.compile(r"[^\w\-]+")


def _slug(title: str) -> str:
    slug = _LOG_RE.sub("-", title.lower()).strip("-")
    return slug[:100] or "learned-file"


def _summary(text: str, limit: int = 300) -> str:
    """A tiny local summarizer — first sentences, cleaned. No LLM needed."""
    cleaned = " ".join((text or "").split())
    return cleaned[:limit].rstrip(" ,.-") + ("…" if len(cleaned) > limit else "")


AGENT_PROMPT = (
    "Research {subject} comprehensively for a campus library. "
    "Produce a well-structured, accurate reference document in plain markdown covering:\n"
    "- Overview and defining ideas\n"
    "- History and development\n"
    "- Core concepts, laws, results and formulas where relevant\n"
    "- Major branches or subfields\n"
    "- Practical applications and real-world relevance\n"
    "- Key figures and milestones\n"
    "- How a learner goes deeper (books, courses, further topics)\n"
    "Be thorough, neutral and precise. Use clear headings."
)


def research_with_agent(subject: str, agent: str = "build", timeout: float = 480.0) -> dict | None:
    """Ask an opencode subagent to research a subject. Returns the written
    knowledge or None when the bridge is disabled/unreachable."""
    if not settings.OPENCODE_AGENT_URL or not settings.LEARN_WITH_AGENTS:
        return None
    payload: dict = {"prompt": AGENT_PROMPT.format(subject=subject), "agent": agent}
    if settings.OPENCODE_MODEL:
        payload["model"] = settings.OPENCODE_MODEL
    try:
        with httpx.Client(timeout=timeout) as client:
            res = client.post(f"{settings.OPENCODE_AGENT_URL.rstrip('/')}/learn", json=payload)
            if res.status_code != 200:
                return None
            data = res.json()
        text = (data.get("text") or "").strip()
        if len(text) < 200:
            return None
        return {
            "text": text,
            "agent": data.get("agent") or agent,
            "session_id": data.get("session_id"),
        }
    except Exception:
        return None


def store_learned_library_file(db, subject: str, content: str, agent: str = "build", actor_id: int | None = None):
    """Persist a learning result as a pending, well-labelled library file.

    Pending means is_approved=False — invisible to everyone except the
    superadmin, who must view and approve it before it becomes public to the
    campus. Chunks are written now so the file is instantly searchable the
    moment it is approved.

    Returns (doc, created) — created is False when the subject was already
    filed, so callers do not double-count their learning.
    """
    from app.api.v1.endpoints.kudos import chunk_text, extract_keywords, simple_summarize
    from app.models import KudosChunk, KudosDocument

    text = (content or "").strip()
    if not text:
        return None, False

    existing = (
        db.query(KudosDocument)
        .filter(KudosDocument.title == subject)
        .filter(KudosDocument.tags.like("%kudos-learned%"))
        .first()
    )
    if existing:
        return existing, False

    doc = KudosDocument(
        uploaded_by=actor_id,
        title=subject,
        filename=f"{_slug(subject)}.txt",
        file_type="md",
        storage_key="",
        content=text,
        summary=simple_summarize(text) or _summary(text),
        tags=f"kudos-learned, agent:{agent}, subject, library-review",
        is_approved=False,  # pending superadmin approval — not public yet
        is_active=True,
    )
    db.add(doc)
    db.flush()
    chunks = chunk_text(text)
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