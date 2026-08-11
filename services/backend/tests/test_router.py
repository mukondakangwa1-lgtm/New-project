"""
KUDOS AI router tests: sequential fallback, health registry, cooldowns.
"""
import time

import pytest

from app.core import llm_engine


@pytest.fixture(autouse=True)
def clean_router(monkeypatch):
    # Hermetic routing: ignore the local .env (e.g. LLM_PROVIDER=ollama with
    # a real local Ollama server) — tests opt into providers explicitly.
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.delenv("LLM_PARALLEL", raising=False)
    llm_engine.ROUTER_HEALTH.clear()
    llm_engine.provider_is_configured = lambda p: False
    yield
    llm_engine.ROUTER_HEALTH.clear()


async def test_sequential_fallback_to_second_provider(monkeypatch):
    calls = []
    llm_engine.provider_is_configured = lambda p: True

    async def boom(prompt, system_prompt="", media=None):
        calls.append("a")
        raise RuntimeError("provider down")

    async def good(prompt, system_prompt="", media=None):
        calls.append("b")
        return "answer from b"

    monkeypatch.setattr(llm_engine, "query_google_gemini", boom)
    monkeypatch.setattr(llm_engine, "query_openai", good)

    result = await llm_engine.query_best_llm("q")
    assert result["response"] == "answer from b"
    assert result["provider"] == "openai"
    assert calls == ["a", "b"]
    assert any(d["ok"] for d in result["details"])
    assert any(not d["ok"] for d in result["details"])


async def test_failure_health_tracking(monkeypatch):
    llm_engine.provider_is_configured = lambda p: True

    async def boom(prompt, system_prompt="", media=None):
        raise RuntimeError("down")

    async def good(prompt, system_prompt="", media=None):
        return "ok"

    monkeypatch.setattr(llm_engine, "query_google_gemini", boom)
    monkeypatch.setattr(llm_engine, "query_openai", good)

    # three explicit failures drive gemini into cooldown
    for _ in range(3):
        result = await llm_engine.query_best_llm("q", provider="google_gemini")
        assert result["provider"] == "none"

    health = {h["provider"]: h for h in llm_engine.router_health()}
    assert health["google_gemini"]["consecutive_failures"] == 3
    assert health["google_gemini"]["cooldown_until"] > time.time()

    # healthy openai keeps serving auto traffic
    result = await llm_engine.query_best_llm("q")
    assert result["provider"] == "openai"
    health = {h["provider"]: h for h in llm_engine.router_health()}
    assert health["openai"]["successes_total"] >= 1


async def test_cooldown_skips_degraded_provider(monkeypatch):
    calls = []
    llm_engine.provider_is_configured = lambda p: p in ("google_gemini", "openai")

    async def boom(prompt, system_prompt="", media=None):
        calls.append("gemini")
        raise RuntimeError("down")

    async def bad_openai(prompt, system_prompt="", media=None):
        raise RuntimeError("openai down")

    monkeypatch.setattr(llm_engine, "query_google_gemini", boom)

    # Drive gemini into cooldown with explicit routing
    for _ in range(3):
        await llm_engine.query_best_llm("q", provider="google_gemini")

    # Now openai is also down: auto routing must skip gemini (cooldown)
    monkeypatch.setattr(llm_engine, "query_openai", bad_openai)
    calls.clear()
    result = await llm_engine.query_best_llm("q")
    assert calls == [], "degraded provider must be skipped during cooldown"
    skips = [d for d in result["details"] if "skipped" in d]
    assert skips and skips[0]["skipped"] == "cooldown"
    assert result["provider"] == "none"


async def test_lone_degraded_provider_still_probed(monkeypatch):
    async def boom(prompt, system_prompt="", media=None):
        raise RuntimeError("down")

    monkeypatch.setattr(llm_engine, "query_google_gemini", boom)
    monkeypatch.setattr(llm_engine, "query_openai", lambda p, s="", media=None: None)
    # only gemini configured
    llm_engine.provider_is_configured = lambda p: p == "google_gemini"

    for _ in range(3):
        await llm_engine.query_best_llm("q")

    calls = []

    async def record(prompt, system_prompt="", media=None):
        calls.append(1)
        raise RuntimeError("still down")

    monkeypatch.setattr(llm_engine, "query_google_gemini", record)
    await llm_engine.query_best_llm("q")
    assert calls == [1], "a lone degraded provider must still be probed"


async def test_explicit_provider_routing(monkeypatch):
    llm_engine.provider_is_configured = lambda p: True

    async def boom(prompt, system_prompt="", media=None):
        raise RuntimeError("down")

    async def good(prompt, system_prompt="", media=None):
        return "from groq"

    monkeypatch.setattr(llm_engine, "query_google_gemini", boom)
    monkeypatch.setattr(llm_engine, "query_groq", good)

    result = await llm_engine.query_best_llm("q", provider="groq")
    assert result["provider"] == "groq"
    assert result["response"] == "from groq"

    result = await llm_engine.query_best_llm("q", provider="bogus")
    assert result["provider"] == "none"
    assert "Unknown" in result["message"]


async def test_parallel_mode_returns_first_success(monkeypatch):
    import asyncio

    llm_engine.provider_is_configured = lambda p: True

    async def slow_good(prompt, system_prompt="", media=None):
        await asyncio.sleep(0.05)
        return "slow winner"

    async def fast_fail(prompt, system_prompt="", media=None):
        raise RuntimeError("nope")

    monkeypatch.setattr(llm_engine, "query_google_gemini", fast_fail)
    monkeypatch.setattr(llm_engine, "query_openai", slow_good)
    monkeypatch.setattr(llm_engine, "query_groq", slow_good)

    monkeypatch.setenv("LLM_PARALLEL", "1")
    result = await llm_engine.query_best_llm("q")
    assert result["response"] == "slow winner"
    assert len(result["details"]) >= 1