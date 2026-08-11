"""
Digital Campus - KUDOS Eyes

Multimodal understanding for KUDOS: describe photos and videos sent in chat,
then turn that understanding into searchable knowledge. Uses whatever vision-
capable provider is configured (Gemini handles images + video natively;
OpenAI handles images).
"""

import base64
import mimetypes
import re

from sqlalchemy.orm import Session

from app.core import storage
from app.core.llm_engine import get_llm_response, media_provider_configured

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    words = text.split()
    if len(words) <= chunk_size:
        return [text.strip()] if text.strip() else []
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk.strip())
        start += chunk_size - overlap
    return chunks


def _extract_keywords(text: str, max_keywords: int = 20) -> str:
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    stop = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "is",
        "it",
        "that",
        "this",
        "with",
        "from",
        "by",
        "as",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "shall",
        "should",
        "may",
        "might",
        "can",
        "could",
        "i",
        "me",
        "my",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "they",
        "them",
        "their",
        "its",
        "not",
        "no",
        "nor",
        "so",
        "if",
        "than",
        "too",
        "very",
        "just",
        "about",
        "above",
        "after",
        "again",
        "all",
        "any",
        "because",
        "before",
        "between",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "then",
        "there",
        "these",
        "through",
        "under",
        "until",
        "when",
        "where",
        "which",
        "while",
        "who",
        "whom",
        "why",
        "how",
    }
    freq: dict[str, int] = {}
    for w in words:
        if w not in stop:
            freq[w] = freq.get(w, 0) + 1
    top = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:max_keywords]
    return " ".join(w for w, _ in top)


def _simple_summarize(text: str, max_sentences: int = 5) -> str:
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    return ". ".join(sentences[:max_sentences]) + "." if sentences else text[:500]


def _media_items(media: list) -> list:
    """Normalize [{"key":..., "mime_type":..., "data":...}] into inline payloads."""
    items = []
    for m in media or []:
        if m.get("data"):
            items.append({"mime_type": m.get("mime_type", "image/jpeg"), "data": m["data"]})
            continue
        key = m.get("key")
        if key:
            try:
                raw = storage.download(key)
            except Exception:
                continue
            mime = m.get("mime_type") or mimetypes.guess_type(key)[0] or "application/octet-stream"
            items.append({"mime_type": mime, "data": base64.b64encode(raw).decode()})
    return items


async def analyze_media(db: Session, media: list, prompt: str = "") -> str:
    """Describe a list of media blobs. Returns a text description or ''."""
    items = _media_items(media)
    if not items:
        return ""
    if not media_provider_configured():
        return ""
    question = prompt or (
        "Look at the attached photo/video carefully and describe it in detail: "
        "what it shows, people/objects/text, colors, and anything notable. "
        "If it is a video, summarize what happens over time."
    )
    answer = await get_llm_response(question=question, media=items, user_name="")
    return (answer or "").strip()


async def describe_and_ingest(db: Session, media: list, uploaded_by: int, title: str, is_admin: bool) -> dict:
    """Describe media, then ingest the description as a searchable knowledge
    document so KUDOS 'learns' the photo/video. Returns a result summary."""
    from app.models import KudosChunk, KudosDocument

    description = await analyze_media(db, media)
    if not description:
        return {"learned": False, "reason": "vision-unavailable", "description": ""}

    text = f"[Media description]\n{description}"
    doc = KudosDocument(
        uploaded_by=uploaded_by,
        title=title,
        filename=title,
        file_type="media",
        storage_key="",
        content=text,
        summary=_simple_summarize(text),
        tags="media,vision",
        is_approved=is_admin,
    )
    db.add(doc)
    db.flush()
    for i, chunk_content in enumerate(_chunk_text(text)):
        db.add(
            KudosChunk(
                document_id=doc.id,
                chunk_index=i,
                content=chunk_content,
                word_count=len(chunk_content.split()),
                keywords=_extract_keywords(chunk_content),
            )
        )
    doc.chunk_count = len(_chunk_text(text))
    db.commit()
    db.refresh(doc)
    return {"learned": True, "document_id": doc.id, "description": description, "chunk_count": doc.chunk_count}
