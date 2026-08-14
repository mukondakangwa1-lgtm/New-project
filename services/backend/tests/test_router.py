"""
KUDOS AI router tests: parallel "ask every LLM + brain picks best",
sequential fallback, health registry, cooldowns.
"""
import time

import pytest

from app.core import llm_engine


@pytest.fixture(autouse=True)
def clean_router(monkeypatch):
    # Hermetic routing: ignore the local .env (e.g. LLM_PROVIDER=ollama with
    # a real local Ollama server) — tests opt into providers explicitly.
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    llm_engine.ROUTER_HEALTH.clear()
    llm_engine.provider_is_configured = lambda p: False
    yield
    llm_engine.ROUTER_HEALTH.clear()


@pytest.fixture(autouse=True)
def isolate_unmocked_providers(monkeypatch):
    """Router unit tests must never contact live model providers."""

    async def unavailable(
        prompt,
        system_prompt="",
        media=None,
    ):
        return None

    llm_engine.ROUTER_HEALTH.clear()
    monkeypatch.setattr(
        llm_engine,
        "query_groq",
        unavailable,
    )
    monkeypatch.setattr(
        llm_engine,
        "query_ollama",
        unavailable,
    )

    yield

    llm_engine.ROUTER_HEALTH.clear()


async def test_brain_mode_queries_all_providers(monkeypatch):
    """Default mode asks EVERY configured LLM at once and returns the best."""
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
    # both providers were asked at the same time (parallel), not sequentially
    assert set(calls) == {"a", "b"}
    assert "brain" in result
    assert any(d["ok"] for d in result["details"])
    assert any(not d["ok"] for d in result["details"])


async def test_brain_picks_grounded_answer_over_hallucination(monkeypatch):
    """KUDOS's brain must prefer the answer grounded in knowledge."""
    llm_engine.provider_is_configured = lambda p: True

    async def hallucinated(prompt, system_prompt="", media=None):
        return "The university has 40,000 students and was founded in 1954. The president is Dr. Jane Smith."

    async def grounded(prompt, system_prompt="", media=None):
        return "The university has 12,000 students and was founded in 1998. [1]"

    monkeypatch.setattr(llm_engine, "query_google_gemini", hallucinated)
    monkeypatch.setattr(llm_engine, "query_openai", grounded)

    question = "How many students does the university have?"
    knowledge = (
        "The university was founded in 1998. It currently has 12,000 students. "
        "The president is Dr. John Doe."
    )
    result = await llm_engine.query_best_llm(question, "system", question=question, knowledge_context=knowledge)

    assert result["provider"] == "openai"
    assert "12,000" in result["response"]
    scoreboard = {s["provider"]: s["score"] for s in result["brain"]["scoreboard"]}
    assert scoreboard["openai"] > scoreboard["google_gemini"]
    assert "brain" in result


async def test_brain_prefers_answer_that_covers_the_question(monkeypatch):
    """Among two plausible answers, the brain picks the one on-topic."""
    llm_engine.provider_is_configured = lambda p: True

    async def off_topic(prompt, system_prompt="", media=None):
        return "The cafeteria serves excellent coffee and pastries every morning."

    async def on_topic(prompt, system_prompt="", media=None):
        return "Registration for the fall semester closes on September 15th. [1]"

    monkeypatch.setattr(llm_engine, "query_google_gemini", off_topic)
    monkeypatch.setattr(llm_engine, "query_openai", on_topic)

    question = "When does registration close for the fall semester?"
    result = await llm_engine.query_best_llm(question, "system", question=question)

    assert result["provider"] == "openai"
    assert "September 15th" in result["response"]


async def test_sequential_mode_keeps_legacy_fallback(monkeypatch):
    """With KUDOS_BRAIN_SELECT=0, providers are tried one at a time."""
    monkeypatch.setattr(llm_engine.settings, "KUDOS_BRAIN_SELECT", False)
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
    assert "brain" not in result


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


async def test_brain_mode_returns_none_when_all_fail(monkeypatch):
    llm_engine.provider_is_configured = lambda p: True

    async def boom(prompt, system_prompt="", media=None):
        raise RuntimeError("nope")

    async def empty(prompt, system_prompt="", media=None):
        return ""

    monkeypatch.setattr(llm_engine, "query_google_gemini", boom)
    monkeypatch.setattr(llm_engine, "query_openai", empty)

    result = await llm_engine.query_best_llm("q")
    assert result["response"] is None
    assert result["provider"] == "none"
