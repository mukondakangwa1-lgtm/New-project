"""
KUDOS Reasoning Core — deterministic "always right" skills.

This module answers the class of questions that must NEVER be guessed at:
arithmetic, percentages, unit conversions, dates/times and a few
self-knowledge questions. It runs BEFORE the knowledge base and before any
LLM, so `1+2` is always `3` — instantly, offline, and for free.

Design rules:
  * Deterministic. Same input -> same output. No randomness.
  * Safe. Expressions are parsed with `ast` and walked against an allow-list.
    `eval()` is never used on user input.
  * Conservative. A skill returns None unless it is confident, so ordinary
    conversation falls through to the LLM / knowledge base untouched.

Public API:
    solve(query) -> Optional[Skill result dict]
        {"answer": str, "skill": str, "confidence": float, "value": Any}
"""
from __future__ import annotations

import ast
import math
import operator
import re
from datetime import datetime, timezone
from typing import Any, Callable, Optional

# ──────────────────────────────────────────────
# NUMBER FORMATTING
# ──────────────────────────────────────────────

MAX_DECIMALS = 10


def format_measurement(value: float, significant: int = 6) -> str:
    """
    Format a converted measurement at a sensible precision.

    Conversions are approximations, so trailing noise like
    6.2137119224 miles is unhelpful — 6.21371 reads far better.
    """
    if value == 0:
        return "0"
    if isinstance(value, int) or float(value).is_integer():
        return format_number(value)

    magnitude = math.floor(math.log10(abs(value)))
    decimals = max(0, significant - 1 - magnitude)
    rounded = round(value, min(decimals, MAX_DECIMALS))
    return format_number(rounded)


def pluralize_unit(name: str, value: float) -> str:
    """Use the singular unit name when the amount is exactly one."""
    if abs(value) != 1:
        return name

    irregular = {
        "feet": "foot",
        "inches": "inch",
        "stone": "stone",
        "knots": "knot",
    }
    if name in irregular:
        return irregular[name]
    if name.endswith("es") and name.endswith(("ches", "shes", "xes", "sses")):
        return name[:-2]
    if name.endswith("s") and not name.endswith("ss"):
        return name[:-1]
    return name


def format_number(value: Any) -> str:
    """Render a number the way a human would write it."""
    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, int):
        return f"{value:,}"

    if isinstance(value, float):
        if math.isnan(value):
            return "undefined"
        if math.isinf(value):
            return "infinity" if value > 0 else "-infinity"

        rounded = round(value, MAX_DECIMALS)

        # Present integral floats as integers: 3.0 -> "3"
        if rounded == int(rounded) and abs(rounded) < 1e15:
            return f"{int(rounded):,}"

        # Very large / very small numbers read better in scientific notation
        if abs(rounded) >= 1e15 or (0 < abs(rounded) < 1e-6):
            return f"{rounded:.6g}"

        text = f"{rounded:,.{MAX_DECIMALS}f}".rstrip("0").rstrip(".")
        return text or "0"

    return str(value)


# ──────────────────────────────────────────────
# SAFE EXPRESSION EVALUATOR
# ──────────────────────────────────────────────

class MathError(Exception):
    """Raised when an expression is invalid or disallowed."""


_BIN_OPS: dict[type, Callable] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS: dict[type, Callable] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_log(x, base=None):
    return math.log(x) if base is None else math.log(x, base)


_FUNCTIONS: dict[str, Callable] = {
    "sqrt": math.sqrt,
    "cbrt": lambda x: math.copysign(abs(x) ** (1 / 3), x),
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "min": min,
    "max": max,
    "sum": lambda *a: sum(a),
    "pow": pow,
    "exp": math.exp,
    "log": _safe_log,
    "ln": math.log,
    "log2": math.log2,
    "log10": math.log10,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "degrees": math.degrees,
    "radians": math.radians,
    "factorial": lambda x: math.factorial(int(x)),
    "gcd": math.gcd,
    "lcm": getattr(math, "lcm", lambda a, b: abs(a * b) // math.gcd(int(a), int(b))),
}

_CONSTANTS: dict[str, float] = {
    "pi": math.pi,
    "tau": math.tau,
    "e": math.e,
    "inf": math.inf,
}

_ALLOWED_NAMES = set(_FUNCTIONS) | set(_CONSTANTS)

# Guard rails so nobody can wedge the server with 10**10**10
_MAX_POW_EXPONENT = 10_000
_MAX_FACTORIAL = 1_000


def _eval_node(node: ast.AST) -> Any:
    """Recursively evaluate an allow-listed AST node."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    # Literals
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise MathError("only numeric literals are allowed")

    # Binary operations
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BIN_OPS:
            raise MathError("unsupported operator")
        left = _eval_node(node.left)
        right = _eval_node(node.right)

        if op_type is ast.Pow:
            if isinstance(right, (int, float)) and abs(right) > _MAX_POW_EXPONENT:
                raise MathError("exponent too large")
            if abs(left) > 1e6 and abs(right) > 100:
                raise MathError("result too large")

        if op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right == 0:
            raise ZeroDivisionError("division by zero")

        return _BIN_OPS[op_type](left, right)

    # Unary +/-
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise MathError("unsupported unary operator")
        return _UNARY_OPS[op_type](_eval_node(node.operand))

    # Function calls
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise MathError("unsupported call")
        name = node.func.id.lower()
        if name not in _FUNCTIONS:
            raise MathError(f"unknown function '{name}'")
        if node.keywords:
            raise MathError("keyword arguments are not supported")
        args = [_eval_node(a) for a in node.args]
        if name == "factorial":
            if not args or args[0] < 0 or args[0] > _MAX_FACTORIAL:
                raise MathError("factorial out of range")
        return _FUNCTIONS[name](*args)

    # Constants like pi / e
    if isinstance(node, ast.Name):
        name = node.id.lower()
        if name in _CONSTANTS:
            return _CONSTANTS[name]
        raise MathError(f"unknown name '{name}'")

    # Comparisons: "is 5 > 3"
    if isinstance(node, ast.Compare):
        if len(node.ops) != 1:
            raise MathError("chained comparisons are not supported")
        left = _eval_node(node.left)
        right = _eval_node(node.comparators[0])
        op = node.ops[0]
        comparators = {
            ast.Eq: operator.eq, ast.NotEq: operator.ne,
            ast.Lt: operator.lt, ast.LtE: operator.le,
            ast.Gt: operator.gt, ast.GtE: operator.ge,
        }
        if type(op) not in comparators:
            raise MathError("unsupported comparison")
        return comparators[type(op)](left, right)

    raise MathError("unsupported expression")


def evaluate_expression(expression: str) -> Any:
    """Safely evaluate a normalized arithmetic expression string."""
    if len(expression) > 500:
        raise MathError("expression too long")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise MathError("could not parse expression") from exc
    return _eval_node(tree)


# ──────────────────────────────────────────────
# NATURAL LANGUAGE -> EXPRESSION
# ──────────────────────────────────────────────

# Phrases that merely introduce the question and carry no math meaning.
_PREFIXES = [
    r"what(?:'s|s| is| are)?",
    r"how much (?:is|are)",
    r"how many (?:is|are)",
    r"can you (?:please )?(?:tell me |calculate |compute |work out |solve )?",
    r"please",
    r"tell me",
    r"calculate",
    r"compute",
    r"evaluate",
    r"solve(?: for me)?",
    r"work out",
    r"the (?:answer|result|value) (?:of|to|for)",
    r"answer",
    r"result of",
    r"equals?",
    r"give me",
    r"i want to know",
    r"do the math(?:s)? (?:for|on)",
    r"math(?:s)?",
]

# Ordered longest-first so multi-word phrases win over single words.
_WORD_OPERATORS: list[tuple[str, str]] = [
    (r"\bmultiplied\s+by\b", "*"),
    (r"\bdivided\s+by\b", "/"),
    (r"\bto\s+the\s+power\s+(?:of\s+)?\b", "**"),
    (r"\braised\s+to\s+(?:the\s+power\s+(?:of\s+)?)?\b", "**"),
    (r"\bsquare\s+root\s+of\b", "sqrt"),
    (r"\bcube\s+root\s+of\b", "cbrt"),
    (r"\bfactorial\s+of\b", "factorial"),
    (r"\bremainder\s+of\b", ""),
    (r"\bmodulo\b", "%"),
    (r"\bmod\b", "%"),
    (r"\bplus\b", "+"),
    (r"\badd(?:ed\s+to)?\b", "+"),
    (r"\bminus\b", "-"),
    (r"\bsubtract(?:ed\s+from)?\b", "-"),
    (r"\btimes\b", "*"),
    (r"\bmultiply(?:\s+by)?\b", "*"),
    (r"\bdivide(?:\s+by)?\b", "/"),
    (r"\bover\b", "/"),
]

_SUFFIX_OPERATORS: list[tuple[str, str]] = [
    (r"\bsquared\b", "**2"),
    (r"\bcubed\b", "**3"),
]

# Patterns that look numeric but are not arithmetic questions.
_NOT_MATH = [
    # Year ranges written tightly and ascending: "2020-2024", "1990–2000".
    # Spaced ("2020 - 1990") or descending forms are treated as subtraction,
    # since that is what someone typing them into a chat box usually means.
    re.compile(r"^\s*(?P<start>(?:19|20)\d{2})[-–](?P<end>(?:19|20)\d{2})\s*$"),
    re.compile(r"^\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*$"),  # dates: 3/4/2025
    re.compile(r"^\s*v?\d+(\.\d+){2,}\s*$"),               # versions: 1.2.3
    # Phone numbers: 7+ digits with separators, e.g. "+1 (555) 123-4567".
    # Requires either a leading "+"/"(" or at least 9 digits, so ordinary
    # subtraction like "100 - 50" is not mistaken for a phone number.
    re.compile(r"^\s*(?:\+\d[\d\s\-()]{6,}|\(\d[\d\s\-()]{6,}|(?:[\d\s\-()]*\d){9,}[\d\s\-()]*)\s*$"),
]


def _strip_prefixes(text: str) -> str:
    changed = True
    while changed:
        changed = False
        for prefix in _PREFIXES:
            pattern = re.compile(rf"^\s*{prefix}\b[\s:,]*", re.IGNORECASE)
            new_text = pattern.sub("", text, count=1)
            if new_text != text:
                text, changed = new_text, True
    return text.strip()


def normalize_expression(query: str) -> Optional[str]:
    """
    Turn a natural-language arithmetic question into a bare expression.

    Returns None when the text does not look like pure arithmetic — that
    conservatism is what keeps normal conversation out of the math path.
    """
    text = query.strip().lower()
    if not text:
        return None

    for pattern in _NOT_MATH:
        if pattern.match(text):
            return None

    # Drop trailing punctuation and a trailing "=". A trailing "!" is kept
    # when it follows a digit, because there it means factorial ("5!").
    text = re.sub(r"[?.\s]+$", "", text)
    if not re.search(r"\d\s*!$", text):
        text = text.rstrip("! \t")
    text = re.sub(r"=\s*$", "", text).strip()
    text = _strip_prefixes(text)
    if not text:
        return None

    # Percent-of: "15% of 200" / "15 percent of 200"
    text = re.sub(
        r"(\d+(?:\.\d+)?)\s*(?:%|percent(?:age)?)\s+of\s+",
        r"(\1/100)*",
        text,
    )
    # Any remaining trailing percent: "10% + 5" -> "(10/100) + 5"
    text = re.sub(r"(\d+(?:\.\d+)?)\s*percent\b", r"(\1/100)", text)

    # Word operators (longest first).
    for pattern, replacement in _WORD_OPERATORS:
        text = re.sub(pattern, replacement, text)
    for pattern, replacement in _SUFFIX_OPERATORS:
        text = re.sub(pattern, replacement, text)

    # "3 x 4" -> "3 * 4" (only between numbers, so "x" as a variable is safe)
    text = re.sub(r"(?<=\d)\s*[x×]\s*(?=\d|\()", "*", text)
    text = text.replace("×", "*").replace("÷", "/")

    # Caret means exponent in everyday writing.
    text = text.replace("^", "**")

    # Postfix factorial: "5!" -> "factorial(5)"
    text = re.sub(r"(\d+(?:\.\d+)?)\s*!", r"factorial(\1)", text)

    # "sqrt 16" -> "sqrt(16)" for bare function application.
    text = re.sub(
        r"\b(sqrt|cbrt|factorial|abs|ln|log10|log2|log|sin|cos|tan|exp)\s+"
        r"(-?\d+(?:\.\d+)?|\()",
        lambda m: f"{m.group(1)}({m.group(2)}" if m.group(2) == "(" else f"{m.group(1)}({m.group(2)})",
        text,
    )

    # Thousands separators inside numbers: 1,234 -> 1234
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)

    # Strip currency symbols and stray whitespace.
    text = re.sub(r"[$£€¥]", "", text).strip()

    if not text:
        return None

    # Must contain at least one digit or a known constant.
    if not re.search(r"\d", text) and not re.search(r"\b(pi|tau|e)\b", text):
        return None

    # Must contain an operator or a function call — a bare "42" is not a question.
    if not re.search(r"[+\-*/%()!]|\b(sqrt|cbrt|factorial|log|ln|sin|cos|tan|exp|abs|round|min|max|gcd|lcm|pow|floor|ceil)\b", text):
        return None

    # Every alphabetic token left must be an allowed function or constant.
    for token in re.findall(r"[a-z_]+", text):
        if token not in _ALLOWED_NAMES:
            return None

    # Only math characters may remain.
    if not re.fullmatch(r"[\d\s+\-*/%^().,a-z_<>=]+", text):
        return None

    return text


# ──────────────────────────────────────────────
# SKILL: ARITHMETIC
# ──────────────────────────────────────────────

def skill_math(query: str) -> Optional[dict]:
    expression = normalize_expression(query)
    if not expression:
        return None

    try:
        value = evaluate_expression(expression)
    except ZeroDivisionError:
        return {
            "answer": (
                "That would mean dividing by zero, which is undefined in mathematics — "
                "there's no number you can multiply by 0 to get a non-zero result."
            ),
            "skill": "math",
            "confidence": 1.0,
            "value": None,
        }
    except (MathError, ValueError, OverflowError, TypeError, RecursionError):
        return None

    if isinstance(value, bool):
        return {
            "answer": "Yes, that's correct." if value else "No, that's not correct.",
            "skill": "math",
            "confidence": 1.0,
            "value": value,
        }

    if not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None

    pretty = format_number(value)
    return {
        "answer": f"**{pretty}**",
        "skill": "math",
        "confidence": 1.0,
        "value": value,
        "expression": expression,
    }


# ──────────────────────────────────────────────
# SKILL: UNIT CONVERSION
# ──────────────────────────────────────────────

# Each entry: canonical -> (dimension, factor to base unit, display name)
_UNITS: dict[str, tuple[str, float, str]] = {
    # Length (base: metre)
    "mm": ("length", 0.001, "millimetres"),
    "cm": ("length", 0.01, "centimetres"),
    "m": ("length", 1.0, "metres"),
    "km": ("length", 1000.0, "kilometres"),
    "in": ("length", 0.0254, "inches"),
    "ft": ("length", 0.3048, "feet"),
    "yd": ("length", 0.9144, "yards"),
    "mi": ("length", 1609.344, "miles"),
    "nmi": ("length", 1852.0, "nautical miles"),
    # Mass (base: kilogram)
    "mg": ("mass", 1e-6, "milligrams"),
    "g": ("mass", 0.001, "grams"),
    "kg": ("mass", 1.0, "kilograms"),
    "t": ("mass", 1000.0, "tonnes"),
    "oz": ("mass", 0.028349523125, "ounces"),
    "lb": ("mass", 0.45359237, "pounds"),
    "st": ("mass", 6.35029318, "stone"),
    # Volume (base: litre)
    "ml": ("volume", 0.001, "millilitres"),
    "l": ("volume", 1.0, "litres"),
    "gal": ("volume", 3.785411784, "US gallons"),
    "qt": ("volume", 0.946352946, "US quarts"),
    "pt": ("volume", 0.473176473, "US pints"),
    "cup": ("volume", 0.2365882365, "cups"),
    "floz": ("volume", 0.0295735295625, "US fluid ounces"),
    # Time (base: second)
    "ms": ("time", 0.001, "milliseconds"),
    "s": ("time", 1.0, "seconds"),
    "min": ("time", 60.0, "minutes"),
    "h": ("time", 3600.0, "hours"),
    "day": ("time", 86400.0, "days"),
    "week": ("time", 604800.0, "weeks"),
    "year": ("time", 31557600.0, "years"),
    # Digital storage (base: byte)
    "b": ("data", 1.0, "bytes"),
    "kb": ("data", 1000.0, "kilobytes"),
    "mb": ("data", 1e6, "megabytes"),
    "gb": ("data", 1e9, "gigabytes"),
    "tb": ("data", 1e12, "terabytes"),
    "kib": ("data", 1024.0, "kibibytes"),
    "mib": ("data", 1024.0 ** 2, "mebibytes"),
    "gib": ("data", 1024.0 ** 3, "gibibytes"),
    # Speed (base: metres/second)
    "mps": ("speed", 1.0, "metres per second"),
    "kmh": ("speed", 1 / 3.6, "kilometres per hour"),
    "mph": ("speed", 0.44704, "miles per hour"),
    "knot": ("speed", 0.514444, "knots"),
}

_UNIT_ALIASES: dict[str, str] = {
    "millimetre": "mm", "millimeter": "mm", "millimetres": "mm", "millimeters": "mm",
    "centimetre": "cm", "centimeter": "cm", "centimetres": "cm", "centimeters": "cm",
    "metre": "m", "meter": "m", "metres": "m", "meters": "m",
    "kilometre": "km", "kilometer": "km", "kilometres": "km", "kilometers": "km", "kms": "km",
    "inch": "in", "inches": "in", '"': "in",
    "foot": "ft", "feet": "ft",
    "yard": "yd", "yards": "yd",
    "mile": "mi", "miles": "mi",
    "milligram": "mg", "milligrams": "mg",
    "gram": "g", "grams": "g", "gramme": "g", "grammes": "g",
    "kilogram": "kg", "kilograms": "kg", "kilo": "kg", "kilos": "kg", "kgs": "kg",
    "tonne": "t", "tonnes": "t", "ton": "t", "tons": "t",
    "ounce": "oz", "ounces": "oz",
    "pound": "lb", "pounds": "lb", "lbs": "lb",
    "stones": "st",
    "millilitre": "ml", "milliliter": "ml", "millilitres": "ml", "milliliters": "ml",
    "litre": "l", "liter": "l", "litres": "l", "liters": "l",
    "gallon": "gal", "gallons": "gal",
    "quart": "qt", "quarts": "qt",
    "pint": "pt", "pints": "pt",
    "cups": "cup",
    "fluidounce": "floz", "fluidounces": "floz", "ozfl": "floz",
    "millisecond": "ms", "milliseconds": "ms", "msec": "ms",
    "second": "s", "seconds": "s", "sec": "s", "secs": "s",
    "minute": "min", "minutes": "min", "mins": "min",
    "hour": "h", "hours": "h", "hr": "h", "hrs": "h",
    "days": "day", "weeks": "week", "years": "year", "yr": "year", "yrs": "year",
    "byte": "b", "bytes": "b",
    "kilobyte": "kb", "kilobytes": "kb",
    "megabyte": "mb", "megabytes": "mb",
    "gigabyte": "gb", "gigabytes": "gb",
    "terabyte": "tb", "terabytes": "tb",
    "kibibyte": "kib", "mebibyte": "mib", "gibibyte": "gib",
    "kph": "kmh", "kmph": "kmh", "km/h": "kmh", "kmperhour": "kmh",
    "m/s": "mps", "mpersecond": "mps",
    "milesperhour": "mph", "mi/h": "mph",
    "knots": "knot",
}

_TEMPERATURE_ALIASES: dict[str, str] = {
    "c": "c", "celsius": "c", "centigrade": "c", "°c": "c", "degreescelsius": "c",
    "f": "f", "fahrenheit": "f", "°f": "f", "degreesfahrenheit": "f",
    "k": "k", "kelvin": "k", "°k": "k",
}


def _canonical_unit(raw: str) -> Optional[str]:
    token = raw.strip().lower().replace("°", "").replace(".", "")
    if token in _UNITS:
        return token
    compact = token.replace(" ", "").replace("/", "")
    if token in _UNIT_ALIASES:
        return _UNIT_ALIASES[token]
    if compact in _UNIT_ALIASES:
        return _UNIT_ALIASES[compact]
    if compact in _UNITS:
        return compact
    return None


def _canonical_temperature(raw: str) -> Optional[str]:
    token = raw.strip().lower().replace(" ", "").replace(".", "")
    token = re.sub(r"^degrees?", "", token)
    return _TEMPERATURE_ALIASES.get(token)


def _convert_temperature(value: float, src: str, dst: str) -> float:
    # Normalize to celsius first
    if src == "c":
        celsius = value
    elif src == "f":
        celsius = (value - 32) * 5 / 9
    else:  # kelvin
        celsius = value - 273.15

    if dst == "c":
        return celsius
    if dst == "f":
        return celsius * 9 / 5 + 32
    return celsius + 273.15


_TEMP_NAMES = {"c": "°C", "f": "°F", "k": "K"}

_CONVERSION_PATTERNS = [
    # "10 km to miles" / "convert 10 km into miles"
    re.compile(
        r"^(?:convert\s+)?(-?[\d,]+(?:\.\d+)?)\s*([a-z°/\"]+(?:\s+[a-z]+)?)\s+"
        r"(?:to|in|into|as|=)\s+([a-z°/\"]+(?:\s+[a-z]+)?)$",
        re.IGNORECASE,
    ),
    # "how many miles in 10 km"
    re.compile(
        r"^how many\s+([a-z°/\"]+(?:\s+[a-z]+)?)\s+(?:are\s+)?(?:in|is)\s+"
        r"(-?[\d,]+(?:\.\d+)?)\s*([a-z°/\"]+(?:\s+[a-z]+)?)$",
        re.IGNORECASE,
    ),
]


def skill_convert(query: str) -> Optional[dict]:
    text = query.strip().rstrip("?!. \t").lower()
    text = _strip_prefixes(text) if text.startswith(("what", "how much")) else text
    text = text.strip()
    if not text:
        return None

    amount_raw = src_raw = dst_raw = None

    match = _CONVERSION_PATTERNS[0].match(text)
    if match:
        amount_raw, src_raw, dst_raw = match.group(1), match.group(2), match.group(3)
    else:
        match = _CONVERSION_PATTERNS[1].match(text)
        if match:
            dst_raw, amount_raw, src_raw = match.group(1), match.group(2), match.group(3)

    if not amount_raw:
        return None

    try:
        amount = float(amount_raw.replace(",", ""))
    except ValueError:
        return None

    # Temperature is affine, so it gets its own path.
    src_temp, dst_temp = _canonical_temperature(src_raw), _canonical_temperature(dst_raw)
    if src_temp and dst_temp:
        result = _convert_temperature(amount, src_temp, dst_temp)
        return {
            "answer": (
                f"**{format_number(amount)}{_TEMP_NAMES[src_temp]} = "
                f"{format_number(round(result, 2))}{_TEMP_NAMES[dst_temp]}**"
            ),
            "skill": "convert",
            "confidence": 1.0,
            "value": result,
        }

    src, dst = _canonical_unit(src_raw), _canonical_unit(dst_raw)
    if not src or not dst:
        return None

    src_dim, src_factor, src_name = _UNITS[src]
    dst_dim, dst_factor, dst_name = _UNITS[dst]

    if src_dim != dst_dim:
        return {
            "answer": (
                f"I can't convert {src_name} ({src_dim}) into {dst_name} ({dst_dim}) — "
                "those measure different things."
            ),
            "skill": "convert",
            "confidence": 1.0,
            "value": None,
        }

    result = amount * src_factor / dst_factor
    return {
        "answer": (
            f"**{format_number(amount)} {pluralize_unit(src_name, amount)} = "
            f"{format_measurement(result)} {pluralize_unit(dst_name, result)}**"
        ),
        "skill": "convert",
        "confidence": 1.0,
        "value": result,
    }


# ──────────────────────────────────────────────
# SKILL: DATE & TIME
# ──────────────────────────────────────────────

_DATE_PATTERNS = re.compile(
    r"\b(what(?:'s| is)?\s+(?:the\s+)?(?:today'?s?\s+)?(?:date|day|time)"
    r"|what\s+day\s+is\s+it"
    r"|what\s+time\s+is\s+it"
    r"|what\s+is\s+today"
    r"|what\s+year\s+is\s+it"
    r"|what\s+month\s+is\s+it"
    r"|today'?s?\s+date)\b",
    re.IGNORECASE,
)


def skill_datetime(query: str, now: Optional[datetime] = None) -> Optional[dict]:
    text = query.strip().lower().rstrip("?!. ")
    if not _DATE_PATTERNS.search(text):
        return None

    now = now or datetime.now(timezone.utc)

    if "time" in text:
        answer = (
            f"It's **{now.strftime('%H:%M')} UTC** on "
            f"{now.strftime('%A, %d %B %Y')}."
        )
    elif "year" in text:
        answer = f"It's **{now.year}**."
    elif "month" in text:
        answer = f"It's **{now.strftime('%B %Y')}**."
    else:
        answer = f"Today is **{now.strftime('%A, %d %B %Y')}** (UTC)."

    return {"answer": answer, "skill": "datetime", "confidence": 1.0, "value": now.isoformat()}


# ──────────────────────────────────────────────
# SKILL REGISTRY
# ──────────────────────────────────────────────

SKILLS: list[Callable[[str], Optional[dict]]] = [
    skill_datetime,
    skill_convert,
    skill_math,
]


def solve(query: str) -> Optional[dict]:
    """
    Try every deterministic skill in priority order.

    Returns the first confident result, or None so the caller can fall
    through to the LLM / knowledge base.
    """
    if not query or not query.strip():
        return None
    if len(query) > 1000:
        return None

    for skill in SKILLS:
        try:
            result = skill(query)
        except Exception:
            continue
        if result and result.get("answer"):
            return result
    return None


def can_answer(query: str) -> bool:
    """Cheap check used by routers that only need a yes/no."""
    return solve(query) is not None
