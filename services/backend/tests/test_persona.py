"""
Personal KUDOS tests: profile API, persona instructions, ask-flow wiring.
"""
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TestSessionLocal, login, register_user

client = TestClient(app)

EMAIL = "persona_tester@campus.edu"


def _setup():
    try:
        register_user(client, EMAIL)
    except AssertionError:
        pass
    return login(client, EMAIL)


def _profile_row():
    from app.models import User, UserProfile

    db = TestSessionLocal()
    try:
        user = db.query(User).filter(User.email == EMAIL).first()
        return db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    finally:
        db.close()


def test_default_profile_and_update():
    headers = _setup()
    r = client.get("/api/v1/kudos/profile", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"tone": "friendly", "verbosity": "normal",
                        "emoji_enabled": False, "interests": [], "greeting": ""}
    # no row persisted for pure defaults
    assert _profile_row() is None

    r = client.put(
        "/api/v1/kudos/profile",
        json={
            "tone": "detailed",
            "verbosity": "brief",
            "emoji_enabled": True,
            "interests": ["physics", "fitness"],
            "greeting": "Hey champ",
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["tone"] == "detailed"
    assert r.json()["verbosity"] == "brief"
    assert r.json()["emoji_enabled"] is True
    assert r.json()["interests"] == ["physics", "fitness"]
    assert r.json()["greeting"] == "Hey champ"
    assert _profile_row() is not None


def test_profile_validation():
    headers = _setup()
    r = client.put("/api/v1/kudos/profile", json={"tone": "shouty"}, headers=headers)
    assert r.status_code == 400
    r = client.put("/api/v1/kudos/profile", json={"verbosity": "shouty"}, headers=headers)
    assert r.status_code == 400


def test_profile_reset():
    headers = _setup()
    client.put("/api/v1/kudos/profile", json={"tone": "formal"}, headers=headers)
    r = client.delete("/api/v1/kudos/profile", headers=headers)
    assert r.status_code == 200
    assert r.json()["tone"] == "friendly"
    assert _profile_row() is None


def test_profile_isolation():
    headers_b = _setup_other("persona_b@campus.edu")
    headers_a = _setup()
    client.put("/api/v1/kudos/profile", json={"tone": "formal"}, headers=headers_a)
    r = client.get("/api/v1/kudos/profile", headers=headers_b)
    assert r.json()["tone"] == "friendly"


def _setup_other(email: str):
    try:
        register_user(client, email)
    except AssertionError:
        pass
    return login(client, email)


def test_persona_instructions_builder():
    from app.core.persona import build_persona_instructions, profile_dict, DEFAULT_PROFILE

    from app.models import User

    db = TestSessionLocal()
    try:
        user = db.query(User).filter(User.email == EMAIL).first()
        effective = profile_dict(db, user.id)
        block = build_persona_instructions(effective)
        assert "TONE" in block and "Do not use emoji" in block

        effective["tone"] = "concise"
        effective["verbosity"] = "brief"
        effective["emoji_enabled"] = True
        effective["interests"] = ["robotics"]
        effective["greeting"] = "Yo"
        block = build_persona_instructions(effective)
        assert "like a knowledgeable friend" not in block
        assert "Use light emoji" in block
        assert "robotics" in block
        assert "Yo" in block
        _ = DEFAULT_PROFILE
    finally:
        db.close()


def test_persona_in_system_prompt():
    from app.core.llm_engine import build_human_prompt

    _, system = build_human_prompt(
        question="Hi",
        persona_instructions="- TONE: Be brief and direct; skip pleasantries, lead with the answer.",
    )
    assert "PERSONALIZATION" in system
    assert "Be brief and direct" in system


def test_ask_flow_uses_persona(monkeypatch):
    from app.core import conversation_engine

    captured = {}

    async def fake_llm(**kwargs):
        captured["persona"] = kwargs.get("persona_instructions", "")
        captured["memory"] = kwargs.get("memory_context", "")
        return {"response": "Colorful answer"}

    monkeypatch.setattr("app.core.llm_engine.get_llm_response", fake_llm)
    monkeypatch.setattr(
        conversation_engine, "generate_human_response", lambda *a, **k: "fallback"
    )

    headers = _setup()
    client.put(
        "/api/v1/kudos/profile",
        json={"tone": "formal", "emoji_enabled": True},
        headers=headers,
    )
    r = client.post("/api/v1/kudos/ask", json={"question": "Hello there"}, headers=headers)
    assert r.status_code == 200
    assert "professional" in captured["persona"].lower()
    assert "emoji" in captured["persona"].lower()