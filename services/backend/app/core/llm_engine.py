"""
KUDOS LLM Engine — Connect to external AI models (Google Gemini, OpenAI, etc.)
KUDOS queries multiple LLMs and picks the best response.
"""
import json
import os
from datetime import datetime, timezone
from typing import Optional

import httpx


# ──────────────────────────────────────────────
# LLM PROVIDER CONFIGS
# ──────────────────────────────────────────────

# These can be set via environment variables or the admin panel
LLM_CONFIGS = {
    "google_gemini": {
        "name": "Google Gemini",
        "icon": "✨",
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        "api_key_env": "GOOGLE_GEMINI_API_KEY",
        "enabled": False,
    },
    "openai": {
        "name": "OpenAI GPT",
        "icon": "🤖",
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "api_key_env": "OPENAI_API_KEY",
        "enabled": False,
    },
    "groq": {
        "name": "Groq (Fast)",
        "icon": "⚡",
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "api_key_env": "GROQ_API_KEY",
        "enabled": False,
    },
    "ollama": {
        "name": "Ollama (Local)",
        "icon": "🦙",
        "endpoint": "http://localhost:11434/api/generate",
        "api_key_env": "",
        "enabled": False,
    },
}

# In-memory API key storage (superadmin sets these)
_api_keys: dict[str, str] = {}


def set_api_key(provider: str, api_key: str):
    """Set API key for a provider (superadmin only)."""
    _api_keys[provider] = api_key
    if provider in LLM_CONFIGS:
        LLM_CONFIGS[provider]["enabled"] = True


def get_api_key(provider: str) -> Optional[str]:
    """Get API key for a provider."""
    # Check in-memory first
    if provider in _api_keys and _api_keys[provider]:
        return _api_keys[provider]
    # Check environment variable
    config = LLM_CONFIGS.get(provider, {})
    env_var = config.get("api_key_env", "")
    if env_var:
        return os.environ.get(env_var)
    return None


def get_llm_status() -> list[dict]:
    """Get status of all LLM providers."""
    status = []
    for key, config in LLM_CONFIGS.items():
        has_key = bool(get_api_key(key))
        status.append({
            "id": key,
            "name": config["name"],
            "icon": config["icon"],
            "enabled": has_key,
            "configured": has_key,
        })
    return status


# ──────────────────────────────────────────────
# LLM QUERY FUNCTIONS
# ──────────────────────────────────────────────

async def query_google_gemini(prompt: str, system_prompt: str = "") -> Optional[str]:
    """Query Google Gemini API."""
    api_key = get_api_key("google_gemini")
    if not api_key:
        return None

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                f"{LLM_CONFIGS['google_gemini']['endpoint']}?key={api_key}",
                json={
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "systemInstruction": {
                        "parts": [{"text": system_prompt}] if system_prompt else [{"text": "You are KUDOS, a helpful AI assistant for a university Digital Campus. Be friendly, concise, and helpful. Respond like a knowledgeable friend."}]
                    },
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 1024,
                    }
                },
                headers={"Content-Type": "application/json"},
            )
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
    except Exception as e:
        print(f"Gemini error: {e}")
    return None


async def query_openai(prompt: str, system_prompt: str = "") -> Optional[str]:
    """Query OpenAI API."""
    api_key = get_api_key("openai")
    if not api_key:
        return None

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                LLM_CONFIGS["openai"]["endpoint"],
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": system_prompt or "You are KUDOS, a helpful AI assistant for a university Digital Campus. Be friendly, concise, and helpful."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1024,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            if res.status_code == 200:
                data = res.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
    except Exception:
        pass
    return None


async def query_groq(prompt: str, system_prompt: str = "") -> Optional[str]:
    """Query Groq API (fast inference)."""
    api_key = get_api_key("groq")
    if not api_key:
        return None

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(
                LLM_CONFIGS["groq"]["endpoint"],
                json={
                    "model": "llama3-8b-8192",
                    "messages": [
                        {"role": "system", "content": system_prompt or "You are KUDOS, a helpful AI assistant for a university Digital Campus. Be friendly, concise, and helpful. Respond like a knowledgeable friend."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1024,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            if res.status_code == 200:
                data = res.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
    except Exception:
        pass
    return None


async def query_ollama(prompt: str, system_prompt: str = "") -> Optional[str]:
    """Query local Ollama instance."""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.post(
                LLM_CONFIGS["ollama"]["endpoint"],
                json={
                    "model": "llama3",
                    "prompt": prompt,
                    "system": system_prompt or "You are KUDOS, a helpful AI assistant. Be friendly and concise.",
                    "stream": False,
                },
            )
            if res.status_code == 200:
                data = res.json()
                return data.get("response", "")
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────
# MULTI-LLM QUERY — BEST RESPONSE SELECTOR
# ──────────────────────────────────────────────

async def query_best_llm(prompt: str, system_prompt: str = "") -> dict:
    """
    Query all available LLMs in parallel and return the best response.
    Falls back to internal knowledge if no LLM is configured.
    """
    import asyncio

    providers = []

    # Build list of available providers
    if get_api_key("google_gemini"):
        providers.append(("google_gemini", query_google_gemini))
    if get_api_key("groq"):
        providers.append(("groq", query_groq))
    if get_api_key("openai"):
        providers.append(("openai", query_openai))
    if get_api_key("ollama"):
        providers.append(("ollama", query_ollama))

    if not providers:
        return {"response": None, "provider": "none", "message": "No LLM configured. Set an API key in the admin panel."}

    # Query all available LLMs in parallel
    async def _query(name, func):
        try:
            result = await asyncio.wait_for(func(prompt, system_prompt), timeout=30)
            return {"provider": name, "response": result} if result else None
        except (asyncio.TimeoutError, Exception):
            return None

    tasks = [_query(name, func) for name, func in providers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Get first successful response
    for r in results:
        if isinstance(r, dict) and r.get("response"):
            return r

    return {"response": None, "provider": "none", "message": "All LLMs failed to respond."}


# ──────────────────────────────────────────────
# HUMAN-LIKE PROMPT BUILDER
# ──────────────────────────────────────────────

def build_human_prompt(
    question: str,
    knowledge_context: str = "",
    conversation_history: list = [],
    user_name: str = "",
) -> tuple[str, str]:
    """
    Build a prompt that makes the LLM respond like a human.
    Returns (user_prompt, system_prompt).
    """
    system_prompt = f"""You are KUDOS, an AI assistant for Digital Campus university platform.

PERSONALITY:
- You are friendly, warm, and approachable — like a knowledgeable friend
- You use natural language, contractions (I'm, you're, don't), and casual tone
- You show empathy and understanding
- You ask follow-up questions to keep the conversation going
- You admit when you don't know something
- You use light humor when appropriate
- You remember context from the conversation

RULES:
- Keep responses concise but helpful (2-4 paragraphs max)
- Use bullet points for lists
- If the user seems confused, break things down simply
- If the user shares good news, congratulate them
- If the user seems stressed, be supportive
- Always end with a helpful follow-up question or suggestion

{f"The user's name is {user_name}. Use it occasionally." if user_name else ""}
"""

    user_prompt = ""

    # Add knowledge context
    if knowledge_context:
        user_prompt += f"RELEVANT KNOWLEDGE:\n{knowledge_context}\n\n"

    # Add conversation history
    if conversation_history:
        user_prompt += "CONVERSATION HISTORY:\n"
        for msg in conversation_history[-5:]:  # Last 5 messages
            role = "User" if msg.get("role") == "user" else "KUDOS"
            user_prompt += f"{role}: {msg.get('content', '')[:200]}\n"
        user_prompt += "\n"

    # Add current question
    user_prompt += f"USER'S QUESTION: {question}\n\nRespond naturally and helpfully:"

    return user_prompt, system_prompt


async def get_llm_response(
    question: str,
    knowledge_context: str = "",
    conversation_history: list = [],
    user_name: str = "",
) -> Optional[str]:
    """
    Get a human-like response from the best available LLM.
    """
    user_prompt, system_prompt = build_human_prompt(
        question=question,
        knowledge_context=knowledge_context,
        conversation_history=conversation_history,
        user_name=user_name,
    )

    result = await query_best_llm(user_prompt, system_prompt)
    return result.get("response")
