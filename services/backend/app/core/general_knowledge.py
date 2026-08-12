"""
KUDOS General Knowledge — a small, curated offline fact base.

Purpose: when no LLM key is configured and the knowledge base has nothing,
KUDOS should still answer common questions instead of replying
"upload a document about it". This covers the everyday questions students
actually ask a campus assistant.

This is intentionally small and hand-written. It is a safety net for the
offline case, not a replacement for a real model — `solve()` in
`reasoning.py` handles anything computable, and the LLM handles the
long tail when a key is present.
"""
from __future__ import annotations

import re
from typing import Optional

# ──────────────────────────────────────────────
# FACT BASE
# Each entry: (trigger keywords, required keyword groups, answer)
# ──────────────────────────────────────────────

_FACTS: list[tuple[list[str], str]] = [
    # ── Self / platform ───────────────────────
    (
        ["what is kudos", "who is kudos", "what does kudos do"],
        "I'm KUDOS 🧠 — the AI assistant built into Digital Campus. I can answer "
        "questions, do exact calculations and conversions, learn from documents "
        "and web pages you give me, and help you with courses, attendance, "
        "assignments and study planning.",
    ),
    (
        ["what is digital campus"],
        "Digital Campus is a unified university platform — courses, attendance, "
        "assignments, exams, study groups, chat and a social hub, all in one "
        "place, with me (KUDOS) built in as your AI assistant.",
    ),

    # ── Programming ───────────────────────────
    (
        ["what is python"],
        "**Python** is a high-level, general-purpose programming language known for "
        "readable, English-like syntax.\n\n"
        "• Created by Guido van Rossum, first released in 1991\n"
        "• Dynamically typed and interpreted\n"
        "• Huge standard library plus packages via `pip`\n"
        "• Widely used for web backends, data science, AI/ML, automation and scripting",
    ),
    (
        ["what is javascript"],
        "**JavaScript** is the programming language of the web — it runs in every "
        "browser and, via Node.js, on servers too.\n\n"
        "• Created by Brendan Eich in 1995\n"
        "• Dynamically typed, event-driven, supports async/await\n"
        "• Powers frameworks like React, Vue, Next.js and Express",
    ),
    (
        ["what is typescript"],
        "**TypeScript** is JavaScript with static types added. You write typed code, "
        "the compiler checks it, and it compiles down to plain JavaScript. It catches "
        "whole classes of bugs before you run anything, which is why large codebases "
        "(like this platform's frontend) use it.",
    ),
    (
        ["what is html"],
        "**HTML** (HyperText Markup Language) is the structure layer of a web page. "
        "It uses tags like `<h1>`, `<p>` and `<div>` to describe headings, paragraphs "
        "and sections. CSS then styles it and JavaScript makes it interactive.",
    ),
    (
        ["what is css"],
        "**CSS** (Cascading Style Sheets) controls how a web page looks — colours, "
        "fonts, spacing and layout. Modern CSS uses Flexbox and Grid for layout, and "
        "media queries to adapt to different screen sizes.",
    ),
    (
        ["what is sql"],
        "**SQL** (Structured Query Language) is the language for working with "
        "relational databases.\n\n"
        "• `SELECT` reads data, `INSERT` adds it, `UPDATE` changes it, `DELETE` removes it\n"
        "• `JOIN` combines rows across tables\n"
        "• `WHERE` filters, `GROUP BY` aggregates, `ORDER BY` sorts",
    ),
    (
        ["what is an api", "what is api"],
        "An **API** (Application Programming Interface) is a defined way for two "
        "programs to talk to each other. A web API exposes endpoints (URLs) that "
        "accept requests and return data — usually JSON. This platform's backend "
        "is a REST API built with FastAPI.",
    ),
    (
        ["what is git"],
        "**Git** is a distributed version control system — it tracks every change to "
        "your code so you can review history, branch, and collaborate.\n\n"
        "• `git status` — see what changed\n"
        "• `git add` / `git commit` — stage and save a snapshot\n"
        "• `git branch` / `git merge` — work in parallel and combine\n"
        "• `git push` / `git pull` — sync with a remote like GitHub",
    ),
    (
        ["what is docker"],
        "**Docker** packages an application together with its dependencies into a "
        "*container* — a lightweight, isolated environment that runs identically on "
        "any machine. It solves the classic \"but it works on my computer\" problem.",
    ),
    (
        ["what is a variable", "what is variable"],
        "A **variable** is a named container for a value. You store data in it and "
        "refer to it by name later, e.g. `score = 90`. The name lets you reuse and "
        "change the value without rewriting the rest of your code.",
    ),
    (
        ["what is a function", "what is function"],
        "A **function** is a reusable, named block of code. You give it inputs "
        "(*arguments*), it runs its steps, and it usually returns a result. Functions "
        "keep programs organised and stop you repeating yourself.",
    ),
    (
        ["what is a loop", "what is loop"],
        "A **loop** repeats a block of code. A `for` loop runs once per item in a "
        "collection; a `while` loop keeps going as long as a condition stays true.",
    ),
    (
        ["what is recursion"],
        "**Recursion** is when a function calls itself on a smaller version of the "
        "problem until it reaches a *base case* that stops the chain. It's natural "
        "for tree traversal, factorials and divide-and-conquer algorithms.",
    ),
    (
        ["what is an algorithm", "what is algorithm"],
        "An **algorithm** is a finite, step-by-step procedure for solving a problem. "
        "Good algorithms are judged on correctness and on efficiency — how their time "
        "and memory use grow as the input gets larger (Big-O notation).",
    ),

    # ── AI / CS concepts ──────────────────────
    (
        ["what is machine learning"],
        "**Machine learning** is a branch of AI where a program learns patterns from "
        "data instead of being explicitly programmed with rules.\n\n"
        "• *Supervised* — learns from labelled examples (spam / not spam)\n"
        "• *Unsupervised* — finds structure in unlabelled data (clustering)\n"
        "• *Reinforcement* — learns by trial and error against a reward signal",
    ),
    (
        ["what is artificial intelligence", "what is ai"],
        "**Artificial intelligence** is the field of building systems that perform "
        "tasks normally requiring human intelligence — understanding language, "
        "recognising images, reasoning and making decisions. Machine learning is "
        "currently its most successful approach.",
    ),
    (
        ["what is a database", "what is database"],
        "A **database** is an organised store of data that can be queried and updated "
        "efficiently. *Relational* databases (PostgreSQL, SQLite, MySQL) store rows in "
        "tables and use SQL; *NoSQL* databases (MongoDB, Redis) use documents or "
        "key-value pairs for more flexible schemas.",
    ),
    (
        ["what is the internet"],
        "The **internet** is the global network of interconnected computer networks. "
        "Devices communicate using the TCP/IP protocol suite, addressed by IP "
        "addresses, with DNS translating human-readable names into those addresses. "
        "The Web is one service running on top of it.",
    ),

    # ── Maths concepts (definitions; the calculator does the numbers) ──
    (
        ["what is a prime number", "what is prime number", "what are prime numbers"],
        "A **prime number** is a whole number greater than 1 whose only divisors are "
        "1 and itself. The first primes are 2, 3, 5, 7, 11, 13, 17, 19, 23, 29. "
        "2 is the only even prime.",
    ),
    (
        ["what is pi", "what is the value of pi"],
        "**π (pi)** is the ratio of a circle's circumference to its diameter, "
        "approximately **3.14159265**. It's irrational — its decimal expansion never "
        "terminates or repeats.",
    ),
    (
        ["what is a percentage", "what is percentage"],
        "A **percentage** expresses a number as a fraction of 100. To find x% of a "
        "value, multiply by x/100 — e.g. 15% of 200 = 200 × 0.15 = 30. Just ask me "
        "directly and I'll calculate it exactly.",
    ),

    # ── Study skills ──────────────────────────
    (
        ["how do i study", "how to study", "study tips", "how can i study better"],
        "A few techniques with strong evidence behind them:\n\n"
        "• **Active recall** — test yourself instead of re-reading. This is the single "
        "biggest win.\n"
        "• **Spaced repetition** — revisit material after 1 day, 3 days, then a week.\n"
        "• **Pomodoro** — 25 minutes focused, 5 minute break; longer break every 4 rounds.\n"
        "• **Interleaving** — mix related topics rather than blocking one subject.\n"
        "• **Teach it back** — explaining a topic out loud exposes the gaps fast.\n\n"
        "Want me to help you build a revision timetable?",
    ),
    (
        ["how to manage time", "time management"],
        "Time management that actually holds up:\n\n"
        "• Put deadlines in one calendar, not several places\n"
        "• Rank tasks by *urgent vs important*, then do the important ones early\n"
        "• Break big tasks into pieces under an hour — vagueness causes procrastination\n"
        "• Timebox your study blocks and protect them\n"
        "• Review the week ahead every Sunday",
    ),
]

# Flatten into a lookup structure at import time.
_INDEX: list[tuple[list[str], str]] = [(triggers, answer) for triggers, answer in _FACTS]


# ──────────────────────────────────────────────────────────────────────
# CAPITAL CITIES
#
# "What is the capital of X" is one of the most common factual questions
# asked of any assistant, so it gets a dedicated resolver rather than one
# hand-written entry per country.
# ──────────────────────────────────────────────────────────────────────

_CAPITALS: dict[str, str] = {
    "zambia": "Lusaka",
    "zimbabwe": "Harare",
    "south africa": "Pretoria (executive), Cape Town (legislative) and Bloemfontein (judicial)",
    "namibia": "Windhoek",
    "botswana": "Gaborone",
    "malawi": "Lilongwe",
    "mozambique": "Maputo",
    "tanzania": "Dodoma",
    "kenya": "Nairobi",
    "uganda": "Kampala",
    "rwanda": "Kigali",
    "ethiopia": "Addis Ababa",
    "nigeria": "Abuja",
    "ghana": "Accra",
    "egypt": "Cairo",
    "morocco": "Rabat",
    "angola": "Luanda",
    "congo": "Kinshasa",
    "drc": "Kinshasa",
    "france": "Paris",
    "germany": "Berlin",
    "italy": "Rome",
    "spain": "Madrid",
    "portugal": "Lisbon",
    "netherlands": "Amsterdam",
    "belgium": "Brussels",
    "switzerland": "Bern",
    "austria": "Vienna",
    "sweden": "Stockholm",
    "norway": "Oslo",
    "denmark": "Copenhagen",
    "finland": "Helsinki",
    "poland": "Warsaw",
    "greece": "Athens",
    "ireland": "Dublin",
    "russia": "Moscow",
    "ukraine": "Kyiv",
    "turkey": "Ankara",
    "united kingdom": "London",
    "uk": "London",
    "england": "London",
    "scotland": "Edinburgh",
    "wales": "Cardiff",
    "united states": "Washington, D.C.",
    "usa": "Washington, D.C.",
    "us": "Washington, D.C.",
    "america": "Washington, D.C.",
    "canada": "Ottawa",
    "mexico": "Mexico City",
    "brazil": "Brasília",
    "argentina": "Buenos Aires",
    "chile": "Santiago",
    "peru": "Lima",
    "colombia": "Bogotá",
    "china": "Beijing",
    "japan": "Tokyo",
    "india": "New Delhi",
    "pakistan": "Islamabad",
    "bangladesh": "Dhaka",
    "indonesia": "Jakarta",
    "thailand": "Bangkok",
    "vietnam": "Hanoi",
    "philippines": "Manila",
    "malaysia": "Kuala Lumpur",
    "singapore": "Singapore",
    "south korea": "Seoul",
    "north korea": "Pyongyang",
    "australia": "Canberra",
    "new zealand": "Wellington",
    "saudi arabia": "Riyadh",
    "israel": "Jerusalem",
    "iran": "Tehran",
    "iraq": "Baghdad",
}

_CAPITAL_RE = re.compile(r"capital (?:city )?of (?:the )?([a-z .'-]+?)\s*$")


def _lookup_capital(text: str) -> Optional[str]:
    """Answer 'what is the capital of X' for a known country."""
    match = _CAPITAL_RE.search(text)
    if not match:
        return None

    country = match.group(1).strip().rstrip(".")
    capital = _CAPITALS.get(country)
    if capital is None:
        return None

    if country in {"uk", "usa", "us", "drc"}:
        display = f"the {country.upper()}"
    elif country in {"united kingdom", "united states", "netherlands", "philippines"}:
        display = f"the {country.title()}"
    else:
        display = country.title()

    return f"The capital of **{display}** is **{capital}**."


def _normalize(text: str, strip_name: bool = True) -> str:
    text = text.lower().strip()
    text = re.sub(r"[?!.,;:]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    # Strip polite scaffolding so "hey kudos, what is python?" still matches.
    text = re.sub(r"^(hey|hi|hello|ok|okay|so|um|please)\b[\s,]*", "", text).strip()
    text = re.sub(r"^(can you |could you |please )+", "", text).strip()
    if strip_name:
        # Drop a leading vocative "kudos," — but keep "kudos" when the user is
        # asking *about* KUDOS ("what is kudos").
        text = re.sub(r"^kudos\b[\s,]*", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def lookup(query: str) -> Optional[str]:
    """
    Return a curated answer for a common question, or None.

    Matching is deliberately strict: a trigger phrase must appear as a
    contiguous substring of the normalized query. That keeps unrelated
    questions from grabbing the wrong fact.
    """
    if not query:
        return None

    # Try both with and without the leading vocative so that "kudos, what is
    # python" and "what is kudos" both resolve correctly.
    candidates = {_normalize(query), _normalize(query, strip_name=False)}

    # Pattern-based facts first — they are more specific than substring matches.
    for text in candidates:
        capital = _lookup_capital(text)
        if capital:
            return capital

    best_answer = None
    best_len = 0

    for text in candidates:
        if not text:
            continue
        for triggers, answer in _INDEX:
            for trigger in triggers:
                if trigger in text and len(trigger) > best_len:
                    best_answer, best_len = answer, len(trigger)

    return best_answer


def topics() -> list[str]:
    """List the primary trigger phrase for every known topic."""
    return sorted(triggers[0] for triggers, _ in _INDEX)
