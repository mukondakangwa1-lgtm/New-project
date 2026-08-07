"""
Digital Campus - MCP End-to-End Test

Boots the real FastMCP app under uvicorn in a SEPARATE PROCESS (isolated
StreamableHTTP session manager, realistic deployment) on an ephemeral port,
and drives it through the real client (app.core.mcp_client), exercising:
  - the auth middleware (x-mcp-token) over real HTTP
  - the Streamable HTTP handshake (initialize + session)
  - DB-backed tools end-to-end against the shared SQLite test DB
  - the client's soft-failure behavior
"""
import os
import socket
import subprocess
import sys
import time

import pytest

from app.core.config import settings
from app.core.mcp_client import call_mcp_tool, search_mcp_sources

E2E_TOKEN = "e2e-secret"


@pytest.fixture(scope="module")
def live_server():
    """Spawn a real uvicorn process serving the MCP app on an ephemeral port."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    runner = (
        "import os\n"
        "os.environ['DATABASE_URL'] = 'sqlite:///./test.db'\n"
        "os.environ['MCP_REQUIRE_AUTH'] = 'true'\n"
        f"os.environ['MCP_AUTH_TOKEN'] = '{E2E_TOKEN}'\n"
        "import uvicorn\n"
        "from app.mcp_server import create_mcp_app\n"
        f"uvicorn.run(create_mcp_app(), host='127.0.0.1', port={port}, log_level='warning')\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", runner],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    saved = (settings.MCP_AUTH_TOKEN, settings.MCP_ENABLED)
    settings.MCP_AUTH_TOKEN = E2E_TOKEN
    settings.MCP_ENABLED = True

    url = f"http://127.0.0.1:{port}/mcp"
    try:
        for _ in range(50):
            if proc.poll() is not None:
                raise RuntimeError(f"uvicorn subprocess exited early ({proc.returncode})")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("uvicorn subprocess did not start listening")
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        settings.MCP_AUTH_TOKEN, settings.MCP_ENABLED = saved


@pytest.mark.asyncio
async def test_e2e_health_tool(live_server, monkeypatch):
    monkeypatch.setattr(settings, "MCP_URL", live_server)

    health = await call_mcp_tool("kudos_get_health")
    assert health is not None, "client should return a structured result"
    assert health.get("status") == "healthy"


@pytest.mark.asyncio
async def test_e2e_list_connectors(live_server, monkeypatch):
    monkeypatch.setattr(settings, "MCP_URL", live_server)

    result = await call_mcp_tool("kudos_list_connectors")
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_e2e_wrong_token_rejected(live_server, monkeypatch):
    monkeypatch.setattr(settings, "MCP_URL", live_server)
    monkeypatch.setattr(settings, "MCP_AUTH_TOKEN", "wrong-token")

    result = await call_mcp_tool("kudos_get_health")
    assert result is None, "client should fail softly when auth is rejected"


@pytest.mark.asyncio
async def test_e2e_unknown_tool_error(live_server, monkeypatch):
    monkeypatch.setattr(settings, "MCP_URL", live_server)

    result = await call_mcp_tool("kudos_does_not_exist")
    assert result is None, "client should fail softly on unknown tool"


@pytest.mark.asyncio
async def test_e2e_disabled_returns_none(live_server, monkeypatch):
    monkeypatch.setattr(settings, "MCP_ENABLED", False)

    result = await call_mcp_tool("kudos_get_health")
    assert result is None, "client should no-op when MCP is disabled"


@pytest.mark.asyncio
async def test_e2e_search_mcp_sources(live_server, monkeypatch):
    monkeypatch.setattr(settings, "MCP_URL", live_server)

    sources = await search_mcp_sources("python", limit=3)
    assert isinstance(sources, list)
