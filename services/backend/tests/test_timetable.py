"""
Digital Campus - Timetable & Attendance API Tests
Timetable entries, session generation, check-ins, attendance records.
"""
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import login, promote_to_admin, register_user

client = TestClient(app)

STUDENT_EMAIL = "tt-student@test.c"
ADMIN_EMAIL = "tt-admin@test.c"
PASSWORD = "pass1234"

H_STUDENT = {}
H_ADMIN = {}
COURSE_ID = None
SESSION_ID = None


def setup_module():
    register_user(client, STUDENT_EMAIL, PASSWORD, "TT Student")
    register_user(client, ADMIN_EMAIL, PASSWORD, "TT Admin")
    promote_to_admin(ADMIN_EMAIL)
    H_STUDENT.update(login(client, STUDENT_EMAIL, PASSWORD))
    H_ADMIN.update(login(client, ADMIN_EMAIL, PASSWORD))
    global COURSE_ID, SESSION_ID

    r = client.post(
        "/api/v1/courses/",
        json={"code": "TT101", "title": "Timetable Course", "description": "d", "credits": 3},
        headers=H_ADMIN,
    )
    assert r.status_code == 201, r.text
    COURSE_ID = r.json()["id"]

    # Enroll the student so check-in passes validation
    student_id = client.get("/api/v1/users/me", headers=H_STUDENT).json()["id"]
    r = client.post(
        "/api/v1/courses/enroll",
        json={"course_id": COURSE_ID, "student_id": student_id},
        headers=H_STUDENT,
    )
    assert r.status_code == 201, r.text

    # Admin creates a timetable entry for today's weekday
    today = date.today().weekday()
    r = client.post(
        "/api/v1/register/timetable",
        json={"course_id": COURSE_ID, "day_of_week": today, "start_time": "09:00:00", "end_time": "10:30:00", "room": "A-101"},
        headers=H_ADMIN,
    )
    assert r.status_code == 201, r.text

    # Generate sessions for this week (covers today's weekday)
    monday = date.today() - timedelta(days=today)
    r = client.post(
        "/api/v1/register/sessions/generate",
        json={"start_date": monday.isoformat(), "end_date": (monday + timedelta(days=7)).isoformat(), "course_id": COURSE_ID},
        headers=H_ADMIN,
    )
    assert r.status_code == 200, r.text
    assert r.json()["sessions_created"] >= 1

    # Find today's session for this course
    r = client.get("/api/v1/register/sessions/today", headers=H_STUDENT)
    assert r.status_code == 200, r.text
    session = next(s for s in r.json() if s["course"]["id"] == COURSE_ID)
    SESSION_ID = session["id"]

    # Open it so students can check in
    r = client.patch(
        f"/api/v1/register/sessions/{SESSION_ID}",
        json={"is_open": True},
        headers=H_ADMIN,
    )
    assert r.status_code == 200 and r.json()["is_open"] is True


# === Timetable ===

def test_timetable_entry_admin_only():
    r = client.post(
        "/api/v1/register/timetable",
        json={"course_id": COURSE_ID, "day_of_week": 1, "start_time": "11:00:00", "end_time": "12:00:00"},
        headers=H_STUDENT,
    )
    assert r.status_code == 403


def test_attendance_check_in_flow():
    # Not enrolled user cannot check in
    register_user(client, "tt-intruder@test.c", PASSWORD, "TT Intruder")
    h_intruder = login(client, "tt-intruder@test.c", PASSWORD)
    r = client.post(
        "/api/v1/register/attendance/check-in",
        json={"session_id": SESSION_ID, "status": "present"},
        headers=h_intruder,
    )
    assert r.status_code == 400

    # Student checks in
    r = client.post(
        "/api/v1/register/attendance/check-in",
        json={"session_id": SESSION_ID, "status": "present"},
        headers=H_STUDENT,
    )
    assert r.status_code == 201, r.text

    # Duplicate check-in rejected
    r = client.post(
        "/api/v1/register/attendance/check-in",
        json={"session_id": SESSION_ID, "status": "late"},
        headers=H_STUDENT,
    )
    assert r.status_code == 400

    # My attendance lists the check-in
    r = client.get("/api/v1/register/attendance/my", headers=H_STUDENT)
    assert r.status_code == 200 and len(r.json()) == 1

    # Admin marks the intruder absent
    intruder_id = client.get("/api/v1/users/me", headers=h_intruder).json()["id"]
    r = client.post(
        f"/api/v1/register/attendance/session/{SESSION_ID}/mark",
        json={"student_id": intruder_id, "status": "absent"},
        headers=H_ADMIN,
    )
    assert r.status_code == 201, r.text

    r = client.get(f"/api/v1/register/attendance/session/{SESSION_ID}", headers=H_ADMIN)
    assert r.status_code == 200 and len(r.json()) == 2

    r = client.get(f"/api/v1/register/attendance/report/{COURSE_ID}", headers=H_STUDENT)
    assert r.status_code == 200 and len(r.json()) == 1  # report covers enrolled students only


def test_session_cancel():
    r = client.patch(f"/api/v1/register/sessions/{SESSION_ID}/cancel", headers=H_ADMIN)
    assert r.status_code == 200 and r.json()["is_cancelled"] is True

    r = client.post(
        "/api/v1/register/attendance/check-in",
        json={"session_id": SESSION_ID, "status": "present"},
        headers=H_STUDENT,
    )
    assert r.status_code == 400  # cancelled
