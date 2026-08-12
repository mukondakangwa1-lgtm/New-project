"""
Tests for the offline general-knowledge fact base.

This layer exists so the assistant answers common questions from its own
knowledge instead of replying "please upload a document". It sits between
the exact-reasoning core and the LLM.
"""
import pytest

from app.core.general_knowledge import lookup, topics


@pytest.mark.parametrize(
    "query,expected_fragment",
    [
        ("what is python", "Python"),
        ("What is Python?", "Python"),
        ("what is javascript", "JavaScript"),
        ("what is an api", "API"),
        ("what is git", "Git"),
        ("what is docker", "Docker"),
        ("what is sql", "SQL"),
        ("what is machine learning", "Machine learning"),
        ("what is recursion", "Recursion"),
        ("what is an algorithm", "algorithm"),
    ],
)
def test_technical_topics(query, expected_fragment):
    answer = lookup(query)
    assert answer is not None, f"{query!r} should have an offline answer"
    assert expected_fragment.lower() in answer.lower()


@pytest.mark.parametrize(
    "query",
    [
        "what is kudos",
        "what is digital campus",
        "kudos, what is python",
        "hey kudos, what is python?",
        "yo, what is sql?",
        "hi, how do i study?",
    ],
)
def test_phrasing_variations_still_resolve(query):
    assert lookup(query) is not None, f"{query!r} should resolve"


def test_asking_about_kudos_is_not_confused_with_the_vocative():
    """'what is kudos' asks ABOUT Kudos; 'kudos, what is python' addresses it."""
    about = lookup("what is kudos")
    addressed = lookup("kudos, what is python")
    assert about is not None and addressed is not None
    assert about != addressed
    assert "python" in addressed.lower()


# ──────────────────────────────────────────────
# CAPITAL CITIES
# ──────────────────────────────────────────────

@pytest.mark.parametrize(
    "query,capital",
    [
        ("what is the capital of France", "Paris"),
        ("capital of zambia", "Lusaka"),
        ("what's the capital of Japan", "Tokyo"),
        ("what is the capital city of Kenya", "Nairobi"),
        ("hey kudos, what is the capital of Germany?", "Berlin"),
        ("capital of the united kingdom", "London"),
        ("what is the capital of brazil", "Brasília"),
        ("capital of india", "New Delhi"),
    ],
)
def test_capitals(query, capital):
    answer = lookup(query)
    assert answer is not None, f"{query!r} should resolve"
    assert capital in answer


def test_unknown_country_falls_through():
    assert lookup("capital of Atlantis") is None
    assert lookup("capital of Wakanda") is None


def test_multi_capital_country_is_explained():
    answer = lookup("capital of south africa")
    assert "Pretoria" in answer and "Cape Town" in answer


def test_definite_article_grammar():
    assert "the United Kingdom" in lookup("capital of the united kingdom")
    assert "the USA" in lookup("capital of usa")


# ──────────────────────────────────────────────
# NEGATIVE CASES
# ──────────────────────────────────────────────

@pytest.mark.parametrize(
    "query",
    [
        "",
        "   ",
        "asdfghjkl",
        "what is the airspeed velocity of an unladen swallow",
        "summarise the document I uploaded",
    ],
)
def test_unknown_queries_return_none(query):
    assert lookup(query) is None


def test_topics_is_a_nonempty_list():
    result = topics()
    assert isinstance(result, list)
    assert len(result) >= 20
    assert result == sorted(result)
