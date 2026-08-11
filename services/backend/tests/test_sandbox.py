"""
KUDOS Sandbox tests: recommendation stage (heuristic + LLM parse),
knowledge base seeding, and the secure-browse endpoint guard.
"""
from fastapi.testclient import TestClient

from app.core import sandbox
from app.main import app
from tests.conftest import TestSessionLocal, login, promote_to_admin, register_user

client = TestClient(app)

EMAIL = "sandbox@campus.edu"


def _setup():
    try:
        register_user(client, EMAIL)
    except AssertionError:
        pass
    headers = login(client, EMAIL)
    promote_to_admin(EMAIL)
    return headers


def test_recommend_heuristic_recommends_clean_tests(monkeypatch):
    headers = _setup()
    prop = sandbox.create_proposal(
        title="Dark mode",
        description="Add a dark theme toggle",
        category="feature",
    )
    prop["test_result"] = {
        "passed": 3,
        "failed": 0,
        "tests": [
            {"name": "existing_tests", "status": "PASS"},
            {"name": "syntax_dark.py", "status": "PASS"},
        ],
    }
    # Hermetic: no LLM verdict — the deterministic heuristic must decide.
    from app.core import llm_engine

    async def no_llm(*args, **kwargs):
        return None

    monkeypatch.setattr(llm_engine, "query_best_llm", no_llm)
    r = client.post("/api/v1/kudos/sandbox/recommend", json={"proposal_id": prop["id"]}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "recommended"
    assert body["recommendation"]["decision"] == "recommend"


def test_recommend_never_recommends_failing_tests(monkeypatch):
    headers = _setup()
    prop = sandbox.create_proposal(
        title="Broken feature",
        description="Has failing tests",
        category="fix",
    )
    prop["test_result"] = {
        "passed": 1,
        "failed": 2,
        "tests": [{"name": "existing_tests", "status": "FAIL", "details": "boom"}],
    }
    from app.core import llm_engine

    async def no_llm(*args, **kwargs):
        return None

    monkeypatch.setattr(llm_engine, "query_best_llm", no_llm)
    r = client.post("/api/v1/kudos/sandbox/recommend", json={"proposal_id": prop["id"]}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "not_recommended"
    assert body["recommendation"]["decision"] == "not_recommend"


def test_recommend_parses_llm_json_verdict():
    prop = sandbox.create_proposal(title="P", description="D", category="feature")
    prop["test_result"] = {"passed": 2, "failed": 0, "tests": []}
    decision, confidence, rationale = sandbox._parse_recommendation(
        '{"decision": "recommend", "confidence": 0.92, "rationale": "solid"}',
        prop["test_result"],
    )
    assert decision == "recommend"
    assert confidence == 0.92
    assert rationale == "solid"


def test_recommend_requires_tested_status():
    headers = _setup()
    prop = sandbox.create_proposal(title="New", description="Never tested", category="feature")
    r = client.post("/api/v1/kudos/sandbox/recommend", json={"proposal_id": prop["id"]}, headers=headers)
    assert r.status_code == 400


def test_knowledge_seed_is_idempotent():
    headers = _setup()
    db = TestSessionLocal()
    try:
        first = sandbox.seed_sandbox_knowledge(db)
        assert first >= 8, f"expected KB entries, got {first}"
        second = sandbox.seed_sandbox_knowledge(db)
        assert second == 0, "seeding must be idempotent"
    finally:
        db.close()

    r = client.get("/api/v1/kudos/sandbox/knowledge", headers=headers)
    assert r.status_code == 200
    assert r.json()["seeded_now"] == 0
    kinds = {e["kind"] for e in r.json()["entries"]}
    assert "concept" in kinds and "fact" in kinds


def test_knowledge_context_helper_returns_prose():
    from app.core.sandbox import build_sandbox_knowledge_context

    db = TestSessionLocal()
    try:
        context = build_sandbox_knowledge_context(db)
    finally:
        db.close()
    assert context, "knowledge context should not be empty"
    assert context.startswith("- ")
    assert "\n" in context


def test_browse_rate_limit_blocks_rapid_calls():
    headers = _setup()
    # drain the rate window by setting history entries
    import time
    from app.api.v1.endpoints import sandbox as sandbox_api

    now = time.monotonic()
    sandbox_api._browse_history[:] = [now] * sandbox_api.BROWSE_RATE_MAX
    r = client.post(
        "/api/v1/kudos/sandbox/browse",
        json={"url": "https://example.com/"},
        headers=headers,
    )
    assert r.status_code == 429
    sandbox_api._browse_history[:] = []
