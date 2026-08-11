"""
Digital Campus - KUDOS Voice Session Tests

Covers the interactive voice-session flow: starting a session (KUDOS greets),
recording a line (stored + transcribed), status/progress fields, cancelling,
and the finalize error path when no ElevenLabs key is configured.
"""
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import login, promote_to_admin, register_user

client = TestClient(app)

ADMIN_EMAIL = "session_admin@campus.edu"

# A fake audio blob that passes the minimum-size checks in the endpoints.
FAKE_AUDIO = b"\x00\x00\x00\x00" * 8192 + b"KUDOS VOICE SESSION"  # ~32 KB


def _admin_headers():
    return login(client, ADMIN_EMAIL)


def _start_session():
    r = client.post("/api/v1/kudos/voice/session/start", headers=_admin_headers())
    assert r.status_code == 200, r.text
    return r.json()


def _turn(session_id: int):
    return client.post(
        "/api/v1/kudos/voice/session/turn",
        headers=_admin_headers(),
        files={"file": ("line.webm", FAKE_AUDIO, "audio/webm")},
        data={"session_id": str(session_id)},
    )


def test_session_start_greets_and_tracks_target():
    register_user(client, ADMIN_EMAIL, full_name="Session Admin")
    promote_to_admin(ADMIN_EMAIL)

    data = _start_session()
    assert data["session_id"] > 0
    assert data["state"] == "active"
    assert data["greeting"]
    assert "voice" in data["greeting"].lower()
    assert data["target_seconds"] >= 30  # raised from 10 to 30
    assert data["total_seconds"] == 0
    assert data["final_ready"] is False


def test_session_turn_stores_line_and_progress():
    data = _start_session()
    sid = data["session_id"]

    r = _turn(sid)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["session_id"] == sid
    assert d["turn_count"] >= 1
    assert d["total_seconds"] >= 1
    assert d["target_seconds"] == data["target_seconds"]
    assert "transcript" in d
    assert "echo_line" in d
    assert "echo" in d
    # Offline test env has no ElevenLabs key: draft voice not cloned.
    assert d["draft_ready"] is False


def test_session_status_reports_latest_active():
    _start_session()
    r = client.get("/api/v1/kudos/voice/session/status", headers=_admin_headers())
    assert r.status_code == 200
    d = r.json()
    assert d["session_id"] is not None
    assert d["state"] == "active"


def test_session_cancel():
    data = _start_session()
    r = client.post(
        "/api/v1/kudos/voice/session/cancel",
        headers=_admin_headers(),
        data={"session_id": str(data["session_id"])},
    )
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "cancelled"

    # A cancelled session rejects further turns.
    r = _turn(data["session_id"])
    assert r.status_code == 422


def test_session_finalize_requires_key():
    data = _start_session()
    _turn(data["session_id"])
    r = client.post(
        "/api/v1/kudos/voice/session/finalize",
        headers=_admin_headers(),
        data={"session_id": str(data["session_id"])},
    )
    assert r.status_code == 400
    assert "ElevenLabs" in r.json()["detail"]


def test_session_endpoints_require_auth():
    r = client.post("/api/v1/kudos/voice/session/start")
    assert r.status_code in (401, 403)
    r = client.post("/api/v1/kudos/voice/session/finalize", data={"session_id": "1"})
    assert r.status_code in (401, 403)
    r = client.post("/api/v1/kudos/voice/session/cancel", data={"session_id": "1"})
    assert r.status_code in (401, 403)
