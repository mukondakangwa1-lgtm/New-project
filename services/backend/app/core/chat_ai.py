"""
Digital Campus - Room Chat AI
Brings KUDOS's full intelligence (retrieval + soul + persona + memory +
offline brain + LLM + hallucination guard) into every chat room so the same
KUDOS that answers on the /kudos page is present in private 1:1 chats and
public group chats alike.
"""

import contextlib
import re

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import ChatMessage, ChatRoom, User

# The KUDOS bot's identity. It has a valid users row so ChatMessage.user_id
# (a NOT NULL FK) is satisfied, but a password that can never be logged into.
KUDOS_EMAIL = "kudos@campus.edu"
KUDOS_NAME = "KUDOS"

_MENTION_RE = re.compile(r"(^|\s)(@kudos|!kudos)(\s|[:,.!?]|$)", re.IGNORECASE)


def get_kudos_bot(db: Session) -> User | None:
    """Fetch (and lazily create) the KUDOS bot user row."""
    bot = db.query(User).filter(User.email == KUDOS_EMAIL).first()
    if bot:
        return bot
    bot = User(
        email=KUDOS_EMAIL,
        full_name=KUDOS_NAME,
        hashed_password="!",  # unusable login
        is_admin=False,
        is_approved=True,
        is_active=True,
    )
    try:
        db.add(bot)
        db.commit()
        db.refresh(bot)
        return bot
    except Exception:
        db.rollback()
        return None


def mentions_kudos(content: str) -> bool:
    return bool(_MENTION_RE.search(content))


def should_kudos_reply(db: Session, room: ChatRoom, content: str) -> bool:
    """Private (1:1 / non-group) rooms: KUDOS answers every message.
    Public/group rooms: KUDOS answers only when summoned with @KUDOS / !kudos."""
    if not room.is_group:
        return True
    return mentions_kudos(content)


def _room_history(db: Session, room_id: int, limit: int = 8) -> list[dict]:
    """Recent messages in the room mapped to LLM roles so KUDOS understands
    the group context (who said what) before replying."""
    msgs = (
        db.query(ChatMessage)
        .filter(ChatMessage.room_id == room_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    history: list[dict] = []
    for m in reversed(msgs):
        role = "kudos" if m.user.email == KUDOS_EMAIL else "user"
        who = KUDOS_NAME if role == "kudos" else m.user.full_name or m.user.email
        history.append({"role": "user", "content": f"{who}: {m.content}"})
    return history


async def generate_room_reply(
    db: Session,
    room_id: int,
    sender_user_id: int,
    question: str,
) -> str:
    """The full KUDOS pipeline for a room message. Mirrors the /kudos/ask
    flow: retrieval -> memory -> persona -> soul -> self-knowledge -> LLM,
    with the offline brain + conversation engine as grounded fallbacks and a
    hallucination guard on the final answer."""
    # KUDOS's self-knowledge (sandbox + radio + world map + network + connectors)
    self_knowledge = ""
    with contextlib.suppress(Exception):
        from app.core.sandbox import build_sandbox_knowledge_context

        self_knowledge = build_sandbox_knowledge_context(db)
    for note_fn in (
        _radio_context,
        _network_context,
        _connectors_note,
    ):
        try:
            note = note_fn(db, sender_user_id)
            if note:
                self_knowledge = f"{self_knowledge}\n{note}"
        except Exception:
            pass

    # Retrieval over approved knowledge + MCP sources.
    sources = []
    with contextlib.suppress(Exception):
        from app.api.v1.endpoints.kudos import search_chunks

        sources = search_chunks(db, question)
    if settings.MCP_ENABLED:
        try:
            from app.core.mcp_client import search_mcp_sources

            mcp_sources = await search_mcp_sources(question)
            sources = mcp_sources + sources
        except Exception:
            pass

    knowledge_context = ""
    if sources:
        knowledge_context = "\n".join(
            f"[{i}] {s.get('content', '')[:300]}" for i, s in enumerate(sources[:3], start=1)
        )

    memory_context = ""
    with contextlib.suppress(Exception):
        from app.core.memory_store import build_memory_context

        memory_context = build_memory_context(db, sender_user_id, query=question)

    persona_instructions = ""
    with contextlib.suppress(Exception):
        from app.core.persona import build_persona_instructions, profile_dict

        persona_instructions = build_persona_instructions(profile_dict(db, sender_user_id))

    soul_context = ""
    with contextlib.suppress(Exception):
        from app.core.soul import build_soul_context

        soul_context = build_soul_context(db)

    sender = db.query(User).filter(User.id == sender_user_id).first()
    user_name = (sender.full_name.split()[0] if sender and sender.full_name else "")

    # Offline brain first when configured, and always as a grounded fallback.
    offline = None
    with contextlib.suppress(Exception):
        from app.core.kudos_brain import answer_offline

        if settings.KUDOS_OFFLINE_FIRST:
            offline = answer_offline(db, question, user_id=sender_user_id)

    answer = ""
    if not (offline and offline.get("grounded")):
        with contextlib.suppress(Exception):
            from app.core.llm_engine import get_llm_response

            llm_answer = await get_llm_response(
                question=question,
                knowledge_context=knowledge_context,
                conversation_history=_room_history(db, room_id),
                user_name=user_name,
                memory_context=memory_context,
                persona_instructions=persona_instructions,
                soul_context=soul_context,
                self_knowledge=self_knowledge,
            )
            if llm_answer and len(llm_answer) > 10:
                answer = llm_answer

    if not answer or len(answer) < 10:
        with contextlib.suppress(Exception):
            from app.core.kudos_brain import answer_offline

            if offline is None:
                offline = answer_offline(db, question, user_id=sender_user_id)
            if offline and offline.get("answer"):
                answer = offline["answer"]

    if not answer or len(answer) < 10:
        with contextlib.suppress(Exception):
            from app.core.conversation_engine import generate_human_response

            answer = generate_human_response(query=question, sources=sources, user_name=user_name)

    if not answer or len(answer) < 10:
        from app.api.v1.endpoints.kudos import generate_answer

        answer = generate_answer(question, sources)

    # Hallucination guard: refuse to pass off unverifiable claims as truth.
    if settings.KUDOS_GROUNDED_ONLY and sources:
        try:
            from app.core.kudos_brain import hallucination_guard

            guard = hallucination_guard(answer, sources, threshold=settings.KUDOS_BRAIN_MIN_SCORE)
            if not guard["passes"]:
                if offline and offline.get("answer"):
                    answer = offline["answer"]
        except Exception:
            pass

    with contextlib.suppress(Exception):
        from app.core.privacy_guard import scrub_response

        answer = scrub_response(answer)

    return answer.strip()


def _radio_context(db: Session, user_id: int) -> str:
    try:
        from app.core.radio_garden import overview

        o = overview(db)
        if not o["total_places"]:
            return ""
        return (
            f"- You can navigate the whole world through live radio. You know {o['total_places']} places "
            f"across {len(o['continents'])} continents with {o['total_stations']} live radio towers."
        )
    except Exception:
        return ""


def _network_context(db: Session, user_id: int) -> str:
    try:
        from app.core.network_mesh import network_note

        user = db.query(User).filter(User.id == user_id).first()
        return network_note(db, user) or ""
    except Exception:
        return ""


def _connectors_note(db: Session, user_id: int) -> str:
    return (
        "- You can connect external knowledge sources (GitHub/GitLab repos, websites, RSS feeds, "
        "Google Drive) so users can ask you about their own connected content."
    )
