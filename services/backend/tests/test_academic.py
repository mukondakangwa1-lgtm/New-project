"""
Digital Campus - Academic API Tests
Assignments, submissions, grading, notifications, exams and auto-grading.
"""
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import login, promote_to_admin, register_user

client = TestClient(app)

STUDENT_EMAIL = "acad-student@test.c"
ADMIN_EMAIL = "acad-admin@test.c"
PASSWORD = "pass1234"

H_STUDENT = {}
H_ADMIN = {}
COURSE_ID = None


def setup_module():
    register_user(client, STUDENT_EMAIL, PASSWORD, "Ace Student")
    register_user(client, ADMIN_EMAIL, PASSWORD, "Ace Admin")
    promote_to_admin(ADMIN_EMAIL)
    H_STUDENT.update(login(client, STUDENT_EMAIL, PASSWORD))
    H_ADMIN.update(login(client, ADMIN_EMAIL, PASSWORD))
    global COURSE_ID
    r = client.post(
        "/api/v1/courses/",
        json={"code": "ACD101", "title": "Academic Course", "description": "d", "credits": 3},
        headers=H_ADMIN,
    )
    assert r.status_code == 201, r.text
    COURSE_ID = r.json()["id"]


# === Assignments ===

def test_create_assignment_requires_admin():
    r = client.post(
        "/api/v1/academic/assignments",
        json={"course_id": COURSE_ID, "title": "Nope"},
        headers=H_STUDENT,
    )
    assert r.status_code == 403


def test_assignment_lifecycle():
    r = client.post(
        "/api/v1/academic/assignments",
        json={"course_id": COURSE_ID, "title": "Essay 1", "description": "Write it", "max_score": 50},
        headers=H_ADMIN,
    )
    assert r.status_code == 201, r.text
    aid = r.json()["id"]

    r = client.get("/api/v1/academic/assignments", headers=H_STUDENT)
    assert r.status_code == 200
    assert any(a["id"] == aid for a in r.json())

    r = client.get(f"/api/v1/academic/assignments?course_id={COURSE_ID}", headers=H_STUDENT)
    assert r.status_code == 200 and len(r.json()) >= 1

    r = client.post(
        f"/api/v1/academic/assignments/{aid}/submit",
        json={"content": "My essay draft"},
        headers=H_STUDENT,
    )
    assert r.status_code == 201, r.text
    sid = r.json()["id"]

    # Resubmission updates instead of duplicating
    r = client.post(
        f"/api/v1/academic/assignments/{aid}/submit",
        json={"content": "My essay final"},
        headers=H_STUDENT,
    )
    assert r.status_code == 201 and r.json()["id"] == sid
    assert r.json()["content"] == "My essay final"

    # Student cannot list all submissions (admin only)
    r = client.get(f"/api/v1/academic/assignments/{aid}/submissions", headers=H_STUDENT)
    assert r.status_code == 403

    r = client.get(f"/api/v1/academic/assignments/{aid}/submissions", headers=H_ADMIN)
    assert r.status_code == 200 and len(r.json()) == 1

    # Grade the submission -> creates a notification for the student
    r = client.post(
        f"/api/v1/academic/assignments/{aid}/submissions/{sid}/grade",
        json={"score": 45, "feedback": "Great work"},
        headers=H_ADMIN,
    )
    assert r.status_code == 200 and r.json()["status"] == "graded"

    r = client.get("/api/v1/planner/notifications", headers=H_STUDENT)
    assert r.status_code == 200
    assert any(n["title"] == "Assignment Graded" for n in r.json())


def test_grades_my():
    r = client.get("/api/v1/academic/grades/my", headers=H_STUDENT)
    assert r.status_code == 200 and isinstance(r.json(), list)

    r = client.get(f"/api/v1/academic/grades/course/{COURSE_ID}", headers=H_STUDENT)
    assert r.status_code == 403


# === Exams ===

def test_create_exam_requires_admin():
    r = client.post("/api/v1/exams/exams", json={"course_id": COURSE_ID, "title": "Nope"}, headers=H_STUDENT)
    assert r.status_code == 403


def test_exam_lifecycle_and_auto_grading():
    r = client.post(
        "/api/v1/exams/exams",
        json={"course_id": COURSE_ID, "title": "Midterm", "duration_minutes": 30, "max_score": 10},
        headers=H_ADMIN,
    )
    assert r.status_code == 201, r.text
    eid = r.json()["id"]

    q1 = client.post(
        f"/api/v1/exams/exams/{eid}/questions",
        json={"question_text": "2+2?", "question_type": "multiple_choice", "options": '["4","5"]', "correct_answer": "4", "points": 5},
        headers=H_ADMIN,
    )
    assert q1.status_code == 201, q1.text
    q2 = client.post(
        f"/api/v1/exams/exams/{eid}/questions",
        json={"question_text": "Capitals?", "question_type": "short_answer", "correct_answer": "Paris", "points": 5},
        headers=H_ADMIN,
    )
    assert q2.status_code == 201
    q1_id, q2_id = q1.json()["id"], q2.json()["id"]

    # Unpublished exams are not listed publicly
    r = client.get("/api/v1/exams/exams")
    assert all(e["id"] != eid for e in r.json())

    r = client.post(f"/api/v1/exams/exams/{eid}/publish", headers=H_ADMIN)
    assert r.status_code == 200 and r.json()["status"] == "published"

    r = client.get("/api/v1/exams/exams")
    assert any(e["id"] == eid for e in r.json())

    r = client.get(f"/api/v1/exams/exams/{eid}")
    assert r.status_code == 200 and len(r.json()["questions"]) == 2

    # Start attempt and submit: one correct, one wrong
    r = client.post(f"/api/v1/exams/exams/{eid}/start", headers=H_STUDENT)
    assert r.status_code == 201, r.text
    attempt_id = r.json()["id"]

    r = client.post(
        f"/api/v1/exams/exams/{eid}/submit/{attempt_id}",
        json={"answers": {str(q1_id): "4", str(q2_id): "wrong answer"}},
        headers=H_STUDENT,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["score"] == 5 and data["total"] == 10
    assert data["percentage"] == 50.0

    # Grading notification was created
    r = client.get("/api/v1/planner/notifications", headers=H_STUDENT)
    assert any(n["title"] == "Exam Graded" for n in r.json())


def test_start_unpublished_exam_404():
    r = client.post(
        "/api/v1/exams/exams",
        json={"course_id": COURSE_ID, "title": "Hidden"},
        headers=H_ADMIN,
    )
    eid = r.json()["id"]
    r = client.post(f"/api/v1/exams/exams/{eid}/start", headers=H_STUDENT)
    assert r.status_code == 404
