"""
Authorization / object-level access control tests.

Each test uses its own TestClient and unique emails so shared cookies and
users cannot leak across tests. Users are created via the API and promoted
to admin directly in the test DB where required.
"""
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import login, promote_to_admin, register_user

_seq = 0


def _unique(base: str) -> str:
    """Return a fresh unique email (test DB is shared across tests)."""
    global _seq
    _seq += 1
    return f"{base}-{_seq}@campus.edu"


def _fresh() -> TestClient:
    return TestClient(app)


def _student(c: TestClient) -> tuple[dict, dict, str]:
    """Register a student; returns (user json, auth headers, email)."""
    email = _unique("student")
    user = register_user(c, email)
    return user, login(c, email), email


def _other(c: TestClient) -> tuple[dict, dict, str]:
    email = _unique("other")
    user = register_user(c, email)
    return user, login(c, email), email


def _admin(c: TestClient) -> dict:
    """Register a fresh admin user and promote them; returns auth headers."""
    email = _unique("admin")
    register_user(c, email)
    promote_to_admin(email)
    return login(c, email)


# ────────────────────────────── Courses ──────────────────────────────


def test_course_catalog_requires_auth():
    r = _fresh().get("/api/v1/courses/")
    assert r.status_code == 401


def test_create_course_admin_only():
    c = _fresh()
    _, student_headers, _ = _student(c)
    course = {
        "title": "Authz Course",
        "code": "AUTHZ-101",
        "description": "Course for authorization tests",
    }
    r = c.post("/api/v1/courses/", json=course, headers=student_headers)
    assert r.status_code == 403


def _create_course_as_admin(c, headers) -> dict:
    r = c.post(
        "/api/v1/courses/",
        json={"title": "Authz Course", "code": f"AUTHZ-{_seq}", "description": "x"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _enroll(c, headers, course_id: int, student_id: int) -> dict:
    r = c.post(
        "/api/v1/courses/enroll",
        json={"course_id": course_id, "student_id": student_id},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_enroll_only_self_or_admin():
    c = _fresh()
    student, student_headers, _ = _student(c)
    other, _, _ = _other(c)
    admin_headers = _admin(c)
    course = _create_course_as_admin(c, admin_headers)

    # A student cannot enroll someone else
    r = c.post(
        "/api/v1/courses/enroll",
        json={"course_id": course["id"], "student_id": other["id"]},
        headers=student_headers,
    )
    assert r.status_code == 403

    # But may enroll themselves
    self_enroll = _enroll(c, student_headers, course["id"], student["id"])
    assert self_enroll["student_id"] == student["id"]

    # And an admin may enroll anyone
    admin_enroll = _enroll(c, admin_headers, course["id"], other["id"])
    assert admin_enroll["student_id"] == other["id"]


def test_enrollments_require_membership_or_admin():
    c = _fresh()
    _, _, _ = _student(c)
    _, other_headers, _ = _other(c)
    admin_headers = _admin(c)
    course = _create_course_as_admin(c, admin_headers)

    # Unenrolled student cannot list enrollments
    r = c.get(f"/api/v1/courses/enrollments/{course['id']}", headers=other_headers)
    assert r.status_code == 403

    # Admin can
    r = c.get(f"/api/v1/courses/enrollments/{course['id']}", headers=admin_headers)
    assert r.status_code == 200


# ────────────────────────────── Assignments ──────────────────────────────


def _create_assignment(c, admin_headers, course_id: int) -> dict:
    r = c.post(
        "/api/v1/academic/assignments",
        json={
            "course_id": course_id,
            "title": "Authz Assignment",
            "due_date": "2026-12-31T23:59:00Z",
        },
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_assignments_require_enrollment():
    c = _fresh()
    student, student_headers, _ = _student(c)
    _, other_headers, _ = _other(c)
    admin_headers = _admin(c)
    course = _create_course_as_admin(c, admin_headers)
    assignment = _create_assignment(c, admin_headers, course["id"])

    # Unenrolled user cannot list the course's assignments
    r = c.get(f"/api/v1/academic/assignments?course_id={course['id']}", headers=other_headers)
    assert r.status_code == 403

    # Enrolled student can
    _enroll(c, student_headers, course["id"], student["id"])
    r = c.get(f"/api/v1/academic/assignments?course_id={course['id']}", headers=student_headers)
    assert r.status_code == 200

    # Unenrolled user cannot submit
    r = c.post(
        f"/api/v1/academic/assignments/{assignment['id']}/submit",
        json={"content": "not enrolled"},
        headers=other_headers,
    )
    assert r.status_code == 403

    # Enrolled student can submit
    r = c.post(
        f"/api/v1/academic/assignments/{assignment['id']}/submit",
        json={"content": "my submission"},
        headers=student_headers,
    )
    assert r.status_code == 201


# ────────────────────────────── Users ──────────────────────────────


def test_user_list_admin_only():
    c = _fresh()
    _, student_headers, _ = _student(c)
    r = c.get("/api/v1/users/", headers=student_headers)
    assert r.status_code == 403

    admin_headers = _admin(c)
    r = c.get("/api/v1/users/", headers=admin_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_user_profile_only_self_or_admin():
    c = _fresh()
    me, me_headers, _ = _student(c)
    other, _, _ = _other(c)

    # Cannot view another user's profile
    r = c.get(f"/api/v1/users/{other['id']}", headers=me_headers)
    assert r.status_code == 403

    # Can view own profile
    own = c.get(f"/api/v1/users/{me['id']}", headers=me_headers)
    assert own.status_code == 200

    admin_headers = _admin(c)
    r = c.get(f"/api/v1/users/{other['id']}", headers=admin_headers)
    assert r.status_code == 200
