"""
Digital Campus - KUDOS Voice Library Tests

Covers the voice library / first-feed signature flow: status fields,
voice listing (stock + library), feeding a recording from a device, adopting
a stock voice as the signature, and the voice-changer error path when no
ElevenLabs key is configured.
"""
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import login, promote_to_admin, register_user

client = TestClient(app)

ADMIN_EMAIL = "voice_admin@campus.edu"
USER_EMAIL = "voice_user@campus.edu"

# A fake audio blob that passes the minimum-size checks in the endpoints.
FAKE_AUDIO = b"\x00\x00\x00\x00" * 8192 + b"KUDOS VOICE SAMPLE"  # ~32 KB


def _admin_headers():
    return login(client, ADMIN_EMAIL)


def _user_headers():
    return login(client, USER_EMAIL)


def test_voice_status_fields():
    register_user(client, ADMIN_EMAIL, full_name="Voice Admin")
    promote_to_admin(ADMIN_EMAIL)
    register_user(client, USER_EMAIL, full_name="Voice User")

    r = client.get("/api/v1/kudos/voice/status", headers=_admin_headers())
    assert r.status_code == 200
    data = r.json()
    assert "signature_state" in data
    assert data["signature_state"] == "none"
    assert "signature_voice" in data
    assert "owner_device_name" in data
    assert "sample_count" in data


def test_voices_list_returns_stock():
    r = client.get("/api/v1/kudos/voice/voices", headers=_user_headers())
    assert r.status_code == 200
    data = r.json()
    assert data["signature_state"] == "none"
    stock = [v for v in data["voices"] if v["kind"] == "stock"]
    assert any(v["provider"] == "openai" for v in stock)
    assert any(v["provider_voice_id"] == "nova" for v in stock)


def test_feed_first_recording_becomes_signature_source():
    r = client.post(
        "/api/v1/kudos/voice/feed",
        headers=_admin_headers(),
        files={"file": ("sample.webm", FAKE_AUDIO, "audio/webm")},
        data={"name": "my-phone"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    # First feed flips the signature state to pending (clone needs a key or
    # more audio — offline test env has neither).
    assert data["signature_state"] in ("pending", "active")
    assert data["sample_count"] >= 1
    assert "message" in data


def test_adopt_stock_voice_as_signature():
    r = client.post(
        "/api/v1/kudos/voice/adopt",
        headers=_admin_headers(),
        json={"voice_id": "nova", "name": "Nova"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["signature_active"] is True
    assert data["signature_state"] == "active"


def test_voice_changer_requires_key():
    r = client.post(
        "/api/v1/kudos/voice/convert",
        headers=_user_headers(),
        files={"file": ("clip.webm", FAKE_AUDIO, "audio/webm")},
        data={"voice_id": ""},
    )
    assert r.status_code == 400
    assert "ElevenLabs" in r.json()["detail"]


def test_convert_requires_auth():
    r = client.post(
        "/api/v1/kudos/voice/convert",
        files={"file": ("clip.webm", FAKE_AUDIO, "audio/webm")},
    )
    assert r.status_code in (401, 403)