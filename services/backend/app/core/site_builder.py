"""KUDOS Site Builder — generate a website / CV / company profile with an LLM
and launch it live on the network in seconds.

A generated site is a SINGLE self-contained ``index.html`` (inline CSS/JS, no
external dependencies) so it renders instantly with no build step and no
long-lived process. Files live under the ``sites/`` storage prefix and are
served publicly through ``GET /api/v1/kudos/sites/<site_id>/...``.
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import UTC, datetime

from app.core import storage

SITES_PREFIX = "sites/"

# MIME map for static site assets (html must render, not download).
SITE_MIME = {
    "html": "text/html; charset=utf-8",
    "htm": "text/html; charset=utf-8",
    "css": "text/css; charset=utf-8",
    "js": "text/javascript; charset=utf-8",
    "mjs": "text/javascript; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "map": "application/json; charset=utf-8",
    "xml": "text/xml; charset=utf-8",
    "svg": "image/svg+xml",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "ico": "image/x-icon",
    "avif": "image/avif",
    "mp4": "video/mp4",
    "webm": "video/webm",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
    "woff": "font/woff",
    "woff2": "font/woff2",
    "ttf": "font/ttf",
    "pdf": "application/pdf",
}

_SAFE_PATH = re.compile(r"^[a-zA-Z0-9_./-]+$")
_SITE_ID_RE = re.compile(r"^[a-f0-9]{12}$")
_INDEX = f"{SITES_PREFIX}index.json"
_index_lock = threading.Lock()

_SITE_SYSTEM_PROMPT = (
    "You are KUDOS Site Builder. The user wants a website generated instantly.\n"
    "Produce EXACTLY ONE complete, self-contained HTML document with inline CSS and "
    "JavaScript (no external CDN links, no external images — use inline SVG or CSS where "
    "needed). Make it modern, polished, responsive, and fully usable.\n"
    "Output ONLY the raw HTML, optionally wrapped in a single ```html ... ``` fenced block. "
    "No prose before or after, no markdown outside the fence."
)

_KIND_INSTRUCTIONS = {
    "site": (
        "Build a polished, modern website for the user's request. Follow the request "
        "closely; include navigation, hero, content sections, and a footer. Write real, "
        "meaningful copy."
    ),
    "cv": (
        "Build a professional, single-page CV / resume. If profile_data is provided, use it "
        "for the person's name, title, contact, skills, experience, and education. Fill "
        "sections cleanly; keep it one page and print-friendly."
    ),
    "company_profile": (
        "Build a professional company profile page in seconds. If profile_data is provided, "
        "use the company name, tagline, industry, services and contact. Include a hero, "
        "About, Mission/Vision, Services/Products, a placeholder team section, and Contact."
    ),
}


class SiteBuildError(RuntimeError):
    """Raised when a site cannot be generated or stored."""


def _build_instruction(kind: str, prompt: str, profile_data: dict | None) -> str:
    kind = kind if kind in _KIND_INSTRUCTIONS else "site"
    lines = [_KIND_INSTRUCTIONS[kind]]
    if kind in ("cv", "company_profile") and profile_data:
        lines.append(f"profile_data (JSON): {json.dumps(profile_data, ensure_ascii=False)[:2000]}")
    if prompt and prompt.strip():
        lines.append(f"User request: {prompt.strip()[:2000]}")
    lines.append("Return only the HTML document.")
    return "\n\n".join(lines)


def _extract_html(raw: str) -> str:
    """Pull the HTML out of an LLM reply (fenced or bare)."""
    text = (raw or "").strip()
    fence = re.search(r"```(?:html)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    if re.search(r"<html[\s>]|<!doctype\s+html", text[:2000], re.IGNORECASE) or "<body" in text[:4000]:
        return text
    raise SiteBuildError("The model did not return a valid HTML document.")


async def generate_site(
    name: str,
    kind: str = "site",
    prompt: str = "",
    profile_data: dict | None = None,
) -> dict:
    """Ask KUDOS (best available LLM) for a site and launch it live.

    Returns site metadata with a public ``url``. Raises ``SiteBuildError`` if the
    model is unavailable or returns invalid HTML.
    """
    from app.core.llm_engine import query_best_llm

    user_prompt = _build_instruction(kind, prompt, profile_data)
    result = await query_best_llm(user_prompt, _SITE_SYSTEM_PROMPT)
    raw = result.get("response")
    if not raw:
        detail = result.get("message") or "No LLM provider is configured."
        raise SiteBuildError(f"KUDOS could not generate the site: {detail}")

    html = _extract_html(raw)
    if len(html) > 500_000:
        html = html[:500_000]

    site_id = uuid.uuid4().hex[:12]
    index_key = f"{SITES_PREFIX}{site_id}/index.html"
    storage.upload_bytes(index_key, html.encode("utf-8"), content_type=SITE_MIME["html"])

    title = _guess_title(name, prompt, html)
    created_at = datetime.now(UTC).isoformat()
    meta = {
        "site_id": site_id,
        "name": (name or title)[:120],
        "kind": kind if kind in _KIND_INSTRUCTIONS else "site",
        "title": title[:160],
        "created_at": created_at,
        "url": f"/api/v1/kudos/sites/{site_id}/",
    }
    _write_meta(meta)
    return meta


def _guess_title(name: str, prompt: str, html: str) -> str:
    if name and name.strip():
        return name.strip()
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()
    return (prompt or "").strip()[:80] or "KUDOS Site"


# ──────────────────────────────────────────────
# METADATA INDEX
# ──────────────────────────────────────────────


def _read_index() -> list[dict]:
    try:
        data = storage.download(_INDEX)
        items = json.loads(data.decode("utf-8"))
        return items if isinstance(items, list) else []
    except Exception:
        return []


def _write_index(items: list[dict]) -> None:
    storage.upload_bytes(_INDEX, json.dumps(items).encode("utf-8"), content_type=SITE_MIME["json"])


def _write_meta(meta: dict) -> None:
    with _index_lock:
        items = _read_index()
        items = [i for i in items if i.get("site_id") != meta["site_id"]]
        items.insert(0, meta)
        _write_index(items[:200])


def _remove_meta(site_id: str) -> bool:
    with _index_lock:
        items = _read_index()
        remaining = [i for i in items if i.get("site_id") != site_id]
        if len(remaining) == len(items):
            return False
        _write_index(remaining)
        return True


def list_sites() -> list[dict]:
    return _read_index()


def get_site(site_id: str) -> dict | None:
    for item in _read_index():
        if item.get("site_id") == site_id:
            return item
    return None


def valid_site_id(site_id: str) -> bool:
    return bool(site_id and _SITE_ID_RE.match(site_id))


def resolve_site_key(site_id: str, path: str = "") -> str:
    """Map a requested path to a storage key, refusing traversal."""
    if not valid_site_id(site_id):
        raise SiteBuildError("invalid site id")
    rel = (path or "").strip().lstrip("/")
    if rel and (not _SAFE_PATH.match(rel) or ".." in rel.split("/")):
        raise SiteBuildError("invalid path")
    return f"{SITES_PREFIX}{site_id}/{rel if rel else 'index.html'}"


def delete_site(site_id: str) -> bool:
    """Remove a site's files and metadata entry (best-effort)."""
    if not valid_site_id(site_id):
        return False
    storage.delete(f"{SITES_PREFIX}{site_id}/index.html")
    _remove_meta(site_id)
    return True
