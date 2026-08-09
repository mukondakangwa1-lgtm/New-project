"""
Digital Campus - Admin Analytics API Tests
Admin-only dashboard endpoints and role enforcement.
"""
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import login, promote_to_admin, register_user

client = TestClient(app)

STUDENT_EMAIL = "an-student@test.c"
ADMIN_EMAIL = "an-admin@test.c"
PASSWORD = "pass1234"

H_STUDENT = {}
H_ADMIN = {}


def setup_module():
    register_user(client, STUDENT_EMAIL, PASSWORD, "An Student")
    register_user(client, ADMIN_EMAIL, PASSWORD, "An Admin")
    promote_to_admin(ADMIN_EMAIL)
    H_STUDENT.update(login(client, STUDENT_EMAIL, PASSWORD))
    H_ADMIN.update(login(client, ADMIN_EMAIL, PASSWORD))


def test_analytics_requires_admin():
    from fastapi.testclient import TestClient as _TestClient

    for path in ("/api/v1/admin/analytics/overview", "/api/v1/admin/analytics/attendance-trends",
                 "/api/v1/admin/analytics/top-courses", "/api/v1/admin/analytics/engagement"):
        r = client.get(path, headers=H_STUDENT)
        assert r.status_code == 403, path
        # Fresh client — the shared one carries an admin session cookie
        r = _TestClient(app).get(path)
        assert r.status_code == 401, path


def test_analytics_overview():
    r = client.get("/api/v1/admin/analytics/overview", headers=H_ADMIN)
    assert r.status_code == 200, r.text
    data = r.json()
    assert set(data.keys()) == {"users", "courses", "attendance", "assignments", "exams", "kudos"}
    assert data["users"]["total"] >= 2
    assert data["users"]["admins"] >= 1
    assert data["users"]["students"] >= 1


def test_analytics_attendance_trends():
    r = client.get("/api/v1/admin/analytics/attendance-trends?days=7", headers=H_ADMIN)
    assert r.status_code == 200 and r.json()["days"] == 7
    assert isinstance(r.json()["data"], list)


def test_analytics_top_courses():
    r = client.get("/api/v1/admin/analytics/top-courses?limit=5", headers=H_ADMIN)
    assert r.status_code == 200 and isinstance(r.json(), list)
    if r.json():
        assert set(r.json()[0].keys()) == {"course_id", "code", "title", "enrollments"}


def test_analytics_engagement():
    r = client.get("/api/v1/admin/analytics/engagement", headers=H_ADMIN)
    assert r.status_code == 200
    data = r.json()
    assert data["active_users"] >= 2
    assert "engagement_rate" in data


def test_superadmin_dashboard_includes_storage():
    """The superadmin dashboard reports storage usage + DB size."""
    r = client.get("/api/v1/superadmin/dashboard", headers=H_ADMIN)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "platform" in data and "users" in data["platform"]
    storage = data.get("storage", {})
    assert "usage" in storage and "db_size_bytes" in storage
    usage = storage["usage"]
    assert "total_bytes" in usage and "total_objects" in usage
    assert "by_prefix" in usage
    assert set(usage["by_prefix"].keys()) == {"audio/", "docs/", "avatars/", "backups/"}
    assert storage["db_size_bytes"] >= 0


def test_storage_usage_local_backend_roundtrip():
    """storage.usage() measures objects written through the storage layer."""
    from app.core import storage as s

    key = s.new_key("docs/")
    s.upload_bytes(key, b"x" * 2048)
    try:
        usage = s.usage()
        assert usage["backend"] in ("minio", "local")
        assert usage["total_objects"] >= 1
        assert usage["total_bytes"] >= 2048
        assert usage["by_prefix"]["docs/"]["objects"] >= 1
        assert usage["by_prefix"]["docs/"]["bytes"] >= 2048
    finally:
        try:
            s.delete(key)
        except Exception:
            pass
