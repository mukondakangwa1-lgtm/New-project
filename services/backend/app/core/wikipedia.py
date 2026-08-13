"""Shared Wikipedia API client configuration.

Wikimedia requires a descriptive User-Agent on every request (see
<https://phabricator.wikimedia.org/T400119>). Bare httpx clients are blocked
with HTTP 403, which silently stopped KUDOS from ever learning from
Wikipedia. All wikipedia.org/w/api.php callers should reuse these headers.
"""

WIKIPEDIA_HEADERS = {
    "User-Agent": "KUDOS-DigitalCampus/1.0 (educational assistant; admin@digitalcampus.local)",
    "Accept-Language": "en",
}