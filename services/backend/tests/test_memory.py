"""
KUDOS Universal Memory tests: store logic + API + ask-flow integration.
"""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TestSessionLocal, login, register_user

client = TestClient(app)

EMAIL = "user_memory@campus.edu"


def _user_id() -> int:
    db = TestSessionLocal()
    try:
        from app.models import User

        user = db.query(User).filter(User.email == EMAIL).first()
        assert user is not None
        return user.id
    finally:
        db.close()


def _wipe_memories():
    from app.models import KudosMemory

    db = TestSessionLocal()
    try:
        db.query(KudosMemory).filter(KudosMemory.user_id == _user_id()).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _setup():
    try:
        register_user(client, EMAIL)
    except AssertionError:
        pass
    return login(client, EMAIL)


# ──────────────────────────────────────────────
# API
# ──────────────────────────────────────────────

def test_write_and_retrieve_memory():
    headers = _setup()
    r = client.post(
        "/api/v1/kudos/memory",
        json={
            "content": "I prefer React over Vue for frontend",
            "layer": "long_term",
            "kind": "preference",
            "tags": ["study", "preference"],
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    mem = r.json()
    assert mem["layer"] == "long_term"
    assert mem["kind"] == "preference"
    assert mem["tags"] == ["study", "preference"]

    r = client.get("/api/v1/kudos/memory", headers=headers)
    assert r.status_code == 200
    contents = [m["content"] for m in r.json()["memories"]]
    assert any("React" in c for c in contents)
    _wipe_memories()


def test_keyword_retrieval_ranking():
    headers = _setup()
    from app.core.memory_store import write_memory

    db = TestSessionLocal()
    try:
        uid = _user_id()
        write_memory(db, uid, "The campus gym opens at 6am daily", layer="long_term", kind="fact")
        write_memory(db, uid, "I love hiking on weekends", layer="long_term", kind="preference")
    finally:
        db.close()

    r = client.get("/api/v1/kudos/memory?query=gym", headers=headers)
    assert r.status_code == 200
    ranked = [m["content"] for m in r.json()["memories"]]
    assert ranked, "expected at least the gym memory to match"
    assert "gym" in ranked[0]
    assert all("gym" not in c for c in ranked[1:]), "non-matching memories should be filtered"
    _wipe_memories()


def test_memory_validation_errors():
    headers = _setup()
    r = client.post("/api/v1/kudos/memory", json={"content": ""}, headers=headers)
    assert r.status_code == 422

    r = client.post(
        "/api/v1/kudos/memory",
        json={"content": "x", "layer": "bogus_layer"},
        headers=headers,
    )
    assert r.status_code == 400

    r = client.delete("/api/v1/kudos/memory?layer=bogus", headers=headers)
    assert r.status_code == 400


def test_clear_memories():
    headers = _setup()
    client.post(
        "/api/v1/kudos/memory",
        json={"content": "temp memory", "layer": "short_term"},
        headers=headers,
    )
    r = client.delete("/api/v1/kudos/memory", headers=headers)
    assert r.status_code == 200
    assert r.json()["deleted"] >= 1
    r = client.get("/api/v1/kudos/memory", headers=headers)
    assert r.json()["memories"] == []


def test_delete_single_memory():
    headers = _setup()
    mem = client.post(
        "/api/v1/kudos/memory",
        json={"content": "single fact"},
        headers=headers,
    ).json()
    r = client.delete(f"/api/v1/kudos/memory/{mem['id']}", headers=headers)
    assert r.status_code == 200
    r = client.get(f"/api/v1/kudos/memory/{mem['id']}", headers=headers)
    assert r.status_code == 404


# ──────────────────────────────────────────────
# Store logic
# ──────────────────────────────────────────────

def test_expired_short_term_excluded():
    from app.core.memory_store import retrieve_memories, write_memory

    db = TestSessionLocal()
    try:
        uid = _user_id()
        write_memory(
            db, uid, "expired secret fact", layer="short_term",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        found = retrieve_memories(db, uid, query="expired")
        assert all("expired secret fact" not in m.content for m in found)
    finally:
        db.close()
    _wipe_memories()


def test_consolidation_promotes_used_memories():
    from app.core.memory_store import consolidate_memories, write_memory

    db = TestSessionLocal()
    try:
        uid = _user_id()
        mem = write_memory(db, uid, "study group meets every tuesday", layer="short_term")
        mem.access_count = 4
        db.commit()
        promoted = consolidate_memories(db, uid)
        assert promoted == 1
        db.refresh(mem)
        assert mem.layer == "long_term"
        assert mem.expires_at is None
    finally:
        db.close()
    _wipe_memories()


# ──────────────────────────────────────────────
# Ask-flow integration
# ──────────────────────────────────────────────

def test_ask_flow_writes_memory(monkeypatch):
    from app.core import conversation_engine, llm_engine

    async def fake_llm(**kwargs):
        return {"response": "Vector databases index data by meaning."}

    monkeypatch.setattr(llm_engine, "get_llm_response", fake_llm)
    monkeypatch.setattr(conversation_engine, "generate_human_response", lambda *a, **k: "fallback")

    headers = _setup()
    r = client.post(
        "/api/v1/kudos/ask",
        json={"question": "Explain vector databases"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["answer"]) > 10

    db = TestSessionLocal()
    try:
        from app.models import KudosMemory

        memories = db.query(KudosMemory).filter(KudosMemory.user_id == _user_id()).all()
        assert any("vector databases" in m.content for m in memories)
    finally:
        db.close()
    _wipe_memories()


def test_memory_context_in_prompt():
    from app.core.llm_engine import build_human_prompt

    user_prompt, _ = build_human_prompt(
        question="What should I study?",
        memory_context="User memory:\n- [long_term][preference] prefers morning study",
    )
    assert "User memory:" in user_prompt
    assert "prefers morning study" in user_prompt