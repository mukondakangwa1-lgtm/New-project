"""
LLM adapter — thin wrapper around existing llm_engine to provide a smaller interface
for endpoints and services. Keeps code decoupled in case of future LLM provider changes.
"""
from __future__ import annotations

from typing import Optional, List

from app.core import llm_engine


async def get_response(question: str, knowledge_context: str = "", conversation_history: List[dict] | None = None, user_name: str = "") -> Optional[str]:
    return await llm_engine.get_llm_response(
        question=question,
        knowledge_context=knowledge_context,
        conversation_history=conversation_history or [],
        user_name=user_name,
    )


def get_providers_status():
    return llm_engine.get_llm_status()
