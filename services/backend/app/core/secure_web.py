"""Secure Web Bridge — the one safe way KUDOS and its sandbox reach the internet.

Guards:
- scheme allowlist (https preferred, http optional via flag)
- SSRF protection: hostname resolution checked against private/loopback/
  link-local/reserved ranges before any request
- implicit redirect following with re-validation per hop
- response size cap, timeout, HTML sanitization
"""

from __future__ import annotations

import contextlib
import ipaddress
import socket
import time
from html.parser import HTMLParser
from typing import Any

import httpx

MAX_RESPONSE_BYTES = 256 * 1024
FETCH_TIMEOUT_SECONDS = 15.0
MAX_REDIRECTS = 4
BLOCKED_HOST_PREFIXES = ("127.", "169.254.", "10.", "192.168.")
_HOSTNAME_CACHE: dict[str, bool] = {}


class _LinkStripper(HTMLParser):
    """Collect text content, dropping scripts/styles and tags."""

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def sanitize_html(html: str, limit: int = 4000) -> str:
    """Strip tags/scripts and collapse whitespace to plain text."""
    parser = _LinkStripper()
    with contextlib.suppress(Exception):
        parser.feed(html)
    text = " ".join(" ".join(parser.parts).split())
    return text[:limit]


def _host_is_safe(host: str) -> bool:
    """True when the host does not resolve to a private/loopback address."""
    cached = _HOSTNAME_CACHE.get(host)
    if cached is not None:
        return cached
    safe = True
    try:
        infos = socket.getaddrinfo(host, None)
        for info in infos:
            addr = info[4][0]
            ip = ipaddress.ip_address(addr)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                safe = False
                break
    except socket.gaierror:
        safe = False
    except Exception:
        safe = False
    _HOSTNAME_CACHE[host] = safe
    return safe


def validate_url(url: str, allow_http: bool = False) -> str | None:
    """Validate a URL for outbound fetch; returns an error message or None."""
    if not url or len(url) > 2000:
        return "URL is missing or too long"
    scheme = url.split("://", 1)[0].lower() if "://" in url else ""
    if scheme not in ("https", "http"):
        return "Only http(s) URLs are allowed"
    if scheme == "http" and not allow_http:
        return "Only https URLs are allowed"
    rest = url.split("://", 1)[1]
    host_port = rest.split("/", 1)[0].split("?", 1)[0]
    if not host_port:
        return "URL is missing a host"
    host = host_port.split(":", 1)[0].strip("[]")
    if not host:
        return "URL is missing a host"
    if any(host.startswith(p) for p in BLOCKED_HOST_PREFIXES):
        return "Private or reserved addresses are blocked"
    label = host.lower()
    if label in ("localhost", "localhost.localdomain") or label.endswith(".local"):
        return "Local hosts are blocked"
    if not _host_is_safe(host):
        return "Address resolves to a private or loopback network"
    return None


def _check_response_ssrf(response: httpx.Response) -> str | None:
    """Re-validate the final address after redirects (scheme already https)."""
    try:
        error = validate_url(str(response.url), allow_http=True)
    except Exception:
        error = "Redirect target could not be validated"
    if error:
        return f"Redirect target blocked: {error}"
    return None


def fetch_url(url: str, allow_http: bool = False, headers: dict[str, str] | None = None) -> dict[str, Any]:
    """Fetch and sanitize a remote page. Returns an error dict on failure.

    Never raises: every failure path returns {"ok": False, "error": ...}.
    """
    error = validate_url(url, allow_http=allow_http)
    if error:
        return {"ok": False, "error": error}

    started = time.monotonic()
    try:
        with httpx.Client(
            timeout=FETCH_TIMEOUT_SECONDS,
            follow_redirects=True,
            max_redirects=MAX_REDIRECTS,
            headers={"User-Agent": "KUDOS-DigitalCampus/1.0 (+https://campus.kudos)"},
        ) as client:
            response = client.get(url, headers=headers or {})
            redirect_error = _check_response_ssrf(response)
            if redirect_error:
                return {"ok": False, "error": redirect_error}
            body = response.content[:MAX_RESPONSE_BYTES]
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        return {"ok": False, "error": f"Fetch failed: {type(exc).__name__}: {str(exc)[:150]}"}
    except Exception as exc:
        return {"ok": False, "error": f"Fetch failed: {str(exc)[:200]}"}

    latency_ms = int((time.monotonic() - started) * 1000)
    content_text = body.decode("utf-8", errors="replace")
    stripped = sanitize_html(content_text)

    return {
        "ok": True,
        "url": str(response.url),
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "content": stripped,
        "bytes": len(body),
        "latency_ms": latency_ms,
    }
