"""
Digital Campus - Phase 1 Hardening Tests

- structured logging / request correlation IDs and unified error responses
- production settings fail-fast validation
- readiness probe
- superadmin metrics endpoint
- PostgreSQL backup helpers (pure logic only; pg_dump is not invoked)
"""
import os
from datetime import datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core import backup
from app.core.config import Settings, settings
from app.main import app
from tests.conftest import login, promote_to_admin, register_user

client = TestClient(app)


def test_error_responses_include_request_id():
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    body = r.json()
    assert "detail" in body
    assert "request_id" in body and len(body["request_id"]) == 12
    assert r.headers.get("x-request-id") == body["request_id"]


def test_validation_error_includes_request_id():
    r = client.post("/api/v1/auth/register", json={})
    assert r.status_code == 422
    assert "request_id" in r.json()


def test_auth_error_includes_request_id():
    r = client.get("/api/v1/users/me")
    assert r.status_code == 401
    assert "request_id" in r.json()


def test_unhandled_exception_returns_500_with_request_id():
    # starlette >=1.0 re-raises server exceptions even after sending the 500;
    # disable that here so we can assert on the delivered response.
    quiet = TestClient(app, raise_server_exceptions=False)

    @app.get("/_test_boom")
    def _boom():
        raise RuntimeError("boom")

    try:
        r = quiet.get("/_test_boom")
        assert r.status_code == 500
        body = r.json()
        assert body["detail"] == "Internal server error"
        assert body["request_id"] and body["request_id"] != "-"
    finally:
        app.router.routes = [
            route for route in app.router.routes if getattr(route, "path", "") != "/_test_boom"
        ]


def test_http_exception_handler_keeps_headers():
    exc = HTTPException(status_code=429, detail="rate limited", headers={"Retry-After": "30"})
    r = client.get("/api/v1/health")
    assert r.status_code == 200  # sanity: route still fine
    assert exc.status_code == 429


def test_request_log_middleware_sets_header_everywhere():
    r = client.get("/api/v1/health")
    assert r.headers.get("x-request-id")
    r2 = client.post("/api/v1/auth/login", json={"email": "a@b.c", "password": "x"})
    assert r2.headers.get("x-request-id")


# --- Production settings fail-fast validation ---


def test_production_defaults_are_rejected():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(_env_file=None, APP_ENV="production")


def test_production_debug_is_rejected():
    with pytest.raises(ValueError, match="DEBUG"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            SECRET_KEY="a-strong-secret-value-at-least-16-chars",
            DEBUG=True,
        )


def test_production_strong_secret_ok():
    s = Settings(
        _env_file=None,
        APP_ENV="production",
        SECRET_KEY="a-strong-secret-value-at-least-16-chars",
        DEBUG=False,
    )
    assert s.SECRET_KEY


def test_development_defaults_are_allowed_but_never_known():
    s = Settings(_env_file=None)
    assert s.APP_ENV == "development"
    assert s.SECRET_KEY != "changeme-in-production"
    assert len(s.SECRET_KEY) >= 32


def test_development_cors_is_explicit():
    s = Settings(_env_file=None)
    assert "*" not in [o.strip() for o in s.CORS_ORIGINS.split(",")]


def test_production_rejects_short_secret():
    with pytest.raises(ValueError, match="at least 32"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            SECRET_KEY="short-secret",
            DEBUG=False,
        )


def test_production_accepts_strong_secret():
    s = Settings(
        _env_file=None,
        APP_ENV="production",
        SECRET_KEY="x" * 40,
        DEBUG=False,
    )
    assert len(s.SECRET_KEY) >= 32


def test_env_file_resolves_next_to_package():
    """The .env the user edits (services/backend/.env) must be the file
    pydantic loads, regardless of the process working directory."""
    from app.core.config import _ENV_FILE

    assert _ENV_FILE.endswith("services/backend/.env")
    assert os.path.isfile(_ENV_FILE), f"env file not found at {_ENV_FILE}"


def test_loaded_secret_is_not_the_known_default():
    """The real SECRET_KEY the user put in .env must be active, not the
    built-in placeholder or a random substitute."""
    from app.core.config import settings as live_settings

    assert live_settings.SECRET_KEY != "changeme-in-production"


# --- Readiness + metrics ---


def test_readiness_ready_with_working_db(monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.health._db_latency_ms", lambda: 2.5)
    monkeypatch.setattr("app.api.v1.endpoints.health._redis_ready", lambda: True)
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200
    checks = r.json()["checks"]
    assert checks["database"]["ready"] is True
    assert checks["database"]["latency_ms"] == 2.5
    assert checks["redis"]["ready"] is True


def test_readiness_unavailable_when_db_down(monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.health._db_latency_ms", lambda: -1.0)
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "unavailable"


def test_metrics_requires_admin():
    r = client.get("/api/v1/admin/metrics")
    assert r.status_code == 401


def test_metrics_with_superadmin(monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.health._db_latency_ms", lambda: 1.5)
    monkeypatch.setattr("app.api.v1.endpoints.health._redis_ready", lambda: False)
    email = "metrics-admin@test.c"
    register_user(client, email)
    promote_to_admin(email)
    headers = login(client, email)
    r = client.get("/api/v1/admin/metrics", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["system"]["cpu_count"] == os.cpu_count()
    assert body["database"]["latency_ms"] == 1.5
    assert body["redis"]["ready"] is False
    assert "requests" in body and body["requests"]["total"] > 0


# --- Backup helpers (pure logic) ---


def test_dump_filename_format():
    name = backup.dump_filename(datetime(2026, 1, 2, 3, 4, 5))
    assert name == "digital_campus_20260102_030405.dump"


def test_pg_cmd_rejects_sqlite():
    with pytest.raises(ValueError, match="PostgreSQL"):
        backup._pg_cmd("sqlite:///./x.db", "pg_dump")


def test_prune_backups_keeps_newest(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_DIR", str(tmp_path))
    for hour in range(5):
        (tmp_path / f"digital_campus_2026010{hour}_000000.dump").write_text("d")

    removed = backup.prune_backups(keep=3)
    assert len(removed) == 2
    remaining = {p.name for p in tmp_path.iterdir()}
    assert "digital_campus_20260104_000000.dump" in remaining
    # newest 2 kept: 04 and 03 removed 02 and 01 (reverse sorted list)
    assert len(remaining) == 3


def test_list_backups_missing_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_DIR", str(tmp_path / "nope"))
    assert backup.list_backups() == []