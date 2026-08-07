"""
Digital Campus - Studio API Tests
Speaking sessions + audio, broadcasts, WebRTC signaling, whiteboard, journal.
"""
import json

from fastapi.testclient import TestClient

from app.main import app

# Test DB, override and table lifecycle come from conftest.py
client = TestClient(app)

auth_alice = {}
auth_bob = {}


def setup_module():
    r = client.post("/api/v1/auth/register", json={"email": "a@studio.c", "password": "pass1234", "full_name": "Alice"})
    assert r.status_code == 201, r.text
    auth_alice["id"] = r.json()["id"]
    r = client.post("/api/v1/auth/login", json={"email": "a@studio.c", "password": "pass1234"})
    auth_alice["H"] = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.post("/api/v1/auth/register", json={"email": "b@studio.c", "password": "pass1234", "full_name": "Bob"})
    assert r.status_code == 201, r.text
    auth_bob["id"] = r.json()["id"]
    r = client.post("/api/v1/auth/login", json={"email": "b@studio.c", "password": "pass1234"})
    auth_bob["H"] = {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_speaking_lifecycle_with_audio():
    H = auth_alice["H"]
    r = client.get("/api/v1/studio/speaking/random-prompt?difficulty=beginner")
    assert r.status_code == 200 and r.json()["prompt"]

    r = client.post("/api/v1/studio/speaking/session", headers=H,
                    json={"prompt": "Intro", "duration_seconds": 60, "difficulty": "beginner"})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]

    r = client.post(f"/api/v1/studio/speaking/session/{sid}/complete", headers=H,
                    json={"session_id": sid, "duration_spoken": 12, "self_rating": 4})
    assert r.status_code == 200 and r.json()["status"] == "completed"

    r = client.post(f"/api/v1/studio/speaking/session/{sid}/audio", headers=H,
                    files={"file": ("rec.webm", b"\x1a\x45\xdf\xa3 fake-audio", "audio/webm")})
    assert r.status_code == 200 and r.json()["audio_url"]

    r = client.get(f"/api/v1/studio/speaking/session/{sid}/audio", headers=H)
    assert r.status_code == 200 and b"fake-audio" in r.content

    r = client.get("/api/v1/studio/speaking/history", headers=H)
    assert r.status_code == 200 and r.json()["total_sessions"] == 1


def test_broadcast_lifecycle_and_signaling():
    H, H2 = auth_alice["H"], auth_bob["H"]
    r = client.post("/api/v1/studio/broadcast/start", headers=H, json={"title": "Test FM", "description": "d"})
    assert r.status_code == 201, r.text
    bid = r.json()["id"]

    r = client.get("/api/v1/studio/broadcast/active")
    assert r.status_code == 200 and r.json()["count"] == 1

    r = client.post(f"/api/v1/studio/broadcast/{bid}/join", headers=H2)
    assert r.status_code == 200 and r.json()["broadcast"]["listeners"] == 1

    r = client.post(f"/api/v1/studio/broadcast/{bid}/signal", headers=H2,
                    json={"recipient_id": auth_alice["id"], "signal_type": "offer", "payload": json.dumps({"sdp": "sdp1"})})
    assert r.status_code == 201
    r = client.get(f"/api/v1/studio/broadcast/{bid}/signals", headers=H)
    assert r.status_code == 200 and len(r.json()["signals"]) == 1
    assert r.json()["signals"][0]["signal_type"] == "offer"
    r = client.get(f"/api/v1/studio/broadcast/{bid}/signals", headers=H)
    assert len(r.json()["signals"]) == 0  # consumed

    r = client.post("/api/v1/studio/broadcast/stop", headers=H)
    assert r.status_code == 200 and r.json()["status"] == "ended"


def test_video_call_signaling_and_whiteboard():
    H, H2 = auth_alice["H"], auth_bob["H"]
    r = client.post("/api/v1/studio/calls/create", headers=H, json={"title": "Lecture", "is_group": True})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]

    r = client.post(f"/api/v1/studio/calls/{cid}/join", headers=H2)
    assert r.status_code == 200

    r = client.get(f"/api/v1/studio/calls/{cid}/participants", headers=H2)
    assert len(r.json()["participants"]) == 2, r.text

    r = client.post(f"/api/v1/studio/calls/{cid}/signal", headers=H2,
                    json={"recipient_id": auth_alice["id"], "signal_type": "offer", "payload": json.dumps({"sdp": "x"})})
    assert r.status_code == 201
    r = client.post(f"/api/v1/studio/calls/{cid}/signal", headers=H2,
                    json={"recipient_id": auth_alice["id"], "signal_type": "ice", "payload": json.dumps({"candidate": "c"})})
    assert r.status_code == 201
    r = client.get(f"/api/v1/studio/calls/{cid}/signals", headers=H)
    assert len(r.json()["signals"]) == 2

    r = client.post(f"/api/v1/studio/calls/{cid}/whiteboard/save", headers=H,
                    json={"strokes": [{"color": "#000", "size": 3, "points": [[1, 2]]}]})
    assert r.status_code == 200
    r = client.get(f"/api/v1/studio/calls/{cid}/whiteboard")
    assert len(r.json()["strokes"]) == 1

    r = client.post(f"/api/v1/studio/calls/{cid}/leave", headers=H)
    assert r.status_code == 200
    r = client.post(f"/api/v1/studio/calls/{cid}/leave", headers=H2)
    assert "ended" in r.json()["status"]


def test_journal_blocks():
    H = auth_alice["H"]
    r = client.post("/api/v1/studio/journal/blocks", headers=H,
                    json={"title": "Block1", "block_type": "webpage", "url": "https://example.com"})
    assert r.status_code == 201
    r = client.get("/api/v1/studio/journal/my", headers=H)
    assert r.json()["blocks"][0]["title"] == "Block1"

    r = client.get(f"/api/v1/studio/journal/{auth_alice['id']}")
    assert r.status_code == 200 and len(r.json()["blocks"]) == 1

    r = client.delete(f"/api/v1/studio/journal/blocks/{r.json()['blocks'][0]['id']}", headers=H)
    assert r.status_code == 204
    r = client.get("/api/v1/studio/journal/my", headers=H)
    assert len(r.json()["blocks"]) == 0
