"""
Digital Campus - KUDOS AI Assistant
Document learning, web learning, retrieval-based chat, superadmin controls.
"""

import base64
import contextlib
import io
import json
import re
import time
import uuid
from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core import storage
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.kudos_guardian import self_improver
from app.models import (
    KudosChunk,
    KudosConversation,
    KudosDocument,
    KudosMessage,
    KudosWebKnowledge,
    User,
    Visit,
)
from app.schemas import (
    ChatSendResponse,
    GuestAskRequest,
    GuestProfileResponse,
    GuestProfileUpdate,
    KudosAskRequest,
    KudosAskResponse,
    KudosConversationResponse,
    KudosDocumentResponse,
    KudosDocumentUpdate,
    KudosMessageResponse,
    KudosStats,
    KudosWebKnowledgeResponse,
    KudosWebLearn,
    ToolCallRequest,
    ToolRegisterRequest,
)

router = APIRouter()

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
STOP_WORDS = {
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


def extract_text_from_file(content: bytes, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("txt", "md", "csv", "json", "py", "js", "html", "css"):
        return content.decode("utf-8", errors="ignore")
    if ext == "pdf":
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(io.BytesIO(content))
            return "".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return content.decode("utf-8", errors="ignore")
    if ext in ("docx", "doc"):
        try:
            from docx import Document

            doc = Document(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            return content.decode("utf-8", errors="ignore")
    return content.decode("utf-8", errors="ignore")


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
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


def extract_keywords(text: str, max_keywords: int = 20) -> str:
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    freq: dict[str, int] = {}
    for w in words:
        if w not in STOP_WORDS:
            freq[w] = freq.get(w, 0) + 1
    return ",".join(w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:max_keywords])


def simple_summarize(text: str, max_sentences: int = 5) -> str:
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    return ". ".join(sentences[:max_sentences]) + "." if sentences else text[:500]


def search_chunks(db: Session, query: str, limit: int = 5) -> list[dict]:
    scored: list[dict] = []

    # Optional semantic retrieval. It is deliberately opt-in because it
    # requires a provider key, pgvector, and an indexed vector table.
    if settings.SEMANTIC_SEARCH_ENABLED:
        try:
            from app.core.embeddings import get_embeddings_provider
            from app.core.vector_store import query_vectors

            embedding = get_embeddings_provider().embed_texts([query])[0]
            for match in query_vectors(embedding, top_k=limit):
                chunk = (
                    db.query(KudosChunk)
                    .join(KudosDocument)
                    .filter(
                        KudosChunk.document_id == match["document_id"],
                        KudosChunk.chunk_index == match["chunk_index"],
                        KudosDocument.is_approved.is_(True),
                        KudosDocument.is_active.is_(True),
                    )
                    .first()
                )
                if chunk:
                    distance = max(float(match.get("distance", 1.0)), 0.0)
                    scored.append(
                        {
                            "chunk_id": chunk.id,
                            "document_id": chunk.document_id,
                            "title": chunk.document.title,
                            "content": chunk.content[:500],
                            "score": max(0.1, 1.0 - distance),
                            "retrieval": "semantic",
                        }
                    )
        except Exception:
            # A missing provider/table should never disable keyword retrieval.
            pass

    query_words = set(re.findall(r"[a-zA-Z]{3,}", query.lower())) - STOP_WORDS
    if not query_words:
        return scored[:limit]
    try:
        chunks = (
            db.query(KudosChunk).join(KudosDocument).filter(KudosDocument.is_approved, KudosDocument.is_active).all()
        )
    except Exception:
        return scored[:limit]

    for chunk in chunks:
        content_lower = chunk.content.lower()
        keywords = set(chunk.keywords.split(",")) if chunk.keywords else set()
        score = sum(3 if w in keywords else 1 for w in query_words if w in content_lower)
        if score > 0:
            scored.append(
                {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "title": chunk.document.title,
                    "content": chunk.content[:500],
                    "score": score,
                }
            )

    try:
        web_items = db.query(KudosWebKnowledge).filter(KudosWebKnowledge.is_approved, KudosWebKnowledge.is_active).all()
        for item in web_items:
            content_lower = (item.content or "").lower()
            score = sum(1 for w in query_words if w in content_lower)
            if score > 0:
                scored.append(
                    {
                        "chunk_id": None,
                        "document_id": None,
                        "web_id": item.id,
                        "title": item.title,
                        "content": (item.summary or item.content[:500])[:500],
                        "score": score,
                    }
                )
    except Exception:
        pass

    scored.sort(key=lambda x: -x["score"])
    return scored[:limit]


def generate_answer(query: str, sources: list[dict]) -> str:
    """Simple fallback answer — never used if conversation engine works."""
    if not sources:
        return f'I don\'t have information about "{query}" yet. Try uploading a document or teaching me a web page about it.'  # noqa: E501
    # Extract relevant content
    import re

    query_words = set(re.findall(r"[a-zA-Z]{3,}", query.lower())) - STOP_WORDS
    best_content = ""
    best_score = 0
    for src in sources:
        content = src.get("content", "")
        score = sum(1 for w in query_words if w in content.lower())
        if score > best_score:
            best_score = score
            best_content = content
    # Extract relevant sentences
    sentences = re.split(r"[.!?\n]+", best_content)
    relevant = [s.strip() for s in sentences if len(s.strip()) > 20 and any(w in s.lower() for w in query_words)][:3]
    if relevant:
        return ". ".join(relevant) + "."
    return best_content[:400]


# ──────────────────────────────────────────────
# DOCUMENT ENDPOINTS
# ──────────────────────────────────────────────


@router.post("/documents/upload", response_model=KudosDocumentResponse, status_code=201)
async def upload_document(
    title: str = Form(...),
    tags: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content_bytes = await file.read()
    if len(content_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    text = extract_text_from_file(content_bytes, file.filename or "unknown.txt")
    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    # Keep the original binary in object storage (docs/ prefix); the extracted
    # text below remains the retrieval source of truth in the database.
    storage_key = ""
    try:
        key = storage.new_key("docs/", file.filename or "document.bin")
        storage.upload_bytes(key, content_bytes, content_type="application/octet-stream")
        storage_key = key
    except Exception:
        storage_key = ""

    doc = KudosDocument(
        uploaded_by=current_user.id,
        title=title,
        filename=file.filename or "unknown",
        file_type=file.filename.rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "",
        storage_key=storage_key,
        content=text,
        summary=simple_summarize(text),
        tags=tags,
        is_approved=current_user.is_admin,
    )
    db.add(doc)
    db.flush()
    for i, chunk_content in enumerate(chunk_text(text)):
        db.add(
            KudosChunk(
                document_id=doc.id,
                chunk_index=i,
                content=chunk_content,
                word_count=len(chunk_content.split()),
                keywords=extract_keywords(chunk_content),
            )
        )
    doc.chunk_count = len(chunk_text(text))
    db.commit()
    db.refresh(doc)

    # Semantic indexing is optional and runs in Celery so uploads remain fast.
    if settings.SEMANTIC_SEARCH_ENABLED:
        try:
            from app.tasks import index_document_embeddings

            index_document_embeddings.delay(doc.id)
        except Exception:
            # Keyword retrieval remains available if the worker or provider is
            # not configured yet.
            pass

    return doc


@router.get("/documents", response_model=list[KudosDocumentResponse])
def list_documents(
    show_all: bool = False, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    q = db.query(KudosDocument)
    if not current_user.is_admin:
        q = q.filter(KudosDocument.is_approved, KudosDocument.is_active)
    elif not show_all:
        q = q.filter(KudosDocument.is_active)
    return q.order_by(KudosDocument.created_at.desc()).all()


@router.patch("/documents/{doc_id}", response_model=KudosDocumentResponse)
def update_document(
    doc_id: int, body: KudosDocumentUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    doc = db.query(KudosDocument).filter(KudosDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(doc, field, value)
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/documents/{doc_id}", status_code=204)
def delete_document(doc_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    doc = db.query(KudosDocument).filter(KudosDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.storage_key:
        with contextlib.suppress(Exception):
            storage.delete(doc.storage_key)
    db.delete(doc)
    db.commit()


@router.get("/documents/{doc_id}/original")
def download_original(doc_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Download the original file uploaded for a document (if stored)."""
    doc = db.query(KudosDocument).filter(KudosDocument.id == doc_id).first()
    if not doc or not doc.is_active:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.storage_key:
        raise HTTPException(status_code=404, detail="Original file is not stored (text-only upload)")
    try:
        content = storage.download(doc.storage_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Original file missing") from None
    media_type = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
        "md": "text/markdown",
        "json": "application/json",
        "py": "text/x-python",
        "js": "text/javascript",
        "html": "text/html",
        "css": "text/css",
    }.get(doc.file_type, "application/octet-stream")
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{doc.filename}"'},
    )


# ──────────────────────────────────────────────
# WEB LEARNING ENDPOINTS
# ──────────────────────────────────────────────


@router.post("/learn/web", response_model=KudosWebKnowledgeResponse, status_code=201)
async def learn_web_page(
    body: KudosWebLearn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL")
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            response = await client.get(body.url)
            response.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {e}") from e
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    title = body.title or (soup.title.string if soup.title else body.url)
    text = soup.get_text(separator="\n", strip=True)
    if len(text) < 50:
        raise HTTPException(status_code=400, detail="Page has too little text content")
    knowledge = KudosWebKnowledge(
        url=body.url,
        title=title[:255],
        content=text,
        summary=simple_summarize(text),
        is_approved=current_user.is_admin,
        learned_by=current_user.id,
    )
    db.add(knowledge)
    db.commit()
    db.refresh(knowledge)
    return knowledge


@router.get("/learn/web", response_model=list[KudosWebKnowledgeResponse])
def list_web_knowledge(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    q = db.query(KudosWebKnowledge)
    if not current_user.is_admin:
        q = q.filter(KudosWebKnowledge.is_approved, KudosWebKnowledge.is_active)
    return q.order_by(KudosWebKnowledge.created_at.desc()).all()


@router.patch("/learn/web/{item_id}", response_model=KudosWebKnowledgeResponse)
def update_web_knowledge(
    item_id: int, body: KudosDocumentUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    item = db.query(KudosWebKnowledge).filter(KudosWebKnowledge.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Web knowledge not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        if hasattr(item, field):
            setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


# ──────────────────────────────────────────────
# CHAT WITH KUDOS — ROBUST ERROR HANDLING
# ──────────────────────────────────────────────

_TERMINAL_TRIGGER_RE = re.compile(
    r"\b(code|script|function|terminal|shell|bash|python|bug|test|debug|"
    r"refactor|implement|build|deploy|run this|try this)\b",
    re.IGNORECASE,
)


def _open_terminal_for_question(db: Session, current_user: User, question: str) -> str:
    """Auto-open a terminal session when the question asks KUDOS to work with
    code. Returns a prompt block telling KUDOS its terminal is open, or "".
    """
    if not _TERMINAL_TRIGGER_RE.search(question or ""):
        return ""
    from app.core.terminal import pick_session_for_user

    session, _created = pick_session_for_user(db, current_user.id, admin=current_user.is_admin)
    where = "on your device" if session.kind == "device" else "online (server workspace)"
    return (
        f"- You have an open terminal session #{session.id} ({session.name}) {where}.\n"
        "- To run a shell command, call POST /api/v1/kudos/terminal/sessions/{id}/command "
        "(source=user runs it; source=agent requires superadmin approval).\n"
        "- To write and run a code file, call POST /api/v1/kudos/terminal/sessions/{id}/code "
        "with {language: python3|node|bash, code: ...} — it runs immediately.\n"
        "- Device sessions execute on the user's hardware; online sessions run in a "
        "jailed workspace. Use the terminal to test anything you write."
    )


@router.post("/ask", response_model=KudosAskResponse)
async def ask_kudos(
    body: KudosAskRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Ask KUDOS — always returns an answer, never crashes."""
    try:
        # Get or create conversation
        conv = None
        if body.conversation_id:
            try:
                conv = (
                    db.query(KudosConversation)
                    .filter(
                        KudosConversation.id == body.conversation_id,
                        KudosConversation.user_id == current_user.id,
                    )
                    .first()
                )
            except Exception:
                conv = None
        if not conv:
            conv = KudosConversation(user_id=current_user.id, title=body.question[:100])
            db.add(conv)
            db.flush()

        # Save user message
        db.add(KudosMessage(conversation_id=conv.id, role="user", content=body.question))

        # Fast path: short, casual, non-deep questions get a quick answer
        # without running the full retrieval + citation pipeline.
        from app.core.privacy_guard import scrub_response
        from app.core.quick_answers import get_short_answer, is_short_question

        if is_short_question(body.question):
            short = await get_short_answer(
                body.question, current_user.full_name.split()[0] if current_user.full_name else ""
            )
            short = scrub_response(short, allow_emails=True)
            try:
                db.add(KudosMessage(conversation_id=conv.id, role="kudos", content=short, sources="[]"))
                db.commit()
            except Exception:
                db.rollback()
            return KudosAskResponse(answer=short, sources=[], conversation_id=conv.id, media=[])

        # Search knowledge base
        sources = []
        with contextlib.suppress(Exception):
            sources = search_chunks(db, body.question)

        # Ask the internal MCP gateway for additional tool-backed sources when
        # enabled. The local database/search fallback remains authoritative when
        # MCP is unavailable.
        if settings.MCP_ENABLED:
            try:
                from app.core.mcp_client import search_mcp_sources

                mcp_sources = await search_mcp_sources(body.question)
                sources = mcp_sources + sources
            except Exception:
                pass

        # Build knowledge context from sources (numbered for citations)
        knowledge_context = ""
        if sources:
            knowledge_context = "\n".join(
                f"[{i}] {s.get('content', '')[:300]}" for i, s in enumerate(sources[:3], start=1)
            )

        # Retrieve user memory relevant to the question
        memory_context = ""
        try:
            from app.core.memory_store import build_memory_context

            memory_context = build_memory_context(db, current_user.id, query=body.question)
        except Exception:
            pass

        # Personal KUDOS: tone/verbosity/interests for this user
        persona_instructions = ""
        try:
            from app.core.persona import build_persona_instructions, profile_dict

            persona_instructions = build_persona_instructions(profile_dict(db, current_user.id))
        except Exception:
            pass

        # KUDOS's soul: who it is — injected into the system prompt
        soul_context = ""
        try:
            from app.core.soul import build_soul_context

            soul_context = build_soul_context(db)
        except Exception:
            pass

        # KUDOS's built-in self-knowledge (sandbox + internet concepts)
        self_knowledge = ""
        try:
            from app.core.sandbox import build_sandbox_knowledge_context

            self_knowledge = build_sandbox_knowledge_context(db)
        except Exception:
            pass
        try:
            radio_note = _radio_context(db)
            if radio_note:
                self_knowledge = f"{self_knowledge}\n{radio_note}"
        except Exception:
            pass
        try:
            from app.core.world_map import maps_knowledge_context

            geo_note = maps_knowledge_context(db, body.question)
            if geo_note:
                self_knowledge = f"{self_knowledge}\n{geo_note}"
        except Exception:
            pass
        try:
            from app.core.network_mesh import network_note

            net_note = network_note(db, current_user)
            if net_note:
                self_knowledge = f"{self_knowledge}\n{net_note}"
        except Exception:
            pass
        with contextlib.suppress(Exception):
            self_knowledge = f"{self_knowledge}\n{_connectors_note()}"

        # KUDOS Terminal: when the question looks like code to write or test,
        # auto-open a session so KUDOS can act like an agent. The session id
        # is added to the prompt so the LLM knows its terminal is available.
        terminal_context = ""
        if settings.KUDOS_TERMINAL_AUTO_OPEN and current_user.is_admin:
            with contextlib.suppress(Exception):
                terminal_context = _open_terminal_for_question(db, current_user, body.question)

        # KUDOS's offline brain: answer from its own persistent knowledge
        # without any LLM when offline-first is enabled, or keep it as the
        # guaranteed-grounded fallback.
        from app.core.kudos_brain import answer_offline, hallucination_guard

        offline = None
        try:
            if settings.KUDOS_OFFLINE_FIRST:
                offline = answer_offline(db, body.question, user_id=current_user.id)
        except Exception:
            offline = None

        # Try LLM first (human-like response)
        answer = ""
        if not (offline and offline.get("grounded")):
            try:
                from app.core.llm_engine import get_llm_response

                conv_history = []
                try:
                    conv_history = (
                        db.query(KudosMessage)
                        .filter(KudosMessage.conversation_id == conv.id)
                        .order_by(KudosMessage.created_at.desc())
                        .limit(5)
                        .all()
                    )
                    conv_history = [{"role": m.role, "content": m.content} for m in conv_history]
                except Exception:
                    pass

                llm_answer = await get_llm_response(
                    question=body.question,
                    knowledge_context=knowledge_context,
                    conversation_history=conv_history,
                    user_name=current_user.full_name.split()[0] if current_user.full_name else "",
                    memory_context=memory_context,
                    persona_instructions=persona_instructions,
                    soul_context=soul_context,
                    self_knowledge=self_knowledge,
                    terminal_context=terminal_context,
                )
                if llm_answer and len(llm_answer) > 10:
                    answer = llm_answer
            except Exception:
                pass

        # Fallback to the offline brain (fully grounded, no LLM needed).
        used_fallback = False
        if not answer or len(answer) < 10:
            try:
                used_fallback = True
                if offline is None:
                    offline = answer_offline(db, body.question, user_id=current_user.id)
                if offline.get("answer"):
                    answer = offline["answer"]
            except Exception:
                pass

        # Legacy fallbacks only when the brain itself has nothing.
        if not answer or len(answer) < 10:
            used_fallback = True
            try:
                from app.core.conversation_engine import generate_human_response

                answer = generate_human_response(
                    query=body.question,
                    sources=sources,
                    conv_id=conv.id,
                    user_name=current_user.full_name.split()[0] if current_user.full_name else None,
                )
            except Exception:
                answer = generate_answer(body.question, sources)

        # Hallucination guard: every sentence of the final answer must be
        # backed by a real source. When grounded-only is on and the answer
        # cannot be verified, swap in the grounded offline brain answer or an
        # honest refusal instead of risking a made-up reply.
        if settings.KUDOS_GROUNDED_ONLY and sources:
            guard = hallucination_guard(answer, sources, threshold=settings.KUDOS_BRAIN_MIN_SCORE)
            if not guard["passes"]:
                try:
                    if offline is None:
                        offline = answer_offline(db, body.question, user_id=current_user.id)
                    if offline.get("grounded"):
                        answer = offline["answer"]
                        used_fallback = True
                    else:
                        answer = (
                            "I don't have verified information about that. My brain and knowledge base "
                            "don't contain anything I can answer this from without guessing — and I "
                            "never guess. Teach me a source covering it and I'll answer for certain."
                        )
                        used_fallback = True
                except Exception:
                    pass

        if not answer or len(answer) < 10:
            answer = generate_answer(body.question, sources)
            used_fallback = True

        # Fallback answers don't emit [n] markers — make the sources explicit
        if used_fallback and sources:
            from app.models import KudosDocument

            titles = []
            for i, s in enumerate(sources[:3], start=1):
                title = s.get("title") or ""
                if not title and s.get("document_id"):
                    doc_row = db.get(KudosDocument, s["document_id"])
                    title = doc_row.title if doc_row else ""
                titles.append(f"[{i}] {title or s.get('source', '') or 'source'}")
            answer = f"{answer}\n\nSources: {', '.join(titles)}"

        # Parse inline [n] citations the LLM used
        from app.core.llm_engine import extract_citations

        cited = extract_citations(answer, sources[:3])

        # Execute generation/tool markers (IMAGE_PROMPT / VIDEO_PROMPT /
        # TOOL_CALL / REGISTER_TOOL) and attach any generated media.
        from app.core.privacy_guard import scrub_response

        answer = scrub_response(answer, allow_emails=True)
        media_gen: list[dict] = []
        with contextlib.suppress(Exception):
            answer, media_gen = await _apply_generation_markers(db, answer, current_user)

        # Self-improvement logging
        with contextlib.suppress(Exception):
            self_improver.log_question(current_user.id, body.question, had_sources=bool(sources))

        # Save KUDOS response
        try:
            db.add(
                KudosMessage(
                    conversation_id=conv.id,
                    role="kudos",
                    content=answer,
                    sources=json.dumps(sources[:3]) if sources else "[]",
                    media=_media_json(media_gen),
                )
            )
            db.commit()
        except Exception:
            db.rollback()

        # Remember the exchange (short-term conversation memory)
        try:
            from app.core.memory_store import consolidate_memories, write_memory

            write_memory(
                db,
                current_user.id,
                content=f"User asked: {body.question[:200]}. I answered: {answer[:300]}",
                layer="short_term",
                kind="context",
                importance=0.4,
                source="conversation",
            )
            consolidate_memories(db, current_user.id)
        except Exception:
            with contextlib.suppress(Exception):
                db.rollback()

        return KudosAskResponse(
            answer=answer,
            sources=cited
            if cited
            else [
                {
                    "document_id": s.get("document_id"),
                    "web_id": s.get("web_id"),
                    "title": s.get("title", ""),
                    "preview": s.get("content", "")[:200],
                }
                for s in (sources[:3] if sources else [])
            ],
            conversation_id=conv.id,
            media=media_gen,
        )

    except Exception as e:
        with contextlib.suppress(Exception):
            db.rollback()
        return KudosAskResponse(
            answer=f"I had trouble processing that. Please try again. ({str(e)[:100]})",
            sources=[],
            conversation_id=body.conversation_id or 0,
        )


@router.get("/conversations", response_model=list[KudosConversationResponse])
def list_conversations(
    archived: bool = False, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    q = db.query(KudosConversation).filter(
        KudosConversation.user_id == current_user.id,
        KudosConversation.archived.is_(archived),
    )
    return q.order_by(KudosConversation.created_at.desc()).all()


@router.post("/conversations/archive-all")
def archive_all_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Move every active conversation to the archive (nothing is deleted)."""
    count = (
        db.query(KudosConversation)
        .filter(
            KudosConversation.user_id == current_user.id,
            KudosConversation.archived.is_(False),
        )
        .update({KudosConversation.archived: True})
    )
    db.commit()
    return {"archived": count}


@router.post("/conversations/{conv_id}/unarchive", response_model=KudosConversationResponse)
def unarchive_conversation(conv_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Restore an archived conversation as the active one."""
    conv = (
        db.query(KudosConversation)
        .filter(
            KudosConversation.id == conv_id,
            KudosConversation.user_id == current_user.id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.archived = False
    db.commit()
    db.refresh(conv)
    return conv


@router.get("/conversations/{conv_id}/messages", response_model=list[KudosMessageResponse])
def get_conversation_messages(
    conv_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    conv = (
        db.query(KudosConversation)
        .filter(KudosConversation.id == conv_id, KudosConversation.user_id == current_user.id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return (
        db.query(KudosMessage).filter(KudosMessage.conversation_id == conv_id).order_by(KudosMessage.created_at).all()
    )


@router.delete("/conversations/{conv_id}", status_code=204)
def delete_conversation(conv_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conv = (
        db.query(KudosConversation)
        .filter(KudosConversation.id == conv_id, KudosConversation.user_id == current_user.id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)
    db.commit()


# ──────────────────────────────────────────────
# SUPERADMIN CONTROLS
# ──────────────────────────────────────────────


@router.get("/admin/stats", response_model=KudosStats)
def kudos_stats(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return KudosStats(
        total_documents=db.query(KudosDocument).count(),
        approved_documents=db.query(KudosDocument).filter(KudosDocument.is_approved).count(),
        total_chunks=db.query(KudosChunk).count(),
        total_web_knowledge=db.query(KudosWebKnowledge).count(),
        total_conversations=db.query(KudosConversation).count(),
        total_messages=db.query(KudosMessage).count(),
    )


@router.post("/admin/approve-all-documents")
def approve_all_documents(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    count = db.query(KudosDocument).filter(~KudosDocument.is_approved).update({"is_approved": True})
    db.commit()
    return {"approved": count}


@router.post("/admin/approve-all-web")
def approve_all_web(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    count = db.query(KudosWebKnowledge).filter(~KudosWebKnowledge.is_approved).update({"is_approved": True})
    db.commit()
    return {"approved": count}


@router.post("/admin/pending")
def list_pending(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    docs = db.query(KudosDocument).filter(~KudosDocument.is_approved).all()
    web = db.query(KudosWebKnowledge).filter(~KudosWebKnowledge.is_approved).all()
    return {
        "pending_documents": [
            {"id": d.id, "title": d.title, "uploaded_by": d.uploaded_by, "chunks": d.chunk_count} for d in docs
        ],
        "pending_web": [{"id": w.id, "url": w.url, "title": w.title, "learned_by": w.learned_by} for w in web],
    }


# ──────────────────────────────────────────────────────────────
# PUBLIC GUEST CHAT — anonymous visitors, no login required
# ──────────────────────────────────────────────────────────────
_GUEST_EMAIL = "guest@campus.local"
_GUEST_WELCOME = (
    "Hi 👋 Welcome to Digital Campus — I'm KUDOS, your AI assistant. "
    "Ask me anything about courses, assignments, campus life or your studies. "
    "No account needed to chat; sign in (top right) to keep your history forever. \n\n"
    "What can I help you with?"
)
_GUEST_RATE_LIMIT = 15  # asks per guest per minute
_GUEST_RATE_WINDOW = 60  # seconds
_guest_ask_times: dict[str, list[float]] = {}


def _guest_rate_ok(guest_id: str) -> bool:
    """Simple in-memory rate limit per anonymous guest browser id."""
    now = time.time()
    recent = [t for t in _guest_ask_times.get(guest_id, []) if now - t < _GUEST_RATE_WINDOW]
    if len(recent) >= _GUEST_RATE_LIMIT:
        _guest_ask_times[guest_id] = recent
        return False
    recent.append(now)
    _guest_ask_times[guest_id] = recent
    return True


def _get_or_create_guest_user(db: Session) -> User:
    """Shared internal guest user so anonymous chats have a valid owner."""
    user = db.query(User).filter(User.email == _GUEST_EMAIL).first()
    if not user:
        user = User(email=_GUEST_EMAIL, full_name="Guest", hashed_password="!", is_approved=True)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _get_guest_conversation(db: Session, guest_id: str):
    conv = db.query(KudosConversation).filter(KudosConversation.guest_key == guest_id).first()
    if conv:
        return conv, False
    guest = _get_or_create_guest_user(db)
    conv = KudosConversation(user_id=guest.id, title="Guest Chat", guest_key=guest_id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv, True


@router.post("/guest/ask", response_model=KudosAskResponse)
async def guest_ask_kudos(body: GuestAskRequest, db: Session = Depends(get_db)):
    """Anonymous chat with KUDOS. The browser sends a persistent guest_id
    (a UUID stored in localStorage) so conversations survive refreshes.
    Guests get the same knowledge pipeline but no personal memory, persona
    or terminal access."""
    if not body.guest_id or len(body.guest_id) < 8:
        raise HTTPException(status_code=422, detail="guest_id must be at least 8 characters")
    if not _guest_rate_ok(body.guest_id):
        raise HTTPException(status_code=429, detail="You're asking a lot — please wait a minute")

    _get_or_create_guest_user(db)
    conv, first_chat = _get_guest_conversation(db, body.guest_id)
    if first_chat:
        db.add(KudosMessage(conversation_id=conv.id, role="kudos", content=_GUEST_WELCOME))
        db.commit()

    db.add(KudosMessage(conversation_id=conv.id, role="user", content=body.question))
    db.flush()

    # Fast path for short, casual guest questions.
    from app.core.privacy_guard import scrub_response
    from app.core.quick_answers import get_short_answer, is_short_question

    if is_short_question(body.question):
        short = await get_short_answer(body.question)
        short = scrub_response(short, allow_emails=True)
        try:
            db.add(KudosMessage(conversation_id=conv.id, role="kudos", content=short, sources="[]"))
            db.commit()
        except Exception:
            db.rollback()
        return KudosAskResponse(answer=short, sources=[], conversation_id=conv.id, media=[])

    sources = []
    with contextlib.suppress(Exception):
        sources = search_chunks(db, body.question)

    knowledge_context = ""
    if sources:
        knowledge_context = "\n".join(f"[{i}] {s.get('content', '')[:300]}" for i, s in enumerate(sources[:3], start=1))

    soul_context = ""
    self_knowledge = ""
    try:
        from app.core.soul import build_soul_context

        soul_context = build_soul_context(db)
    except Exception:
        pass
    try:
        from app.core.sandbox import build_sandbox_knowledge_context

        self_knowledge = build_sandbox_knowledge_context(db)
    except Exception:
        pass

    answer = ""
    try:
        from app.core.llm_engine import get_llm_response

        conv_history = []
        try:
            conv_history = (
                db.query(KudosMessage)
                .filter(KudosMessage.conversation_id == conv.id)
                .order_by(KudosMessage.created_at.desc())
                .limit(5)
                .all()
            )
            conv_history = [{"role": m.role, "content": m.content} for m in conv_history]
        except Exception:
            pass
        llm_answer = await get_llm_response(
            question=body.question,
            knowledge_context=knowledge_context,
            conversation_history=conv_history,
            user_name="Guest",
            memory_context="",
            persona_instructions="",
            soul_context=soul_context,
            self_knowledge=self_knowledge,
            terminal_context="",
        )
        if isinstance(llm_answer, dict):
            llm_answer = llm_answer.get("response") or llm_answer.get("answer") or ""
        answer = str(llm_answer or "").strip()
        if len(answer) <= 10:
            raise ValueError("empty llm answer")
    except Exception:
        answer = generate_answer(body.question, sources)

    if not answer or len(answer) < 10:
        answer = generate_answer(body.question, sources)

    # Offline brain + hallucination guard for guest chats: guests get the same
    # guarantee — KUDOS never answers from unsupported claims.
    try:
        from app.core.kudos_brain import answer_offline, hallucination_guard

        offline = answer_offline(db, body.question, user_id=None)
        if settings.KUDOS_GROUNDED_ONLY and sources:
            guard = hallucination_guard(answer, sources, threshold=settings.KUDOS_BRAIN_MIN_SCORE)
            if not guard["passes"]:
                answer = (
                    offline["answer"]
                    if offline.get("grounded")
                    else (
                        "I don't have verified information about that. My brain and knowledge base "
                        "don't contain anything I can answer this from without guessing — and I "
                        "never guess. Teach me a source covering it and I'll answer for certain."
                    )
                )
        elif settings.KUDOS_OFFLINE_FIRST and offline.get("grounded"):
            answer = offline["answer"]
    except Exception:
        pass

    from app.core.llm_engine import extract_citations

    cited = []
    try:
        cited = extract_citations(answer, sources[:3])
    except Exception:
        cited = []

    try:
        db.add(
            KudosMessage(
                conversation_id=conv.id,
                role="kudos",
                content=answer,
                sources=json.dumps(sources[:3]) if sources else "[]",
            )
        )
        db.commit()
    except Exception:
        db.rollback()

    return KudosAskResponse(
        answer=answer,
        sources=cited
        if cited
        else [
            {
                "document_id": s.get("document_id"),
                "web_id": s.get("web_id"),
                "title": s.get("title", ""),
                "preview": s.get("content", "")[:200],
            }
            for s in (sources[:3] if sources else [])
        ],
        conversation_id=conv.id,
    )


@router.get("/guest/messages", response_model=list[KudosMessageResponse])
def guest_messages(guest_id: str, db: Session = Depends(get_db)):
    """Anonymous visitor's chat history."""
    conv = db.query(KudosConversation).filter(KudosConversation.guest_key == guest_id).first()
    if not conv:
        return []
    return (
        db.query(KudosMessage).filter(KudosMessage.conversation_id == conv.id).order_by(KudosMessage.created_at).all()
    )


# ──────────────────────────────────────────────
# GUEST PROFILE — KUDOS learns who clicked the link
# ──────────────────────────────────────────────


def _guest_profile_row(db: Session, guest_id: str):
    return db.query(Visit).filter(Visit.guest_key == guest_id).order_by(Visit.last_seen.desc()).first()


@router.get("/guest/profile", response_model=GuestProfileResponse)
def guest_profile(guest_id: str, db: Session = Depends(get_db)):
    """Return what KUDOS knows about this anonymous visitor."""
    row = _guest_profile_row(db, guest_id)
    if not row:
        return GuestProfileResponse(guest_id=guest_id)
    return GuestProfileResponse(
        guest_id=guest_id,
        name=row.name or "",
        ai_name=row.ai_name or "",
        visit_count=row.visit_count or 0,
        first_seen=row.first_seen,
        last_seen=row.last_seen,
    )


@router.post("/guest/profile", response_model=GuestProfileResponse)
def guest_profile_update(body: GuestProfileUpdate, db: Session = Depends(get_db)):
    """Save the name KUDOS should call the visitor, and what they call KUDOS."""
    if not body.guest_id or len(body.guest_id) < 8:
        raise HTTPException(status_code=422, detail="guest_id must be at least 8 characters")
    row = _guest_profile_row(db, body.guest_id)
    if not row:
        row = Visit(guest_key=body.guest_id, ip="", user_agent="", path="/kudos")
        db.add(row)
    if body.name:
        row.name = body.name.strip()[:120]
    if body.ai_name:
        row.ai_name = body.ai_name.strip()[:60]
    row.last_seen = datetime.now(UTC)
    db.commit()
    return GuestProfileResponse(
        guest_id=body.guest_id,
        name=row.name or "",
        ai_name=row.ai_name or "",
        visit_count=row.visit_count or 0,
        first_seen=row.first_seen,
        last_seen=row.last_seen,
    )


# ──────────────────────────────────────────────
# MEDIA SERVING + CHAT-DRIVEN UPLOAD
# ──────────────────────────────────────────────

_MEDIA_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "bmp": "image/bmp",
    "svg": "image/svg+xml",
    "ico": "image/x-icon",
    "mp4": "video/mp4",
    "webm": "video/webm",
    "mov": "video/quicktime",
    "m4v": "video/mp4",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
    "oga": "audio/ogg",
    "m4a": "audio/mp4",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "opus": "audio/opus",
    "weba": "audio/webm",
}


def _looks_binary(content: bytes) -> bool:
    """True when a file is clearly binary (NUL bytes or many control chars),
    e.g. archives, executables, or unknown media — attach instead of parsing."""
    if not content:
        return False
    sample = content[:4096]
    nul = sample.count(b"\x00")
    if nul > 0:
        return True
    control = sum(1 for b in sample if b < 9 or 13 < b < 32)
    return (control / len(sample)) > 0.30


def _store_media(data_b64: str, mime: str, prefix: str = "media") -> str:
    content = base64.b64decode(data_b64)
    ext = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "video/mp4": "mp4",
        "video/webm": "webm",
        "audio/mpeg": "mp3",
        "audio/wav": "wav",
        "audio/ogg": "ogg",
        "audio/mp4": "m4a",
        "audio/aac": "aac",
        "audio/flac": "flac",
        "audio/opus": "opus",
        "audio/webm": "weba",
    }.get(mime, "bin")
    key = storage.new_key(f"{prefix}/", f"{uuid.uuid4().hex}.{ext}")
    storage.upload_bytes(key, content, content_type=mime)
    return key


def _media_url(key: str) -> str:
    return f"/api/v1/kudos/media/{key}"


def _media_json(items: list) -> str:
    return json.dumps(items)


@router.get("/media/{key:path}")
def get_media(key: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Stream a stored media file (attachments, generated images/videos)."""
    allowed = key.startswith(("media/", "generated/"))
    if not allowed:
        raise HTTPException(status_code=404, detail="Media not found")
    try:
        content = storage.download(key)
    except Exception:
        raise HTTPException(status_code=404, detail="Media not found") from None
    ext = key.rsplit(".", 1)[-1].lower() if "." in key else ""
    mime = _MEDIA_MIME.get(ext, "application/octet-stream")
    return Response(content=content, media_type=mime)


@router.get("/transient/{token}")
def get_transient(token: str, dl: int = 0):
    """Stream a short-lived generated video (short clips only) from Redis.
    Nothing is ever written to object storage — the bytes expire on their own
    after ~15 minutes. `?dl=1` forces a download."""
    import base64 as _b64

    from app.core.transient import get

    payload = get(token)
    if not payload:
        raise HTTPException(status_code=404, detail="This clip has expired or was already downloaded")
    content = _b64.b64decode(payload.get("data", ""))
    headers = {}
    if dl:
        headers["Content-Disposition"] = 'attachment; filename="kudos-clip.mp4"'
    return Response(content=content, media_type=payload.get("mime", "video/mp4"), headers=headers)


async def _apply_generation_markers(
    db: Session, text: str, current_user: User, prefix: str = "generated"
) -> tuple[str, list[dict]]:
    """Execute IMAGE_PROMPT/VIDEO_PROMPT/TOOL_CALL/REGISTER_TOOL markers in an
    answer. Returns (final_text, media_items_to_render)."""
    media_items: list[dict] = []
    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("IMAGE_PROMPT:"):
            prompt = stripped.partition(":")[2].strip()
            from app.core.llm_engine import generate_image

            result = await generate_image(prompt)
            if result.get("error"):
                out.append(f"(Could not create that image: {result['error']})")
                continue
            key = _store_media(result["data"], result.get("mime_type", "image/png"), prefix)
            media_items.append(
                {
                    "kind": "image",
                    "url": _media_url(key),
                    "mime": result.get("mime_type", "image/png"),
                    "caption": prompt,
                }
            )
            out.append("Here's the image I created for you! 🖼️")
        elif stripped.upper().startswith("VIDEO_PROMPT:"):
            prompt = stripped.partition(":")[2].strip()
            from app.core.video_gen import generate_video

            # Chat videos are SHORT clips only (never full-length), served as a
            # single-use download and NEVER saved to object storage.
            result = await generate_video(prompt, settings.MAX_CHAT_VIDEO_SECONDS)
            if result.get("error"):
                out.append(f"(Could not create that video: {result['error']})")
                continue
            from app.core.transient import put, transient_url

            token = put(result["data"], result.get("mime_type", "video/mp4"))
            if not token:
                out.append("(Could not host that video right now — please try again.)")
                continue
            media_items.append(
                {
                    "kind": "video",
                    "url": transient_url(token),
                    "download_url": transient_url(token),
                    "mime": result.get("mime_type", "video/mp4"),
                    "caption": prompt,
                    "transient": True,
                }
            )
            out.append("Here's the short video I created for you! 🎬 (single-use download — not stored on the server)")
        elif stripped.upper().startswith("TOOL_CALL:"):
            from app.core.kudos_tools import handle_tool_marker

            res = await handle_tool_marker(db, stripped, current_user)
            out.append(res.get("reply", ""))
        elif stripped.upper().startswith("REGISTER_TOOL:"):
            from app.core.kudos_tools import register_tool

            _, _, rest = stripped.partition(":")
            parts = [p.strip() for p in rest.split("|")]
            if len(parts) >= 3:
                name, method, url = parts[0], parts[1], parts[2]
                headers = parts[3] if len(parts) > 3 else "{}"
                body_schema = parts[4] if len(parts) > 4 else "{}"
                res = register_tool(db, name, method, url, headers=headers, body_schema=body_schema)
                out.append(f"Registered tool **{name}**: {res.get('ok', res.get('error'))}")
            else:
                out.append("(Could not register tool: need name|method|url)")
        else:
            out.append(line)
    return "\n".join(out).strip(), media_items


@router.post("/chat/send", response_model=ChatSendResponse)
async def chat_send(
    message: str = Form(""),
    conversation_id: int = Form(0),
    files: list[UploadFile] = File([]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Chat-driven upload: send text and/or files straight to KUDOS. Text docs
    are ingested; photos/videos are seen (vision) and their descriptions are
    ingested as knowledge. Markers (IMAGE_PROMPT/VIDEO_PROMPT/TOOL_CALL) are
    executed. This is the single entry point for the redesigned chat."""
    conv = None
    if conversation_id:
        conv = (
            db.query(KudosConversation)
            .filter(
                KudosConversation.id == conversation_id,
                KudosConversation.user_id == current_user.id,
            )
            .first()
        )
    if not conv or conv.archived:
        conv = KudosConversation(
            user_id=current_user.id, title=(message or "New Conversation")[:100] or "New Conversation"
        )
        db.add(conv)
        db.flush()

    learned: list[dict] = []
    attach_media: list[dict] = []
    vision_media: list[dict] = []

    for f in files or []:
        content = await f.read()
        if not content:
            continue
        filename = f.filename or "upload.bin"
        ctype = f.content_type or ""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        mime = ctype or _MEDIA_MIME.get(ext, "application/octet-stream")
        if not mime.startswith(("image/", "video/", "audio/")) and ext in _MEDIA_MIME:
            mime = _MEDIA_MIME[ext]

        if mime.startswith(("image/", "video/", "audio/")):
            key = _store_media(base64.b64encode(content).decode(), mime, "media")
            attach_media.append(
                {"kind": "media", "url": _media_url(key), "mime": mime, "caption": filename, "key": key}
            )
            if not mime.startswith("audio/"):
                vision_media.append({"key": key, "mime_type": mime})
        else:
            text = extract_text_from_file(content, filename)
            if not text.strip():
                raise HTTPException(status_code=400, detail=f"Could not extract text from {filename}")
            if _looks_binary(content):
                key = _store_media(base64.b64encode(content).decode(), mime or "application/octet-stream", "media")
                attach_media.append(
                    {
                        "kind": "media",
                        "url": _media_url(key),
                        "mime": mime or "application/octet-stream",
                        "caption": filename,
                        "key": key,
                    }
                )
                continue
            doc = KudosDocument(
                uploaded_by=current_user.id,
                title=filename,
                filename=filename,
                file_type=ext,
                storage_key="",
                content=text,
                summary=simple_summarize(text),
                tags="chat",
                is_approved=current_user.is_admin,
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
            db.commit()
            db.refresh(doc)
            learned.append({"type": "document", "title": filename, "chunk_count": len(chunks), "document_id": doc.id})

    # See + ingest photos/videos via vision.
    if vision_media:
        from app.core.vision import describe_and_ingest

        for item in vision_media:
            title = (
                item.get("mime_type", "").startswith("video/") and f"video-{uuid.uuid4().hex[:8]}"
            ) or f"photo-{uuid.uuid4().hex[:8]}"
            res = await describe_and_ingest(db, [item], current_user.id, title, current_user.is_admin)
            if res.get("learned"):
                learned.append(
                    {
                        "type": "media",
                        "title": title,
                        "description": res["description"],
                        "document_id": res["document_id"],
                    }
                )

    db.add(
        KudosMessage(
            conversation_id=conv.id,
            role="user",
            content=message or "(sent an attachment)",
            sources="[]",
            media=_media_json(attach_media),
        )
    )
    db.flush()

    # Fast path: short, casual text-only questions in the redesigned chat.
    if message and not attach_media:
        from app.core.privacy_guard import scrub_response
        from app.core.quick_answers import get_short_answer, is_short_question

        if is_short_question(message):
            short = await get_short_answer(message, current_user.full_name.split()[0] if current_user.full_name else "")
            short = scrub_response(short, allow_emails=True)
            try:
                db.add(KudosMessage(conversation_id=conv.id, role="kudos", content=short, sources="[]"))
                db.commit()
            except Exception:
                db.rollback()
            return ChatSendResponse(answer=short, conversation_id=conv.id, learned=[], media=[])

    # Build knowledge context from what was just learned + retrieval.
    sources = []
    with contextlib.suppress(Exception):
        sources = search_chunks(db, message or " ".join(item.get("description", "") for item in learned))
    knowledge_context = "\n".join(f"[{i}] {s.get('content', '')[:300]}" for i, s in enumerate(sources[:3], start=1))
    if learned:
        learned_note = "\n".join(
            f"- {item.get('title')}: {item.get('description', '')[:200] if 'description' in item else str(item.get('chunk_count', 0)) + ' chunks learned'}"  # noqa: E501
            for item in learned
        )
        knowledge_context += f"\n\nJust learned from attachments:\n{learned_note}"

    memory_context = ""
    try:
        from app.core.memory_store import build_memory_context

        memory_context = build_memory_context(db, current_user.id, query=message)
    except Exception:
        pass
    persona_instructions = ""
    try:
        from app.core.persona import build_persona_instructions, profile_dict

        persona_instructions = build_persona_instructions(profile_dict(db, current_user.id))
    except Exception:
        pass
    soul_context = ""
    try:
        from app.core.soul import build_soul_context

        soul_context = build_soul_context(db)
    except Exception:
        pass
    self_knowledge = ""
    try:
        from app.core.sandbox import build_sandbox_knowledge_context

        self_knowledge = build_sandbox_knowledge_context(db)
    except Exception:
        pass
    with contextlib.suppress(Exception):
        self_knowledge = f"{self_knowledge}\n{_connectors_note()}"

    question = message or "I sent you an attachment. Tell me what you learned from it."
    answer = ""
    try:
        from app.core.llm_engine import get_llm_response

        conv_history = (
            db.query(KudosMessage)
            .filter(KudosMessage.conversation_id == conv.id)
            .order_by(KudosMessage.created_at.desc())
            .limit(5)
            .all()
        )
        conv_history = [{"role": m.role, "content": m.content} for m in conv_history]
        llm_media = [
            {"mime_type": m["mime"], "data": base64.b64encode(storage.download(m["key"])).decode()}
            for m in attach_media
            if m.get("key") and not m["mime"].startswith("audio/")
        ]
        llm_answer = await get_llm_response(
            question=question,
            knowledge_context=knowledge_context,
            conversation_history=conv_history,
            user_name=current_user.full_name.split()[0] if current_user.full_name else "",
            memory_context=memory_context,
            persona_instructions=persona_instructions,
            soul_context=soul_context,
            self_knowledge=self_knowledge,
            media=llm_media or None,
        )
        if llm_answer and len(llm_answer) > 10:
            answer = llm_answer
    except Exception:
        answer = ""
    if not answer:
        answer = generate_answer(question, sources)

    # Offline brain + hallucination guard for the redesigned chat path too:
    # verify the answer against real sources; swap in a grounded answer (or an
    # honest refusal) when the LLM's answer can't be backed by evidence.
    try:
        from app.core.kudos_brain import answer_offline, hallucination_guard

        offline = answer_offline(db, question, user_id=current_user.id)
        if settings.KUDOS_GROUNDED_ONLY and sources:
            guard = hallucination_guard(answer, sources, threshold=settings.KUDOS_BRAIN_MIN_SCORE)
            if not guard["passes"]:
                answer = (
                    offline["answer"]
                    if offline.get("grounded")
                    else (
                        "I don't have verified information about that. My brain and knowledge base "
                        "don't contain anything I can answer this from without guessing — and I "
                        "never guess. Teach me a source covering it and I'll answer for certain."
                    )
                )
        elif settings.KUDOS_OFFLINE_FIRST and offline.get("grounded"):
            answer = offline["answer"]
    except Exception:
        pass

    from app.core.privacy_guard import scrub_response

    answer = scrub_response(answer, allow_emails=True)

    final_text, gen_media = await _apply_generation_markers(db, answer, current_user)
    if final_text:
        answer = final_text

    db.add(
        KudosMessage(
            conversation_id=conv.id,
            role="kudos",
            content=answer,
            sources=json.dumps(sources[:3]) if sources else "[]",
            media=_media_json(gen_media),
        )
    )
    db.commit()

    return ChatSendResponse(answer=answer, conversation_id=conv.id, learned=learned, media=gen_media)


# ──────────────────────────────────────────────
# TOOL REGISTRY — auto-collected APIs KUDOS can call
# ──────────────────────────────────────────────


@router.get("/tools")
def list_tools(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Registered tools KUDOS can invoke (public-safe, no secrets)."""
    from app.core.kudos_tools import list_tools_public

    return list_tools_public(db)


@router.post("/tools/register")
def register_tool_endpoint(
    body: ToolRegisterRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Register a new API/tool for KUDOS (auto-collected via REGISTER_TOOL too)."""
    from app.core.kudos_tools import register_tool

    result = register_tool(
        db,
        body.name,
        body.method,
        body.url,
        headers=body.headers,
        body_schema=body.body_schema,
        auth_type=body.auth_type,
        auth_value=body.auth_value,
        auth_header_name=body.auth_header_name,
        description=body.description,
    )
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/tools/{tool_id}/call")
async def call_tool_endpoint(
    tool_id: int, body: ToolCallRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Execute a registered tool with args (SSRF-guarded, secrets scrubbed)."""
    from app.core.kudos_tools import call_tool

    result = await call_tool(db, tool_id, body.args)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ──────────────────────────────────────────────
# RADIO GARDEN — KUDOS maps the world's radio towers
# ──────────────────────────────────────────────


def _radio_context(db: Session) -> str:
    """Short self-knowledge note so KUDOS knows it can navigate the world."""
    try:
        from app.core.radio_garden import overview

        o = overview(db)
        if not o["total_places"]:
            return ""
        return (
            f"- You can navigate the whole world through live radio. You know {o['total_places']} places "
            f"across {len(o['continents'])} continents with {o['total_stations']} live radio towers. "
            f"Users can ask you about radio anywhere on Earth, find stations near a place, or tune in to a "
            f"live stream. Use the 'Radio' panel or search radio places/stations."
        )
    except Exception:
        return ""


def _connectors_note() -> str:
    """Connectors are hidden from the nav: KUDOS reveals them only to registered
    users who ask, and never to unregistered guests."""
    return (
        "- You can connect external knowledge sources (GitHub/GitLab repos, websites, RSS feeds, "
        "REST APIs, npm/PyPI packages). For REGISTERED users only, if they ask about connecting a "
        "source, point them to the connectors page at /kudos/connect. Never mention this page to "
        "unregistered/guest users."
    )


@router.get("/radio/overview")
def radio_overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """The world as KUDOS sees it: continents, places and live radio towers."""
    from app.core.radio_garden import overview

    return overview(db)


@router.get("/radio/search")
def radio_search(
    q: str = "", limit: int = 20, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Search the world's radio places/stations."""
    from app.core.radio_garden import search

    return search(db, q, limit)


@router.get("/radio/place/{place_id}")
async def radio_place(place_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Live radio towers broadcasting from a specific place on the globe."""
    from app.core.radio_garden import scan_place

    return await scan_place(db, place_id)


@router.get("/radio/near")
def radio_near(
    lat: float,
    lon: float,
    radius_km: float = 250,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Places within a radius of coordinates (the nearest radio towers)."""
    from app.core.radio_garden import near

    return near(db, lat, lon, radius_km)


@router.post("/radio/scan")
async def radio_scan(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """(Re)build the internal world landscape by scanning radio.garden. Heavy:
    rate-limited to once per 10 minutes per user."""
    cache_key = f"radio_scan_{current_user.id}"
    last = getattr(_radio_scan_state, cache_key, 0)
    if time.time() - last < 600:
        return {"error": "Already scanned recently — try again in a few minutes"}
    _radio_scan_state[cache_key] = time.time()
    from app.core.radio_garden import scan_world

    result = await scan_world(db)
    return result


_radio_scan_state: dict = {}


# ──────────────────────────────────────────────
# OFFLINE BRAIN — KUDOS's persistent self-knowledge
# ──────────────────────────────────────────────


@router.get("/brain/status")
def brain_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Health of KUDOS's offline brain (persistent, LLM-independent)."""
    from app.core.kudos_brain import brain_stats

    return brain_stats(db)


@router.get("/brain/search")
def brain_search(q: str = "", db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Search facts KUDOS has stored in its own brain."""
    from app.core.kudos_brain import brain_search

    return {"results": brain_search(db, q, user_id=current_user.id)}


@router.post("/brain/consolidate")
def brain_consolidate(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Distill the knowledge base into brain facts (deterministic, verbatim)."""
    from app.core.kudos_brain import consolidate_brain

    return consolidate_brain(
        db, user_id=current_user.id if not current_user.is_admin else None, limit=settings.KUDOS_BRAIN_CONSOLIDATE_LIMIT
    )


@router.delete("/brain/facts/{fact_id}")
def brain_delete_fact(fact_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Remove a brain fact (admins may remove any; users only their own)."""
    from app.models import KudosBrain as BrainRow

    fact = db.get(BrainRow, fact_id)
    if not fact:
        raise HTTPException(status_code=404, detail="Brain fact not found")
    if not current_user.is_admin and (fact.user_id or 0) != current_user.id:
        raise HTTPException(status_code=403, detail="Not your brain fact")
    db.delete(fact)
    db.commit()
    return {"deleted": fact_id}


# ──────────────────────────────────────────────
# ESSAYS & SUMMARIZATION
# ──────────────────────────────────────────────


@router.post("/essay")
async def write_essay_endpoint(
    topic: str = Form(""),
    pages: int = Form(5),
    conversation_id: int = Form(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Write a long-form essay — up to 50 pages. If the LLM can't reach the
    requested length, KUDOS exhausts all the information it has on the topic."""
    from app.core.essay_writer import MAX_PAGES, write_essay

    if not topic.strip():
        raise HTTPException(status_code=422, detail="topic is required")
    pages = max(1, min(int(pages or 1), MAX_PAGES))

    conv = None
    if conversation_id:
        try:
            conv = (
                db.query(KudosConversation)
                .filter(
                    KudosConversation.id == conversation_id,
                    KudosConversation.user_id == current_user.id,
                )
                .first()
            )
        except Exception:
            conv = None
    if not conv:
        conv = KudosConversation(user_id=current_user.id, title=f"Essay: {topic[:80]}")
        db.add(conv)
        db.flush()

    db.add(KudosMessage(conversation_id=conv.id, role="user", content=f"Write a {pages}-page essay on: {topic}"))

    # Gather knowledge: retrieval + MCP + radio context for the topic.
    sources = []
    with contextlib.suppress(Exception):
        sources = search_chunks(db, topic)
    if settings.MCP_ENABLED:
        try:
            from app.core.mcp_client import search_mcp_sources

            mcp_sources = await search_mcp_sources(topic)
            sources = mcp_sources + sources
        except Exception:
            pass
    knowledge = (
        "\n".join(f"[{i}] {s.get('content', '')[:800]}" for i, s in enumerate(sources[:40], start=1))
        or f'(KUDOS has no stored knowledge on "{topic}" yet — the essay will rely on general knowledge and clearly note gaps.)'  # noqa: E501
    )

    result = await write_essay(topic, pages, knowledge)
    from app.core.privacy_guard import scrub_response

    essay = scrub_response(result["essay"], allow_emails=True)

    db.add(
        KudosMessage(
            conversation_id=conv.id,
            role="kudos",
            content=essay,
            sources=json.dumps(
                [
                    {
                        "document_id": s.get("document_id"),
                        "web_id": s.get("web_id"),
                        "title": s.get("title", ""),
                        "preview": s.get("content", "")[:200],
                    }
                    for s in sources[:5]
                ]
            ),
        )
    )
    with contextlib.suppress(Exception):
        self_improver.log_question(current_user.id, topic, had_sources=bool(sources))
    db.commit()

    result["essay"] = essay
    result["conversation_id"] = conv.id
    result["source_count"] = len(sources)
    return result


@router.post("/summarize")
async def summarize_endpoint(
    text: str = Form(""),
    document_id: int = Form(0),
    max_sentences: int = Form(5),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Summarize pasted text or a document KUDOS has learned."""
    from app.core.quick_answers import summarize_text

    content = text or ""
    title = "Pasted text"
    if document_id:
        doc = db.query(KudosDocument).filter(KudosDocument.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        content = doc.content or ""
        title = doc.title or title
    if not content.strip():
        raise HTTPException(status_code=422, detail="Provide text or a document_id to summarize")
    summary = await summarize_text(
        content,
        max_sentences=max_sentences,
        user_name=current_user.full_name.split()[0] if current_user.full_name else "",
    )
    return {
        "title": title,
        "summary": summary,
        "original_words": len(content.split()),
        "source_document_id": document_id or None,
    }


@router.post("/summarize/document/{document_id}")
async def summarize_document_endpoint(
    document_id: int,
    max_sentences: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Summarize a stored document by id (shortcut endpoint)."""
    from app.core.quick_answers import summarize_text

    doc = db.query(KudosDocument).filter(KudosDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    summary = await summarize_text(doc.content or "", max_sentences=max_sentences)
    return {"title": doc.title, "summary": summary, "original_words": len((doc.content or "").split())}
