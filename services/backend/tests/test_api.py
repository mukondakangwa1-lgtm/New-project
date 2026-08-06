"""
Digital Campus - API Tests
"""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db

# --- Test database (in-memory SQLite) ---
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


def setup_module():
    """Create test tables before all tests."""
    Base.metadata.create_all(bind=engine)


def teardown_module():
    """Drop test tables after all tests."""
    Base.metadata.drop_all(bind=engine)
    import os

    if os.path.exists("./test.db"):
        os.remove("./test.db")


client = TestClient(app)

# --- Test data ---
TEST_USER = {"email": "test@campus.edu", "full_name": "Test User", "password": "testpass123"}
TEST_COURSE = {"code": "TST101", "title": "Test Course", "description": "A test course", "credits": 3}


# === Health ===

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["app"] == "Digital Campus API"


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


# === Auth ===

def test_register():
    response = client.post("/api/v1/auth/register", json=TEST_USER)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == TEST_USER["email"]
    assert "id" in data


def test_register_duplicate():
    response = client.post("/api/v1/auth/register", json=TEST_USER)
    assert response.status_code == 400


def test_login():
    response = client.post(
        "/api/v1/auth/login",
        json={"email": TEST_USER["email"], "password": TEST_USER["password"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password():
    response = client.post(
        "/api/v1/auth/login",
        json={"email": TEST_USER["email"], "password": "wrong"},
    )
    assert response.status_code == 401


# === Users ===

def get_auth_header():
    """Helper — log in and return auth header."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": TEST_USER["email"], "password": TEST_USER["password"]},
    )
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_users_me():
    response = client.get("/api/v1/users/me", headers=get_auth_header())
    assert response.status_code == 200
    assert response.json()["email"] == TEST_USER["email"]


def test_users_me_unauthenticated():
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401


def test_users_list():
    response = client.get("/api/v1/users/", headers=get_auth_header())
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# === Courses ===

def test_courses_list_empty():
    response = client.get("/api/v1/courses/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_courses_create_requires_admin():
    response = client.post("/api/v1/courses/", json=TEST_COURSE, headers=get_auth_header())
    assert response.status_code == 403  # not admin


def test_courses_create_as_admin():
    """Create admin user, log in, create course."""
    # Register admin
    client.post(
        "/api/v1/auth/register",
        json={"email": "admin@test.com", "full_name": "Admin", "password": "admin123"},
    )
    # Make admin directly in DB
    db = TestSessionLocal()
    from app.models import User
    user = db.query(User).filter(User.email == "admin@test.com").first()
    user.is_admin = True
    db.commit()
    db.close()

    # Login as admin
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "admin123"},
    )
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post("/api/v1/courses/", json=TEST_COURSE, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["code"] == TEST_COURSE["code"]


def test_courses_get():
    response = client.get("/api/v1/courses/1")
    assert response.status_code == 200
    assert response.json()["code"] == TEST_COURSE["code"]


def test_courses_get_not_found():
    response = client.get("/api/v1/courses/999")
    assert response.status_code == 404
