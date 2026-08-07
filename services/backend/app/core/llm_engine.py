"""
KUDOS LLM Engine — Connect to external AI models (Google Gemini, OpenAI, etc.)
KUDOS queries multiple LLMs and picks the best response.
"""
import os
from typing import Optional

import httpx

from app.core.config import settings


# ──────────────────────────────────────────────
# LLM PROVIDER CONFIGS
# ──────────────────────────────────────────────

# These can be set via environment variables or the admin panel
LLM_CONFIGS = {
    "google_gemini": {
        "name": "Google Gemini",
        "icon": "✨",
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models",
        "api_key_env": "GOOGLE_GEMINI_API_KEY",
        "model_env": "GEMINI_MODEL",
        "enabled": False,
    },
    "openai": {
        "name": "OpenAI GPT",
        "icon": "🤖",
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "api_key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_MODEL",
        "enabled": False,
    },
    "groq": {
        "name": "Groq (Fast)",
        "icon": "⚡",
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "api_key_env": "GROQ_API_KEY",
        "model_env": "GROQ_MODEL",
        "enabled": False,
    },
    "ollama": {
        "name": "Ollama (Local)",
        "icon": "🦙",
        "endpoint": "http://localhost:11434/api/generate",
        "api_key_env": "OLLAMA_API_KEY",
        "model_env": "OLLAMA_MODEL",
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
    """Get a provider key from process memory or the environment."""
    if provider in _api_keys and _api_keys[provider]:
        return _api_keys[provider]

    config = LLM_CONFIGS.get(provider, {})
    env_var = config.get("api_key_env", "")
    if not env_var:
        return None
    return os.getenv(env_var) or getattr(settings, env_var, None)


def get_model(provider: str) -> str:
    """Return the configured model for a provider."""
    defaults = {
        "google_gemini": settings.GEMINI_MODEL,
        "openai": settings.OPENAI_MODEL,
        "groq": settings.GROQ_MODEL,
        "ollama": settings.OLLAMA_MODEL,
    }
    config = LLM_CONFIGS.get(provider, {})
    env_name = config.get("model_env", "")
    return os.getenv(env_name) or defaults.get(provider, "")


def provider_is_configured(provider: str) -> bool:
    """Return whether a provider can be queried right now."""
    # Ollama is local and does not require an API key.
    if provider == "ollama":
        base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        requires_key = base_url.startswith("https://ollama.com")
        return bool(
            settings.OLLAMA_ENABLED
            and base_url
            and get_model(provider)
            and (not requires_key or get_api_key(provider))
        )
    return bool(get_api_key(provider))


def get_llm_status() -> list[dict]:
    """Get status of all LLM providers."""
    status = []
    for key, config in LLM_CONFIGS.items():
        configured = provider_is_configured(key)
        status.append({
            "id": key,
            "name": config["name"],
            "icon": config["icon"],
            "model": get_model(key),
            "enabled": configured,
            "configured": configured,
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
        endpoint = f"{LLM_CONFIGS['google_gemini']['endpoint']}/{get_model('google_gemini')}:generateContent"
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            res = await client.post(
                f"{endpoint}?key={api_key}",
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
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            res = await client.post(
                LLM_CONFIGS["openai"]["endpoint"],
                json={
                    "model": get_model("openai"),
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
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            res = await client.post(
                LLM_CONFIGS["groq"]["endpoint"],
                json={
                    "model": get_model("groq"),
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
        base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        if base_url.endswith("/api"):
            base_url = base_url[:-4]
        endpoint = f"{base_url}/api/generate"
        headers = {}
        api_key = get_api_key("ollama")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        async with httpx.AsyncClient(timeout=max(settings.LLM_TIMEOUT_SECONDS, 60)) as client:
            res = await client.post(
                endpoint,
                headers=headers,
                json={
                    "model": get_model("ollama"),
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

async def query_best_llm(
    prompt: str,
    system_prompt: str = "",
    provider: str | None = None,
) -> dict:
    """
    Query all available LLMs in parallel and return the best response.
    Falls back to internal knowledge if no LLM is configured.
    """
    import asyncio

    providers = []
    provider_functions = {
        "google_gemini": query_google_gemini,
        "groq": query_groq,
        "openai": query_openai,
        "ollama": query_ollama,
    }

    preferred = (provider or os.getenv("LLM_PROVIDER") or settings.LLM_PROVIDER).strip().lower()
    if preferred != "auto":
        if preferred not in provider_functions:
            return {
                "response": None,
                "provider": "none",
                "message": f"Unknown LLM_PROVIDER '{preferred}'. Use auto, google_gemini, openai, groq, or ollama.",
            }
        provider_order = [preferred]
    else:
        # Keep a deterministic order so deployments can predict which model
        # receives traffic when more than one secret is configured.
        provider_order = ["google_gemini", "openai", "groq", "ollama"]

    for provider in provider_order:
        if provider_is_configured(provider):
            providers.append((provider, provider_functions[provider]))

    if not providers:
        return {"response": None, "provider": "none", "message": "No LLM configured. Set an API key in the admin panel."}

    # Query all available LLMs in parallel
    async def _query(name, func):
        try:
            result = await asyncio.wait_for(
                func(prompt, system_prompt),
                timeout=max(settings.LLM_TIMEOUT_SECONDS, 1),
            )
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
