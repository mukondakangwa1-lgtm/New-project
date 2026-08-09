"""
Public guest chat tests: anonymous KUDOS ask without login,
guest conversation persistence, rate limiting, and input validation.
"""
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TestSessionLocal

client = TestClient(app)

GUEST_EMAIL = "guest@campus.local"


def _seed_sources():
    """Create an approved document with two chunks in the test DB."""
    from app.models import KudosChunk, KudosDocument, User

    db = TestSessionLocal()
    try:
        if db.query(User).filter(User.id == 1).first() is None:
            db.add(User(id=1, email="seed@campus.edu", full_name="Seed",
                        hashed_password="!", is_approved=True))
            db.commit()
        doc = KudosDocument(
            title="Vector DB Guide",
            uploaded_by=1,
            filename="vectors.pdf",
            file_type="pdf",
            content="pgvector adds semantic search on top of Postgres. "
                    "Cosine distance ranks results by meaning similarity.",
            is_approved=True,
            is_active=True,
        )
        db.add(doc)
        db.flush()
        db.add(KudosChunk(document_id=doc.id, chunk_index=0,
                          content="pgvector adds semantic search on top of Postgres."))
        db.add(KudosChunk(document_id=doc.id, chunk_index=1,
                          content="Cosine distance ranks results by meaning similarity."))
        db.commit()
        return doc.id
    finally:
        db.close()


def _guest_cleanup():
    from app.models import (
        KudosChunk,
        KudosConversation,
        KudosDocument,
        KudosMessage,
        User,
    )

    db = TestSessionLocal()
    try:
        for msg in db.query(KudosMessage).all():
            db.delete(msg)
        for conv in db.query(KudosConversation).all():
            db.delete(conv)
        for doc in db.query(KudosDocument).all():
            for ch in db.query(KudosChunk).filter(KudosChunk.document_id == doc.id).all():
                db.delete(ch)
            db.delete(doc)
        db.query(User).filter(User.email == GUEST_EMAIL).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def test_guest_ask_works_without_login(monkeypatch):
    _seed_sources()
    try:
        async def fake_llm(**kwargs):
            return {"response": ("Vector databases index text by meaning. [1] "
                                 "Cosine distance ranks the results.")}

        monkeypatch.setattr("app.core.llm_engine.get_llm_response", fake_llm)

        r = client.post(
            "/api/v1/kudos/guest/ask",
            json={"question": "how do vector databases work", "guest_id": "test-guest-abc-123"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["conversation_id"] is not None
        assert "answer" in data and len(data["answer"]) > 10
        assert data["sources"], "expected cited sources"
        assert data["sources"][0]["citation"] == 1
    finally:
        _guest_cleanup()


def test_guest_messages_returns_welcome_and_history(monkeypatch):
    try:
        async def fake_llm(**kwargs):
            return {"response": "Sure — vector search ranks by similarity. [1]"}

        monkeypatch.setattr("app.core.llm_engine.get_llm_response", fake_llm)

        guest_id = "guest-history-xyz"
        r = client.post("/api/v1/kudos/guest/ask",
                        json={"question": "what is embedding", "guest_id": guest_id})
        assert r.status_code == 200, r.text

        h = client.get(f"/api/v1/kudos/guest/messages?guest_id={guest_id}")
        assert h.status_code == 200
        msgs = h.json()
        assert len(msgs) >= 2
        assert msgs[0]["role"] == "kudos"
        assert "Welcome" in msgs[0]["content"] or "👋" in msgs[0]["content"]
        assert msgs[1]["role"] == "user"
        assert msgs[-1]["role"] == "kudos"

        # unknown guest → empty history, not an error
        h2 = client.get("/api/v1/kudos/guest/messages?guest_id=never-seen-123")
        assert h2.status_code == 200 and h2.json() == []
    finally:
        _guest_cleanup()


def test_guest_ask_rejects_short_guest_id():
    r = client.post("/api/v1/kudos/guest/ask",
                    json={"question": "hi", "guest_id": "short"})
    assert r.status_code == 422


def test_guest_rate_limit(monkeypatch):
    try:
        async def fake_llm(**kwargs):
            return {"response": "ok."}

        monkeypatch.setattr("app.core.llm_engine.get_llm_response", fake_llm)

        guest_id = "guest-rate-limit"
        for _ in range(15):
            r = client.post("/api/v1/kudos/guest/ask",
                            json={"question": "hi", "guest_id": guest_id})
            assert r.status_code == 200, r.text
        r = client.post("/api/v1/kudos/guest/ask",
                        json={"question": "too many", "guest_id": guest_id})
        assert r.status_code == 429
    finally:
        _guest_cleanup()