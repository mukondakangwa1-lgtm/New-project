"""
Shared pytest fixtures: one SQLite test database for the whole session,
single get_db override target.
"""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def _test_db():
    """Create tables once for the session; drop and clean up at the end."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test.db"):
        os.remove("./test.db")


@pytest.fixture(scope="session", autouse=True)
def _local_storage():
    """Pin object storage to the local-disk backend for the whole session.

    The provisioned .env configures STORAGE_BACKEND=minio for deployment; the
    test session must never depend on a running MinIO server.
    """
    from app.core.config import settings

    previous = getattr(settings, "STORAGE_BACKEND", None)
    settings.STORAGE_BACKEND = "local"
    yield
    if previous is not None:
        settings.STORAGE_BACKEND = previous


@pytest.fixture(scope="session", autouse=True)
def _open_registration():
    """Default the suite to open registration (no admin approval gate).
    tests/test_approval_gate.py enables REQUIRE_APPROVAL explicitly."""
    from app.core.config import settings

    previous = settings.REQUIRE_APPROVAL
    settings.REQUIRE_APPROVAL = False
    yield
    settings.REQUIRE_APPROVAL = previous


@pytest.fixture(scope="session", autouse=True)
def _test_app_env():
    """The provisioned .env sets APP_ENV=production, which makes session
    cookies `Secure`; httpx test clients then drop them over plain http.
    Pin the app to a non-production env for the whole test session."""
    from app.core.config import settings

    previous = settings.APP_ENV
    if previous != "production":
        yield
        return
    settings.APP_ENV = "testing"
    yield
    settings.APP_ENV = previous


# ──────────────────────────────────────────────
# Shared helpers (import from tests.conftest)
# ──────────────────────────────────────────────

def register_user(client, email: str, password: str = "pass1234", full_name: str = "Test User",
                  auto_approve: bool = True):
    """Register a user and assert success; returns the response JSON.
    Auto-approves the account so subsequent logins pass the approval gate
    (approval-gate tests pass auto_approve=False to keep accounts pending)."""
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": full_name, "password": password},
    )
    assert r.status_code == 201, r.text
    if auto_approve:
        _approve_user(email)
    return r.json()


def _approve_user(email: str):
    """Flip is_approved=True for an existing user, directly in the test DB."""
    from app.models import User

    db = TestSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is not None:
            user.is_approved = True
            db.commit()
    finally:
        db.close()


def login(client, email: str, password: str = "pass1234"):
    """Log in and return an Authorization header dict."""
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def promote_to_admin(email: str):
    """Flip is_admin=True for an existing user, directly in the test DB."""
    from app.models import User

    db = TestSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None, f"user {email} not found"
        user.is_admin = True
        db.commit()
    finally:
        db.close()
