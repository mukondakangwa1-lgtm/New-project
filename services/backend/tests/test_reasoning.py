"""
Tests for the KUDOS reasoning core.

Two things matter here:
  1. Questions with an exact answer are ALWAYS answered correctly.
  2. Ordinary conversation is NEVER hijacked by the calculator.

The second is what keeps the assistant feeling natural, so the
false-positive suite is as important as the correctness suite.
"""
import math

import pytest

from app.core.reasoning import (
    MathError,
    evaluate_expression,
    format_number,
    normalize_expression,
    solve,
)


# ──────────────────────────────────────────────
# CORE ARITHMETIC
# ──────────────────────────────────────────────

@pytest.mark.parametrize(
    "query,expected",
    [
        ("1+2", 3),
        ("1 + 2", 3),
        ("what is 1+2", 3),
        ("What is 1 + 2?", 3),
        ("whats 1+2", 3),
        ("calculate 1+2", 3),
        ("1+2 =", 3),
        ("2*3", 6),
        ("7-9", -2),
        ("10/4", 2.5),
        ("2^10", 1024),
        ("2**10", 1024),
        ("(2+3)*4", 20),
        ("100 - 50", 50),
        ("17 % 5", 2),
        ("-5 + 3", -2),
    ],
)
def test_basic_arithmetic(query, expected):
    result = solve(query)
    assert result is not None, f"{query!r} should be solved"
    assert result["skill"] == "math"
    assert result["value"] == pytest.approx(expected)


@pytest.mark.parametrize(
    "query,expected",
    [
        ("what is 12 divided by 4", 3),
        ("5 plus 5", 10),
        ("10 minus 3", 7),
        ("6 times 7", 42),
        ("3 multiplied by 4", 12),
        ("100 divided by 8", 12.5),
        ("10 to the power of 3", 1000),
        ("5 squared", 25),
        ("3 cubed", 27),
        ("square root of 144", 12),
        ("3 x 4", 12),
    ],
)
def test_word_arithmetic(query, expected):
    result = solve(query)
    assert result is not None, f"{query!r} should be solved"
    assert result["value"] == pytest.approx(expected)


@pytest.mark.parametrize(
    "query,expected",
    [
        ("15% of 200", 30),
        ("50% of 80", 40),
        ("what is 20% of 150", 30),
        ("100 - 15% of 200", 70),
    ],
)
def test_percentages(query, expected):
    result = solve(query)
    assert result is not None
    assert result["value"] == pytest.approx(expected)


@pytest.mark.parametrize(
    "query,expected",
    [
        ("sqrt(16)", 4),
        ("5!", 120),
        ("factorial of 5", 120),
        ("abs(-7)", 7),
        ("max(3,9)", 9),
        ("min(3,9)", 3),
        ("gcd(12,18)", 6),
        ("round(3.7)", 4),
        ("floor(3.7)", 3),
        ("ceil(3.2)", 4),
        ("log10(1000)", 3),
    ],
)
def test_functions(query, expected):
    result = solve(query)
    assert result is not None, f"{query!r} should be solved"
    assert result["value"] == pytest.approx(expected)


def test_thousands_separator():
    assert solve("1,234 + 1")["value"] == 1235


def test_pi_constant():
    assert solve("pi * 2")["value"] == pytest.approx(2 * math.pi)


def test_answer_is_formatted_for_humans():
    assert solve("1+2")["answer"] == "**3**"
    # Integral floats should not render as "3.0"
    assert solve("10/5")["answer"] == "**2**"
    # Large numbers get thousands separators
    assert solve("2^20")["answer"] == "**1,048,576**"


def test_division_by_zero_is_explained_not_crashed():
    result = solve("100/0")
    assert result is not None
    assert "undefined" in result["answer"].lower()
    assert result["value"] is None


def test_determinism():
    """The same question must always give the same answer."""
    answers = {solve("what is 1+2")["answer"] for _ in range(50)}
    assert answers == {"**3**"}


# ──────────────────────────────────────────────
# FALSE POSITIVES — the important suite
# ──────────────────────────────────────────────

@pytest.mark.parametrize(
    "query",
    [
        "hello",
        "hi there",
        "how are you",
        "who are you",
        "what is python",
        "what is the capital of France",
        "tell me about world war 2",
        "my grade is 85",
        "I have 3 assignments due",
        "I scored 90 out of 100",
        "2020-2024",
        "3/4/2025",
        "v1.2.3",
        "room 101",
        "COVID-19",
        "chapter 5",
        "call me at 555 123 4567",
        "explain 2+2 to a child",
        "what is 1+1 in binary and why",
        "thanks",
        "",
        "   ",
    ],
)
def test_does_not_hijack_normal_conversation(query):
    assert solve(query) is None, f"{query!r} must fall through to the LLM"


def test_bare_number_is_not_a_question():
    assert solve("42") is None
    assert normalize_expression("42") is None


# ──────────────────────────────────────────────
# SAFETY
# ──────────────────────────────────────────────

@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('ls')",
        "open('/etc/passwd').read()",
        "().__class__.__bases__",
        "exec('x=1')",
        "eval('1+1')",
        "lambda: 1",
        "[i for i in range(10)]",
    ],
)
def test_code_injection_is_rejected(expression):
    """The evaluator must never execute arbitrary Python."""
    with pytest.raises((MathError, ValueError, SyntaxError, TypeError)):
        evaluate_expression(expression)


def test_injection_via_solve_returns_none():
    assert solve("__import__('os').system('ls')") is None


def test_huge_exponent_is_refused():
    with pytest.raises(MathError):
        evaluate_expression("10**999999")


def test_overlong_input_is_refused():
    assert solve("1+" * 600 + "1") is None


# ──────────────────────────────────────────────
# UNIT CONVERSION
# ──────────────────────────────────────────────

@pytest.mark.parametrize(
    "query,expected",
    [
        ("10 km to miles", 6.21371),
        ("1 mile to km", 1.609344),
        ("2 feet to inches", 24),
        ("5 kg to pounds", 11.023113),
        ("convert 100 cm to m", 1),
        ("how many inches in 2 feet", 24),
        ("1 gb to mb", 1000),
        ("2 hours to minutes", 120),
    ],
)
def test_unit_conversion(query, expected):
    result = solve(query)
    assert result is not None, f"{query!r} should convert"
    assert result["skill"] == "convert"
    assert result["value"] == pytest.approx(expected, rel=1e-4)


@pytest.mark.parametrize(
    "query,expected",
    [
        ("100 c to f", 212),
        ("32 f to c", 0),
        ("25 celsius in fahrenheit", 77),
        ("0 c to k", 273.15),
    ],
)
def test_temperature_conversion(query, expected):
    result = solve(query)
    assert result is not None
    assert result["value"] == pytest.approx(expected, rel=1e-4)


def test_incompatible_units_explained():
    result = solve("10 kg to miles")
    assert result is not None
    assert "different things" in result["answer"]


def test_singular_unit_grammar():
    assert "1 gigabyte =" in solve("1 gb to mb")["answer"]
    assert "1 mile =" in solve("1 mile to km")["answer"]


# ──────────────────────────────────────────────
# DATE / TIME
# ──────────────────────────────────────────────

@pytest.mark.parametrize(
    "query",
    ["what is today", "what's the date", "what day is it", "what time is it", "what year is it"],
)
def test_datetime_answered(query):
    result = solve(query)
    assert result is not None
    assert result["skill"] == "datetime"


# ──────────────────────────────────────────────
# FORMATTING
# ──────────────────────────────────────────────

def test_format_number():
    assert format_number(3) == "3"
    assert format_number(3.0) == "3"
    assert format_number(2.5) == "2.5"
    assert format_number(1000000) == "1,000,000"
    assert format_number(-42) == "-42"
