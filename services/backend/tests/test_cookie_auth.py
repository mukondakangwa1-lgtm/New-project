"""
Cookie-based session auth tests: HttpOnly cookie issuance, cookie
authentication, CSRF guard, logout, and Bearer compatibility.
"""
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import register_user

client = TestClient(app)

EMAIL = "cookie@campus.edu"
PASSWORD = "pass1234"


def test_login_sets_http_only_cookie():
    try:
        register_user(client, EMAIL)
    except AssertionError:
        pass

    r = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["access_token"]
    assert "dc_access_token" in r.cookies

    cookie = r.cookies["dc_access_token"]
    assert cookie
    set_cookie = r.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie
    assert "samesite=lax" in set_cookie.lower()


def test_cookie_authenticates_requests():
    c = TestClient(app)
    try:
        register_user(c, EMAIL)
    except AssertionError:
        pass
    c.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})

    # cookie alone is enough — no Authorization header anywhere
    r = c.get("/api/v1/users/me")
    assert r.status_code == 200
    assert r.json()["email"] == EMAIL


def test_csrf_guard_blocks_cookie_mutations_without_header():
    c = TestClient(app)
    try:
        register_user(c, EMAIL)
    except AssertionError:
        pass
    c.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})

    # POST without the custom header -> 403 (cross-site form-style request)
    r = c.post("/api/v1/kudos/memory", json={"content": "csfr probe"})
    assert r.status_code == 403
    assert "CSRF" in r.json()["detail"]


def test_csrf_guard_allows_mutations_with_custom_header():
    c = TestClient(app)
    try:
        register_user(c, EMAIL)
    except AssertionError:
        pass
    c.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})

    r = c.post(
        "/api/v1/kudos/memory",
        json={"content": "cookie session memory"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert r.status_code == 201


def test_bearer_header_still_works_without_cookie():
    c = TestClient(app)
    try:
        register_user(c, EMAIL)
    except AssertionError:
        pass
    r = c.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    token = r.json()["access_token"]

    c.cookies.clear()
    r = c.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == EMAIL


def test_logout_clears_cookie():
    c = TestClient(app)
    try:
        register_user(c, EMAIL)
    except AssertionError:
        pass
    c.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})

    r = c.post("/api/v1/auth/logout")
    assert r.status_code == 204
    assert "dc_access_token" not in c.cookies

    r = c.get("/api/v1/users/me")
    assert r.status_code == 401


def test_token_endpoint_sets_cookie_for_swagger():
    c = TestClient(app)
    try:
        register_user(c, EMAIL)
    except AssertionError:
        pass
    r = c.post("/api/v1/auth/token", data={"username": EMAIL, "password": PASSWORD})
    assert r.status_code == 200
    assert "dc_access_token" in c.cookies
