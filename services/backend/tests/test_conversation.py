"""
Tests for conversation routing.

The assistant has to tell apart four kinds of input:
  greeting / small talk  → warm, short reply
  exact question         → computed answer
  knowledge question     → explanation
  unknown                → honest fallback

Getting this wrong is what made the assistant feel unhelpful, so each
route is pinned down here.
"""
import pytest

from app.core.conversation_engine import generate_human_response

USER_ID = 12345


def reply(question: str) -> str:
    return generate_human_response(question, [], USER_ID)


# ──────────────────────────────────────────────
# EXACT ANSWERS WIN
# ──────────────────────────────────────────────

@pytest.mark.parametrize(
    "question,expected",
    [
        ("1+2", "**3**"),
        ("what is 1+2", "**3**"),
        ("What is 1 + 2?", "**3**"),
        ("2*3", "**6**"),
        ("15% of 200", "**30**"),
        ("2^10", "**1,024**"),
    ],
)
def test_arithmetic_is_answered_exactly(question, expected):
    assert expected in reply(question)


def test_conversion_is_answered():
    assert "6.21371" in reply("10 km to miles")


def test_the_original_bug_stays_fixed():
    """
    '1+2' used to return "Hey! What would you like to know?" and
    'what is 1+2' returned "Hmm, I'm not sure...". Both must compute now.
    """
    for question in ("1+2", "what is 1+2"):
        answer = reply(question)
        assert "**3**" in answer
        assert "not sure" not in answer.lower()
        assert "what would you like to know" not in answer.lower()


# ──────────────────────────────────────────────
# SMALL TALK STAYS SMALL TALK
# ──────────────────────────────────────────────

@pytest.mark.parametrize(
    "question",
    ["hello", "hi", "hey", "hi there", "good morning", "how are you", "whats up", "what's up"],
)
def test_greetings_are_not_treated_as_questions(question):
    answer = reply(question)
    assert "not sure" not in answer.lower(), f"{question!r} should be small talk"
    assert len(answer) > 0


def test_thanks_and_farewell():
    assert reply("thanks")
    assert reply("bye")
    assert "not sure" not in reply("thanks").lower()
    assert "not sure" not in reply("bye").lower()


@pytest.mark.parametrize("question", ["who are you", "what can you do"])
def test_identity_and_capability_questions(question):
    answer = reply(question)
    assert "not sure" not in answer.lower()
    assert len(answer) > 40, "should describe what the assistant offers"


def test_capability_answer_mentions_real_features():
    answer = reply("what can you do").lower()
    assert "convert" in answer or "arithmetic" in answer or "compute" in answer


# ──────────────────────────────────────────────
# KNOWLEDGE QUESTIONS
# ──────────────────────────────────────────────

@pytest.mark.parametrize(
    "question",
    [
        "what is python",
        "hey kudos, what is python?",
        "what is git",
        "what is machine learning",
        "what is the capital of France",
        "how do i study",
    ],
)
def test_known_topics_are_answered_not_deflected(question):
    answer = reply(question)
    assert "upload" not in answer.lower(), f"{question!r} should not demand a document"
    assert "not sure" not in answer.lower()


# ──────────────────────────────────────────────
# HONEST FALLBACK
# ──────────────────────────────────────────────

def test_genuinely_unknown_question_falls_back_gracefully():
    answer = reply("what did my lecturer say about topic seventeen last Tuesday")
    assert answer, "must always return something"
    assert isinstance(answer, str)


def test_never_returns_empty():
    for question in ["", "   ", "?", "asdfgh", "1+2", "hello"]:
        assert reply(question).strip(), f"{question!r} produced an empty reply"
