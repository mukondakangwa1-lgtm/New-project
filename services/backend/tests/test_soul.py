"""
KUDOS Soul tests: singleton read, superadmin shaping, reset,
and the voice block used in the system prompt.
"""
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TestSessionLocal, login, promote_to_admin, register_user

client = TestClient(app)

EMAIL = "soul@campus.edu"


def _setup():
    try:
        register_user(client, EMAIL)
    except AssertionError:
        pass
    headers = login(client, EMAIL)
    promote_to_admin(EMAIL)
    return headers


def test_soul_default_readable_by_any_user():
    headers = _setup()
    r = client.get("/api/v1/kudos/soul", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "KUDOS"
    assert isinstance(body["personality"], list) and body["personality"]
    assert isinstance(body["goals"], list)


def test_soul_update_requires_admin():
    headers = login(client, EMAIL)
    promote_to_admin(EMAIL)
    # demote to a normal user for the negative test
    db = TestSessionLocal()
    try:
        from app.models import User

        user = db.query(User).filter(User.email == EMAIL).first()
        user.is_admin = False
        db.commit()
    finally:
        db.close()

    r = client.put(
        "/api/v1/kudos/soul",
        json={"desires": ["to be even better"]},
        headers=headers,
    )
    assert r.status_code == 403
    promote_to_admin(EMAIL)


def test_soul_update_and_voice():
    headers = _setup()
    r = client.put(
        "/api/v1/kudos/soul",
        json={
            "desires": ["to make every student feel heard", "to test code like an agent"],
            "values": ["truth over hype", "code that runs"],
            "goals": [{"goal": "Open a terminal on any device", "status": "active"}],
        },
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "to test code like an agent" in body["desires"]
    assert "code that runs" in body["values"]

    r = client.get("/api/v1/kudos/soul/voice", headers=headers)
    assert r.status_code == 200
    voice = r.json()
    assert "to test code like an agent" in voice
    assert "Open a terminal on any device" in voice


def test_soul_reset_restores_defaults():
    headers = _setup()
    client.put("/api/v1/kudos/soul", json={"desires": ["temporary desire"]}, headers=headers)
    r = client.delete("/api/v1/kudos/soul", headers=headers)
    assert r.status_code == 200
    assert "to keep learning alongside its users" in r.json()["desires"]
