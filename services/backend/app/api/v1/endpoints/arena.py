"""
Digital Campus - KUDOS Arena AI
Multi-AI orchestration — always responds, never crashes.
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.arena_engine import ARENA_MODES, query_multiple_sources, score_answer, select_best_answer, get_arena_modes
from app.core.kudos_guardian import self_improver
from app.models import KudosConversation, KudosMessage, User
from app.schemas import KudosAskRequest

router = APIRouter()


@router.get("/modes")
def list_arena_modes():
    modes = []
    for key, config in ARENA_MODES.items():
        modes.append({"id": key, "name": config["name"], "description": config["description"], "icon": config["icon"], "sources": config["sources"]})
    return {"modes": modes}


@router.post("/query")
async def arena_query(body: KudosAskRequest, mode: str = "directchat", db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Query KUDOS in Arena mode — always returns, never crashes."""
    try:
        if mode not in ARENA_MODES:
            mode = "directchat"

        # Get or create conversation
        conv = None
        if body.conversation_id:
            try:
                conv = db.query(KudosConversation).filter(
                    KudosConversation.id == body.conversation_id,
                    KudosConversation.user_id == current_user.id,
                ).first()
            except Exception:
                conv = None
        if not conv:
            conv = KudosConversation(user_id=current_user.id, title=f"[{mode}] {body.question[:80]}")
            db.add(conv)
            db.flush()

        db.add(KudosMessage(conversation_id=conv.id, role="user", content=body.question))

        # Query sources
        answers = []
        try:
            answers = await query_multiple_sources(body.question, mode, db, current_user.id)
        except Exception:
            pass

        # Select best answer
        result = {"answer": "", "source": "none", "score": 0, "alternatives": []}
        try:
            if answers:
                result = select_best_answer(body.question, answers)
        except Exception:
            pass

        # Generate human-like answer
        answer = result.get("answer", "")
        if not answer or len(answer) < 20:
            # Fallback to simple answer
            try:
                from app.api.v1.endpoints.kudos import search_chunks, generate_answer
                sources = search_chunks(db, body.question)
                answer = generate_answer(body.question, sources)
                result["source"] = "knowledge_base"
                result["score"] = 0.5
            except Exception:
                answer = f"I couldn't find an answer to '{body.question}' right now. Try teaching me about this topic by uploading a document or web page."

        # Add arena metadata
        if result.get("alternatives"):
            answer += f"\n\n---\n📊 *Arena: Best from {result['source']} (confidence: {result['score']:.0%})*"

        # Save response
        try:
            db.add(KudosMessage(
                conversation_id=conv.id, role="kudos", content=answer,
                sources=json.dumps({"mode": mode, "best": result["source"]}),
            ))
            db.commit()
        except Exception:
            db.rollback()

        try:
            self_improver.log_question(current_user.id, body.question, had_sources=bool(answers))
        except Exception:
            pass

        return {
            "answer": answer, "mode": mode, "mode_name": ARENA_MODES[mode]["name"],
            "mode_icon": ARENA_MODES[mode]["icon"], "best_source": result["source"],
            "confidence": result["score"], "alternatives": result.get("alternatives", []),
            "sources_queried": len(answers), "conversation_id": conv.id,
        }

    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {
            "answer": f"I had trouble processing that. Please try again. ({str(e)[:100]})",
            "mode": mode, "mode_name": "Error", "mode_icon": "⚠️",
            "best_source": "none", "confidence": 0, "alternatives": [],
            "sources_queried": 0, "conversation_id": body.conversation_id or 0,
        }


@router.post("/compare")
async def arena_compare(query: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        answers = await query_multiple_sources(query, "sidebyside", db, current_user.id)
        comparisons = []
        for a in answers:
            s = score_answer(query, a["content"], a["source"])
            comparisons.append({"source": a["source"], "score": round(s, 2), "answer": a["content"][:500], "word_count": len(a["content"].split())})
        comparisons.sort(key=lambda x: -x["score"])
        return {"query": query, "comparisons": comparisons, "best_source": comparisons[0]["source"] if comparisons else "none", "total_sources": len(comparisons)}
    except Exception as e:
        return {"query": query, "comparisons": [], "best_source": "none", "total_sources": 0, "error": str(e)[:200]}


@router.post("/quick-learn")
async def arena_quick_learn(topic: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        from app.models import KudosWebKnowledge
        from app.api.v1.endpoints.kudos import simple_summarize
        answers = await query_multiple_sources(topic, "agent", db, current_user.id)
        stored = 0
        for a in answers:
            if a["content"] and len(a["content"]) > 100:
                db.add(KudosWebKnowledge(
                    url=f"arena://quick-learn/{topic.replace(' ', '-')}",
                    title=f"[Arena Quick-Learn] {topic.title()}"[:255],
                    content=a["content"], summary=simple_summarize(a["content"]),
                    is_approved=current_user.is_admin, learned_by=current_user.id,
                ))
                stored += 1
        db.commit()
        return {"topic": topic, "sources_found": len(answers), "items_stored": stored, "message": f"KUDOS learned about '{topic}' from {stored} sources via Arena"}
    except Exception as e:
        db.rollback()
        return {"topic": topic, "sources_found": 0, "items_stored": 0, "message": f"Error: {str(e)[:200]}"}
