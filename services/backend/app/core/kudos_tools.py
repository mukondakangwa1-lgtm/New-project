"""
Digital Campus - KUDOS Tools (auto-collected APIs)

KUDOS can register new tools/APIs at runtime (REGISTER_TOOL marker) and call
them to execute commands (TOOL_CALL marker). Safety rules:

- Only http(s) schemes; internal compose service names allowed.
- SSRF guard: public tool calls refuse private/loopback/link-local targets.
- Auth values are stored but never returned to clients or put in LLM context.
- Responses are truncated and secret-shaped values are scrubbed.
"""
import ipaddress
import json
import socket
import urllib.parse
from typing import Optional

import httpx

from app.core.config import settings

_ALLOWED_INTERNAL_HOSTS = {"localhost", "backend", "frontend", "mcp", "networkops", "redis", "minio", "db", "worker"}


def _ssrf_ok(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname or ""
    if host in _ALLOWED_INTERNAL_HOSTS:
        return True
    try:
        info = socket.getaddrinfo(host, None)
    except Exception:
        return False
    for family, _, _, _, sockaddr in info[:4]:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return False
    return True


def register_tool(db, name: str, method: str, url: str, headers: str = "{}",
                  body_schema: str = "{}", auth_type: str = "none", auth_value: str = "",
                  auth_header_name: str = "Authorization", description: str = "") -> dict:
    """Create or update a registered tool. Returns a public-safe description."""
    from app.models import KudosTool

    if not _ssrf_ok(url):
        return {"error": "Tool URL refused by SSRF guard (must be public https or internal service)"}
    method = (method or "GET").upper()
    if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        return {"error": f"Unsupported method {method}"}

    tool = db.query(KudosTool).filter(KudosTool.name == name).first()
    if not tool:
        tool = KudosTool(name=name)
        db.add(tool)
    tool.method = method
    tool.url = url
    tool.headers = json.dumps(_safe_json(headers))
    tool.body_schema = json.dumps(_safe_json(body_schema))
    tool.auth_type = auth_type
    tool.auth_value = auth_value  # stored, never serialized to clients
    tool.auth_header_name = auth_header_name or "Authorization"
    tool.description = (description or "")[:2000]
    tool.enabled = True
    db.commit()
    db.refresh(tool)
    return {"ok": True, "id": tool.id, "name": tool.name, "method": tool.method, "url": tool.url}


def _safe_json(value) -> dict:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def list_tools_public(db) -> list[dict]:
    """Tools without any secret material (auth values never exposed)."""
    from app.models import KudosTool

    tools = db.query(KudosTool).filter(KudosTool.enabled == True).order_by(KudosTool.name).all()  # noqa: E712
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "method": t.method,
            "url": t.url,
            "headers": _safe_json(t.headers),
            "body_schema": _safe_json(t.body_schema),
            "response_kind": t.response_kind,
            "auth_type": t.auth_type,
            "timeout": t.timeout,
        }
        for t in tools
    ]


async def call_tool(db, tool_id: int, args: Optional[dict] = None) -> dict:
    """Execute a registered tool with the given args. Never returns secrets."""
    from app.models import KudosTool
    from datetime import datetime, timezone

    tool = db.query(KudosTool).filter(KudosTool.id == tool_id, KudosTool.enabled == True).first()  # noqa: E712
    if not tool:
        return {"error": "Tool not found or disabled"}

    url = tool.url
    headers = _safe_json(tool.headers)
    body_schema = _safe_json(tool.body_schema)
    args = args or {}

    # Substitute {param} placeholders in URL and body.
    try:
        url = url.format(**args)
    except Exception:
        return {"error": "Missing arguments for URL placeholders"}

    if not _ssrf_ok(url):
        return {"error": "SSRF guard refused tool URL"}

    if tool.auth_type == "bearer":
        headers["Authorization"] = f"Bearer {tool.auth_value}"
    elif tool.auth_type == "header":
        headers[tool.auth_header_name or "Authorization"] = tool.auth_value
    elif tool.auth_type == "query":
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{urllib.parse.quote(tool.auth_header_name)}={urllib.parse.quote(tool.auth_value)}"

    body = None
    if tool.method in ("POST", "PUT", "PATCH"):
        payload = dict(body_schema)
        for k, v in args.items():
            if k in body_schema or k not in payload:
                payload[k] = v
        body = json.dumps(payload)
        headers.setdefault("Content-Type", "application/json")

    try:
        timeout = max(5, min(tool.timeout or 30, int(settings.TOOL_CALL_TIMEOUT_SECONDS * 2)))
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.request(tool.method, url, headers=headers, content=body)
    except Exception as e:
        return {"error": f"Tool call failed: {e}"}

    text = res.text or ""
    text = text[: settings.TOOL_CALL_MAX_RESPONSE_CHARS]
    from app.core.privacy_guard import scrub_response
    text = scrub_response(text, allow_emails=True)

    tool.last_used_at = datetime.now(timezone.utc)
    db.commit()

    parsed = None
    if tool.response_kind == "json" or (not tool.response_kind and text.strip().startswith("{")):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                # Never leak auth material stored on the tool row.
                parsed.pop("auth_value", None)
                parsed.pop("auth_header_name", None)
        except Exception:
            parsed = None

    return {"ok": res.status_code < 400, "status_code": res.status_code, "response": parsed if parsed is not None else text}


async def handle_tool_marker(db, line: str, current_user) -> dict:
    """Execute a TOOL_CALL:<name>|<json args> marker line. Returns a reply text."""
    _, _, rest = line.partition(":")
    name, _, args_str = rest.partition("|")
    name = name.strip()
    try:
        args = json.loads(args_str.strip()) if args_str.strip() else {}
    except Exception:
        args = {}
    from app.models import KudosTool

    tool = db.query(KudosTool).filter(KudosTool.name == name).first()
    if not tool:
        return {"reply": f"I wanted to use the tool '{name}' but it isn't registered yet. Please register it."}
    result = await call_tool(db, tool.id, args)
    if result.get("error"):
        return {"reply": f"Tool '{name}' failed: {result['error']}"}
    resp = result.get("response")
    if isinstance(resp, dict):
        summary = json.dumps(resp, ensure_ascii=False)[:1500]
    else:
        summary = str(resp)[:1500]
    return {"reply": f"I called **{name}** ({result.get('status_code')}): {summary}"}
