"""
Approval-gated registration (REQUIRE_APPROVAL) tests.

The flag is toggled per-test and always restored, so the default test suite
behaviour (open registration) is unaffected.
"""
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from tests.conftest import login, promote_to_admin, register_user

client = TestClient(app)


@pytest.fixture
def approval_mode():
    original = settings.REQUIRE_APPROVAL
    settings.REQUIRE_APPROVAL = True
    yield
    settings.REQUIRE_APPROVAL = original


def test_register_pending_when_approval_required(approval_mode):
    res = client.post(
        "/api/v1/auth/register",
        json={"email": "pending@campus.edu", "full_name": "Pending User", "password": "pass1234"},
    )
    assert res.status_code == 201
    assert res.json()["is_approved"] is False


def test_pending_user_cannot_login(approval_mode):
    register_user(client, "pending2@campus.edu", auto_approve=False)
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "pending2@campus.edu", "password": "pass1234"},
    )
    assert res.status_code == 403
    assert "approval" in res.json()["detail"].lower()


def test_superadmin_approval_unlocks_login(approval_mode):
    register_user(client, "pending3@campus.edu", auto_approve=False)
    register_user(client, "gate-admin@campus.edu")
    promote_to_admin("gate-admin@campus.edu")
    headers = login(client, "gate-admin@campus.edu")

    pending = client.get("/api/v1/superadmin/users/pending", headers=headers)
    assert pending.status_code == 200
    emails = [u["email"] for u in pending.json()]
    assert "pending3@campus.edu" in emails
    uid = next(u["id"] for u in pending.json() if u["email"] == "pending3@campus.edu")

    ok = client.post(f"/api/v1/superadmin/users/{uid}/approve", headers=headers)
    assert ok.status_code == 200

    res = client.post(
        "/api/v1/auth/login",
        json={"email": "pending3@campus.edu", "password": "pass1234"},
    )
    assert res.status_code == 200