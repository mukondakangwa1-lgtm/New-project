"""
Digital Campus - MCP Server Tests
Auth middleware over Streamable HTTP, tool registration, mutation guard,
and DB-backed tool behavior.
"""
import pytest
from fastapi.testclient import TestClient

import app.mcp_server as mcp_module
from app.core.config import settings
from app.mcp_server import create_mcp_app
from app.models import KudosConnector, KudosWebKnowledge, User
from tests.conftest import TestSessionLocal

app = create_mcp_app()

INIT_PAYLOAD = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    },
}


@pytest.fixture
def mcp_db(monkeypatch):
    """Point MCP tool DB sessions at the shared test database."""
    monkeypatch.setattr(mcp_module, "SessionLocal", TestSessionLocal)


@pytest.fixture
def admin_user():
    db = TestSessionLocal()
    try:
        admin = db.query(User).filter(User.email == "mcp-admin@test.c").first()
        if admin is None:
            admin = User(email="mcp-admin@test.c", full_name="MCP Admin", hashed_password="x")
            db.add(admin)
            db.commit()
            db.refresh(admin)
        return admin
    finally:
        db.close()


# === HTTP layer + auth middleware ===

@pytest.fixture(scope="module")
def mcp_client():
    """Enter the app once so FastMCP's lifespan (task group) stays alive."""
    with TestClient(app) as c:
        yield c


def test_mcp_requires_token(monkeypatch, mcp_client):
    monkeypatch.setattr(settings, "MCP_REQUIRE_AUTH", True)
    monkeypatch.setattr(settings, "MCP_AUTH_TOKEN", "s3cret")
    headers = {"Accept": "application/json, text/event-stream"}

    r = mcp_client.post("/mcp", json=INIT_PAYLOAD, headers=headers)
    assert r.status_code == 401

    r = mcp_client.post("/mcp", json=INIT_PAYLOAD, headers={**headers, "x-mcp-token": "wrong"})
    assert r.status_code == 401

    r = mcp_client.post("/mcp", json=INIT_PAYLOAD, headers={**headers, "x-mcp-token": "s3cret"})
    assert r.status_code == 200
    assert "jsonrpc" in r.text


def test_mcp_auth_optional_when_disabled(monkeypatch, mcp_client):
    monkeypatch.setattr(settings, "MCP_REQUIRE_AUTH", False)
    r = mcp_client.post("/mcp", json=INIT_PAYLOAD, headers={"Accept": "application/json, text/event-stream"})
    assert r.status_code == 200


def test_mcp_rejects_missing_accept_header(monkeypatch, mcp_client):
    monkeypatch.setattr(settings, "MCP_REQUIRE_AUTH", False)
    r = mcp_client.post("/mcp", json=INIT_PAYLOAD)
    assert r.status_code == 406


# === Tools: health ===

def test_kudos_get_health(mcp_db, admin_user):
    result = mcp_module.kudos_get_health()
    assert result["status"] == "healthy"
    assert result["documents"] == 0


# === Tools: connectors ===

def test_kudos_list_connectors(mcp_db, admin_user):
    db = TestSessionLocal()
    try:
        db.add(KudosConnector(
            created_by=admin_user.id, name="Approved", connector_type="rss",
            source_url="https://example.com/rss", is_approved=True, status="active",
        ))
        db.add(KudosConnector(
            created_by=admin_user.id, name="Pending", connector_type="rss",
            source_url="https://example.com/rss2", is_approved=False, status="active",
        ))
        db.commit()
    finally:
        db.close()

    result = mcp_module.kudos_list_connectors()
    names = [c["name"] for c in result]
    assert "Approved" in names
    assert "Pending" not in names


# === Tools: knowledge search ===

def test_kudos_search_knowledge(mcp_db, admin_user):
    db = TestSessionLocal()
    try:
        db.add(KudosWebKnowledge(
            url="https://example.com/photosynthesis",
            title="Photosynthesis explained",
            content="Photosynthesis converts sunlight into chemical energy in plants.",
            summary="A page about photosynthesis.",
            is_approved=True, is_active=True, learned_by=admin_user.id,
        ))
        db.add(KudosWebKnowledge(
            url="https://example.com/unapproved",
            title="Unapproved page",
            content="Photosynthesis content that is not approved yet.",
            is_approved=False, is_active=True, learned_by=admin_user.id,
        ))
        db.commit()
    finally:
        db.close()

    results = mcp_module.kudos_search_knowledge("photosynthesis", limit=5)
    assert results, "expected at least one match"
    assert any("Photosynthesis explained" == r.get("title") for r in results)
    assert all(r.get("title") != "Unapproved page" for r in results)


# === Tools: mutation guard ===

def test_kudos_queue_connector_sync_disabled(monkeypatch):
    monkeypatch.setattr(settings, "MCP_ALLOW_MUTATIONS", False)
    with pytest.raises(RuntimeError, match="disabled"):
        mcp_module.kudos_queue_connector_sync(1)


def test_kudos_queue_connector_sync_enabled(monkeypatch):
    monkeypatch.setattr(settings, "MCP_ALLOW_MUTATIONS", True)

    queued = {}

    class FakeTask:
        def delay(self, connector_id):
            queued["connector_id"] = connector_id
            return type("R", (), {"id": "fake-task-id"})()

    monkeypatch.setattr("app.tasks.sync_connector", FakeTask())
    result = mcp_module.kudos_queue_connector_sync(7)
    assert result == {"status": "queued", "connector_id": 7, "task_id": "fake-task-id"}
    assert queued["connector_id"] == 7
