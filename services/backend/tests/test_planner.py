"""
Digital Campus - Planner API Tests
Calendar events, study goals, notifications.
"""
from fastapi.testclient import TestClient

from app.main import app
from app.models import User
from app.models_extended import Notification
from tests.conftest import TestSessionLocal, login, register_user

client = TestClient(app)

ALICE_EMAIL = "planner-alice@test.c"
BOB_EMAIL = "planner-bob@test.c"
PASSWORD = "pass1234"

H_ALICE = {}
H_BOB = {}


def setup_module():
    register_user(client, ALICE_EMAIL, PASSWORD, "Planner Alice")
    register_user(client, BOB_EMAIL, PASSWORD, "Planner Bob")
    H_ALICE.update(login(client, ALICE_EMAIL, PASSWORD))
    H_BOB.update(login(client, BOB_EMAIL, PASSWORD))


# === Calendar ===

def test_calendar_event_lifecycle():
    r = client.post(
        "/api/v1/planner/calendar",
        json={"title": "Study session", "start_time": "2026-09-01T09:00:00", "end_time": "2026-09-01T10:00:00"},
        headers=H_ALICE,
    )
    assert r.status_code == 201, r.text
    eid = r.json()["id"]

    r = client.get("/api/v1/planner/calendar", headers=H_ALICE)
    assert r.status_code == 200 and len(r.json()) == 1

    r = client.get("/api/v1/planner/calendar?start=2026-09-01T00:00:00&end=2026-09-01T23:59:59", headers=H_ALICE)
    assert r.status_code == 200 and len(r.json()) == 1

    r = client.get("/api/v1/planner/calendar?start=2026-10-01T00:00:00", headers=H_ALICE)
    assert r.status_code == 200 and len(r.json()) == 0

    # Bob cannot delete Alice's event
    r = client.delete(f"/api/v1/planner/calendar/{eid}", headers=H_BOB)
    assert r.status_code == 404

    r = client.delete(f"/api/v1/planner/calendar/{eid}", headers=H_ALICE)
    assert r.status_code == 204
    assert client.get("/api/v1/planner/calendar", headers=H_ALICE).json() == []


# === Goals ===

def test_goal_progress_and_completion():
    r = client.post(
        "/api/v1/planner/goals",
        json={"title": "Read 3 chapters", "goal_type": "daily", "target_value": 3},
        headers=H_ALICE,
    )
    assert r.status_code == 201, r.text
    gid = r.json()["id"]

    r = client.get("/api/v1/planner/goals", headers=H_ALICE)
    assert any(g["id"] == gid for g in r.json())

    r = client.patch(f"/api/v1/planner/goals/{gid}?increment=1", headers=H_ALICE)
    assert r.status_code == 200 and r.json()["current_value"] == 1

    r = client.patch(f"/api/v1/planner/goals/{gid}?increment=2", headers=H_ALICE)
    assert r.json()["is_completed"] is True
    # Capped at target
    r = client.patch(f"/api/v1/planner/goals/{gid}?increment=5", headers=H_ALICE)
    assert r.json()["current_value"] == 3

    # Bob cannot update Alice's goal
    r = client.patch(f"/api/v1/planner/goals/{gid}?increment=1", headers=H_BOB)
    assert r.status_code == 404


# === Notifications ===

def _seed_notification(user_email: str, title: str = "System Notice", read: bool = False) -> int:
    db = TestSessionLocal()
    try:
        user = db.query(User).filter(User.email == user_email).first()
        n = Notification(user_id=user.id, title=title, message="hello", notification_type="info", is_read=read)
        db.add(n)
        db.commit()
        return n.id
    finally:
        db.close()


def test_notifications_lifecycle():
    unread_id = _seed_notification(ALICE_EMAIL, "Unread Notice")
    _seed_notification(ALICE_EMAIL, "Old Notice", read=True)

    r = client.get("/api/v1/planner/notifications", headers=H_ALICE)
    assert r.status_code == 200 and len(r.json()) == 2

    r = client.get("/api/v1/planner/notifications?unread_only=true", headers=H_ALICE)
    assert r.status_code == 200 and len(r.json()) == 1
    assert r.json()[0]["title"] == "Unread Notice"

    r = client.patch(f"/api/v1/planner/notifications/{unread_id}/read", headers=H_ALICE)
    assert r.status_code == 200 and r.json()["status"] == "read"

    r = client.get("/api/v1/planner/notifications?unread_only=true", headers=H_ALICE)
    assert r.json() == []

    # Bob is unaffected by Alice's read-all
    r = client.post("/api/v1/planner/notifications/read-all", headers=H_BOB)
    assert r.status_code == 200 and r.json()["status"] == "all_read"
