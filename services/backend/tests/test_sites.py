"""
KUDOS Sites — generate + launch sites live, public serving, path safety.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core import site_builder
from app.main import app
from tests.conftest import login, register_user

client = TestClient(app)

SITE_HTML = """<!doctype html>
<html><head><title>My Site</title></head>
<body><h1>Hello KUDOS</h1><p>Built in seconds.</p></body></html>
"""

FENCED_HTML = "```html\n" + SITE_HTML + "\n```"


@pytest.fixture(autouse=True)
def clean_sites():
    """Remove any sites created during the test session (local backend)."""
    yield
    for item in site_builder.list_sites():
        site_builder.delete_site(item["site_id"])


def test_extract_html_bare():
    assert site_builder._extract_html(SITE_HTML).startswith("<!doctype html")


def test_extract_html_fenced():
    assert site_builder._extract_html(FENCED_HTML).startswith("<!doctype html")


def test_extract_html_rejects_non_html():
    with pytest.raises(site_builder.SiteBuildError):
        site_builder._extract_html("This is just some prose, no html here.")


def test_resolve_site_key_blocks_traversal():
    sid = "a" * 12
    assert site_builder.resolve_site_key(sid, "style.css").endswith("/style.css")
    for bad in ("../secret", "..%2fsecret", "a/../../etc/passwd", "\\..\\secret"):
        with pytest.raises(site_builder.SiteBuildError):
            site_builder.resolve_site_key(sid, bad)
    assert not site_builder.valid_site_id("not-an-id")


def test_generate_and_serve_public(monkeypatch):
    async def fake_query(prompt, system_prompt="", provider=None, media=None, question=None, knowledge_context=None):
        return {"response": FENCED_HTML, "provider": "fake"}

    monkeypatch.setattr("app.core.llm_engine.query_best_llm", fake_query)

    meta = asyncio.run(site_builder.generate_site("My Site", kind="site", prompt="a demo site"))
    assert meta["site_id"] and meta["url"].endswith("/")
    assert meta["title"] == "My Site"

    # Public index
    r = client.get(meta["url"])
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Hello KUDOS" in r.text
    assert r.headers["x-content-type-options"] == "nosniff"

    # Proxy (Next.js) strips the trailing slash — the no-slash root must work too
    r2 = client.get(meta["url"].rstrip("/"))
    assert r2.status_code == 200
    assert "Hello KUDOS" in r2.text
    assert f'<base href="{meta["url"]}">' in r2.text

    # Public list
    lst = client.get("/api/v1/kudos/sites").json()["sites"]
    assert any(s["site_id"] == meta["site_id"] for s in lst)

    # Missing assets / unknown ids 404
    assert client.get(f"/api/v1/kudos/sites/{meta['site_id']}/nope.css").status_code == 404
    assert client.get("/api/v1/kudos/sites/deadbeefdead/").status_code == 404


def test_generate_site_requires_llm(monkeypatch):
    async def no_llm(prompt, system_prompt="", provider=None, media=None, question=None, knowledge_context=None):
        return {"response": None, "provider": "none", "message": "No LLM configured"}

    monkeypatch.setattr("app.core.llm_engine.query_best_llm", no_llm)
    with pytest.raises(site_builder.SiteBuildError):
        asyncio.run(site_builder.generate_site("x"))


def test_create_and_delete_site_endpoint(monkeypatch):
    email = "sitemaker@campus.edu"
    register_user(client, email)
    auth = login(client, email)

    async def fake_query(prompt, system_prompt="", provider=None, media=None, question=None, knowledge_context=None):
        return {"response": SITE_HTML, "provider": "fake"}

    monkeypatch.setattr("app.core.llm_engine.query_best_llm", fake_query)

    r = client.post(
        "/api/v1/kudos/sites",
        json={"name": "CV Maker", "kind": "cv", "prompt": "software engineer CV"},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    meta = r.json()
    assert meta["kind"] == "cv"

    # served
    assert client.get(meta["url"]).status_code == 200
    assert client.get(meta["url"].rstrip("/")).status_code == 200

    # delete requires auth
    assert client.delete(f"/api/v1/kudos/sites/{meta['site_id']}").status_code in (401, 403)
    assert client.delete(f"/api/v1/kudos/sites/{meta['site_id']}", headers=auth).status_code == 204
    assert client.get(meta["url"]).status_code == 404
