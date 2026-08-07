"""Small KUDOS client for calling internal MCP tools."""

from __future__ import annotations

import json
from typing import Any

from app.core.config import settings


async def call_mcp_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
    """Call one MCP tool and normalize its structured/text result.

    MCP is optional. If it is disabled, unavailable, or returns an error, this
    helper returns ``None`` so the existing KUDOS fallbacks continue working.
    """
    if not settings.MCP_ENABLED:
        return None

    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        headers = {}
        if settings.MCP_AUTH_TOKEN:
            headers["x-mcp-token"] = settings.MCP_AUTH_TOKEN

        async with streamablehttp_client(
            settings.MCP_URL,
            headers=headers,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        ) as (read_stream, write_stream, _get_session_id):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments or {})

        if result.isError:
            return None
        if result.structuredContent is not None:
            structured = result.structuredContent
            # The Python SDK wraps structured tool return values under
            # ``result`` for some schema shapes.
            if (
                isinstance(structured, dict)
                and set(structured) == {"result"}
            ):
                return structured["result"]
            return structured

        text_parts = [
            item.text
            for item in result.content
            if getattr(item, "type", None) == "text"
            and getattr(item, "text", None)
        ]
        text = "\n".join(text_parts).strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    except Exception:
        return None


async def search_mcp_sources(query: str, limit: int = 5) -> list[dict]:
    """Return normalized source records from the KUDOS MCP gateway."""
    result = await call_mcp_tool(
        "kudos_search_sources", {"query": query, "limit": limit}
    )
    if not isinstance(result, list):
        return []

    normalized = []
    for item in result:
        if not isinstance(item, dict) or not item.get("content"):
            continue
        normalized.append(
            {
                "source": item.get("source", "mcp"),
                "document_id": item.get("document_id"),
                "web_id": item.get("web_id"),
                "title": item.get("title", item.get("source", "MCP tool")),
                "content": str(item["content"])[:2000],
                "score": item.get("score", 0.5),
                "retrieval": "mcp",
            }
        )
    return normalized[:limit]
