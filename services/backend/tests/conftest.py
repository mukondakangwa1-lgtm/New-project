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


# ──────────────────────────────────────────────
# Shared helpers (import from tests.conftest)
# ──────────────────────────────────────────────

def register_user(client, email: str, password: str = "pass1234", full_name: str = "Test User"):
    """Register a user and assert success; returns the response JSON."""
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": full_name, "password": password},
    )
    assert r.status_code == 201, r.text
    return r.json()


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
