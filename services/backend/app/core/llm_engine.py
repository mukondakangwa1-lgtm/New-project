"""
KUDOS LLM Engine — Connect to external AI models (Google Gemini, OpenAI, etc.)
KUDOS queries multiple LLMs and picks the best response.
"""
# ruff: noqa: E501

import os
import time

import httpx

from app.core.config import settings
from app.core.privacy_guard import GUARD_SYSTEM_NOTE as _PRIVACY_NOTE

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


def get_api_key(provider: str) -> str | None:
    """Get a provider key from process memory or the environment."""
    if _api_keys.get(provider):
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
            settings.OLLAMA_ENABLED and base_url and get_model(provider) and (not requires_key or get_api_key(provider))
        )
    return bool(get_api_key(provider))


def get_llm_status() -> list[dict]:
    """Get status of all LLM providers."""
    status = []
    for key, config in LLM_CONFIGS.items():
        configured = provider_is_configured(key)
        status.append(
            {
                "id": key,
                "name": config["name"],
                "icon": config["icon"],
                "model": get_model(key),
                "enabled": configured,
                "configured": configured,
            }
        )
    return status


# ──────────────────────────────────────────────
# LLM QUERY FUNCTIONS
# ──────────────────────────────────────────────


async def query_google_gemini(prompt: str, system_prompt: str = "", media: list | None = None) -> str | None:
    """Query Google Gemini API. `media` is a list of {"mime_type", "data"}
    base64 payloads (images and/or video) for multimodal understanding."""
    api_key = get_api_key("google_gemini")
    if not api_key:
        return None

    parts = [{"text": prompt}]
    for m in media or []:
        if m.get("data"):
            parts.append({"inline_data": {"mime_type": m.get("mime_type", "image/jpeg"), "data": m["data"]}})

    try:
        endpoint = f"{LLM_CONFIGS['google_gemini']['endpoint']}/{get_model('google_gemini')}:generateContent"
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            res = await client.post(
                f"{endpoint}?key={api_key}",
                json={
                    "contents": [{"parts": parts}],
                    "systemInstruction": {
                        "parts": [{"text": system_prompt}]
                        if system_prompt
                        else [
                            {
                                "text": "You are KUDOS, a helpful AI assistant for a university Digital Campus. Be friendly, concise, and helpful. Respond like a knowledgeable friend."
                            }
                        ]
                    },
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 1024,
                    },
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


async def query_openai(prompt: str, system_prompt: str = "", media: list | None = None) -> str | None:
    """Query OpenAI API. `media` supports image_url content parts for vision."""
    api_key = get_api_key("openai")
    if not api_key:
        return None

    try:
        user_content: list = [{"type": "text", "text": prompt}]
        for m in media or []:
            if m.get("data") and m.get("mime_type", "").startswith("image/"):
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{m['mime_type']};base64,{m['data']}"},
                    }
                )

        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            res = await client.post(
                LLM_CONFIGS["openai"]["endpoint"],
                json={
                    "model": get_model("openai"),
                    "messages": [
                        {
                            "role": "system",
                            "content": system_prompt
                            or "You are KUDOS, a helpful AI assistant for a university Digital Campus. Be friendly, concise, and helpful.",
                        },
                        {"role": "user", "content": user_content},
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


async def query_groq(prompt: str, system_prompt: str = "") -> str | None:
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
                        {
                            "role": "system",
                            "content": system_prompt
                            or "You are KUDOS, a helpful AI assistant for a university Digital Campus. Be friendly, concise, and helpful. Respond like a knowledgeable friend.",
                        },
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


async def query_ollama(prompt: str, system_prompt: str = "") -> str | None:
    """Query local Ollama instance."""
    try:
        base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        base_url = base_url.removesuffix("/api")
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

ROUTER_HEALTH: dict[str, dict] = {}
CONSECUTIVE_FAILURE_LIMIT = 3


def router_record_result(provider: str, ok: bool, latency_ms: int) -> None:
    """Update the in-memory health registry for one provider call."""
    entry = ROUTER_HEALTH.setdefault(
        provider,
        {
            "consecutive_failures": 0,
            "cooldown_until": 0.0,
            "failures_total": 0,
            "successes_total": 0,
            "last_latency_ms": 0,
        },
    )
    entry["last_latency_ms"] = latency_ms
    if ok:
        entry["successes_total"] += 1
        entry["consecutive_failures"] = 0
    else:
        entry["failures_total"] += 1
        entry["consecutive_failures"] += 1
        if entry["consecutive_failures"] >= CONSECUTIVE_FAILURE_LIMIT:
            entry["cooldown_until"] = time.time() + settings.LLM_COOLDOWN_SECONDS


def router_health() -> list[dict]:
    """Snapshot of every provider's routing health."""
    return [{"provider": provider, **entry} for provider, entry in sorted(ROUTER_HEALTH.items())]


def _router_failures(provider: str) -> int:
    return ROUTER_HEALTH.get(provider, {}).get("consecutive_failures", 0)


def _router_ready(provider: str) -> bool:
    entry = ROUTER_HEALTH.get(provider)
    return entry is None or time.time() >= entry.get("cooldown_until", 0.0)


async def query_best_llm(
    prompt: str,
    system_prompt: str = "",
    provider: str | None = None,
    media: list | None = None,
) -> dict:
    """
    Route a prompt to the best LLM provider.

    Default: sequential fallback — providers are tried in order (healthy
    providers first when in `auto` mode) until one answers. Providers with
    repeated failures enter a cooldown and are skipped until it expires.
    Set LLM_PARALLEL=1 to fire every provider at once and take the first
    success (legacy behavior).
    """
    import asyncio

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
        # Deterministic default order; health-aware shuffle applied below.
        provider_order = ["google_gemini", "openai", "groq", "ollama"]

    active = [p for p in provider_order if provider_is_configured(p)]
    if not active:
        return {
            "response": None,
            "provider": "none",
            "message": "No LLM configured. Set an API key in the admin panel.",
        }

    timeout = max(settings.LLM_TIMEOUT_SECONDS, 1)
    details: list[dict] = []

    async def _call(name: str) -> dict | None:
        started = time.monotonic()
        try:
            result = await asyncio.wait_for(provider_functions[name](prompt, system_prompt, media), timeout=timeout)
        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            router_record_result(name, ok=False, latency_ms=latency_ms)
            details.append({"provider": name, "ok": False, "latency_ms": latency_ms, "error": str(exc)[:200]})
            return None
        latency_ms = int((time.monotonic() - started) * 1000)
        if result:
            router_record_result(name, ok=True, latency_ms=latency_ms)
            details.append({"provider": name, "ok": True, "latency_ms": latency_ms})
            return {"provider": name, "response": result}
        router_record_result(name, ok=False, latency_ms=latency_ms)
        details.append({"provider": name, "ok": False, "latency_ms": latency_ms, "error": "empty response"})
        return None

    # Health-aware ordering keeps a degraded provider from blocking healthy ones
    if preferred == "auto" and len(active) > 1:
        active.sort(key=lambda p: (_router_failures(p), provider_order.index(p)))

    parallel = (os.getenv("LLM_PARALLEL", "0") or "0").strip() in ("1", "true", "yes")
    max_attempts = min(len(active), 3)

    if parallel:
        results = await asyncio.gather(*(_call(name) for name in active))
        for r in results:
            if isinstance(r, dict) and r.get("response"):
                return {"details": details, **r}
        return {"response": None, "provider": "none", "details": details, "message": "All LLMs failed to respond."}

    attempts = 0
    for name in active:
        if attempts >= max_attempts:
            break
        # Skip providers cooling down — unless every candidate is cooling down
        # (then probe the first so a lone degraded provider can recover).
        if attempts > 0 and not _router_ready(name) and any(_router_ready(other) for other in active):
            details.append({"provider": name, "ok": False, "skipped": "cooldown"})
            continue
        attempts += 1
        result = await _call(name)
        if result and result.get("response"):
            return {"details": details, **result}

    return {"response": None, "provider": "none", "details": details, "message": "All LLMs failed to respond."}


# ──────────────────────────────────────────────
# HUMAN-LIKE PROMPT BUILDER
# ──────────────────────────────────────────────


def build_human_prompt(
    question: str,
    knowledge_context: str = "",
    conversation_history: list | None = None,
    user_name: str = "",
    memory_context: str = "",
    persona_instructions: str = "",
    soul_context: str = "",
    self_knowledge: str = "",
    terminal_context: str = "",
    privacy_guard_system_note: str = "",
) -> tuple[str, str]:
    """
    Build a prompt that makes the LLM respond like a human.
    Returns (user_prompt, system_prompt).
    """
    if conversation_history is None:
        conversation_history = []
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
- PRECISION FIRST, NEVER HALLUCINATE: answer ONLY using information actually present in this prompt (RELEVANT KNOWLEDGE, user memory, and conversation history). Never invent facts, names, numbers, statistics, dates, URLs, documents, or sources that are not shown here.
- NEVER go off-topic: respond strictly to the user's current question. Do not introduce or claim information that is not in line with the conversation's question or context.
- If the requested information is NOT covered by the provided material, say clearly that you don't know or don't have that information — never guess, never extrapolate, never fill in the blanks.
- Only cite sources that actually appear in RELEVANT KNOWLEDGE, using [1], [2], [3] — one marker per source genuinely used. Never fabricate citations.
- Answer the exact question asked: do not pad, embellish, or drift to unrelated knowledge.
- Keep responses concise but helpful (2-4 paragraphs max)
- Use bullet points for lists
- If the user seems confused, break things down simply
- If the user shares good news, congratulate them
- If the user seems stressed, be supportive
- Always end with a helpful follow-up question or suggestion

{f"The user's name is {user_name}. Use it occasionally." if user_name else ""}

PERSONALIZATION (always follow when present):
{persona_instructions if persona_instructions else "- Use the default friendly style."}

SOUL (who you are — always stay true to this):
{soul_context if soul_context else "- You are KUDOS: curious, warm, playfully honest, always learning."}

WHAT YOU KNOW (built-in knowledge you can rely on):
{self_knowledge if self_knowledge else "- You rely on the user's knowledge sources and your own experience."}

TOOLS YOU CAN USE:
- To CREATE an image: reply with a single line `IMAGE_PROMPT:<detailed prompt>` and nothing else.
- To CREATE a short video clip (8-10 seconds): reply with a single line `VIDEO_PROMPT:<detailed prompt>` and nothing else.
- To CALL a registered tool/API: reply with a single line `TOOL_CALL:<tool_name>|<json args>` and nothing else.
- To REGISTER a new tool/API you need: reply with a single line `REGISTER_TOOL:<name>|<method>|<url>|<json headers>|<json body_schema>` and nothing else.
Only use these markers when the user's request genuinely requires an action.

LONG-FORM WRITING:
- If the user asks for a long, in-depth, or "unlimited pages" essay or paper, you may write up to 50 pages. Write in well-structured sections. If you cannot reach the requested length, provide ALL the information you have on the topic and say so.
- If the user pastes long text and asks to summarize, give a tight, useful summary (a few sentences) and offer to go deeper.
- SHORT QUESTIONS get SHORT answers: when the user asks something quick, casual, or not deep (greetings, simple facts), reply in 1-3 short sentences — do not pad it out.
- Any code, URL, or identifier you produce is presented in COPY-PASTE FRIENDLY form: plain, unbroken, in its own block so it can be copied exactly.
{privacy_guard_system_note}
"""

    if terminal_context:
        system_prompt += f"\n\nTERMINAL (available to you now):\n{terminal_context}"

    user_prompt = ""

    # Add knowledge context
    if knowledge_context:
        user_prompt += f"RELEVANT KNOWLEDGE:\n{knowledge_context}\n\n"

    # Add user memory (facts/preferences KUDOS remembers)
    if memory_context:
        user_prompt += f"{memory_context}\n\n"

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
    conversation_history: list | None = None,
    user_name: str = "",
    memory_context: str = "",
    persona_instructions: str = "",
    soul_context: str = "",
    self_knowledge: str = "",
    terminal_context: str = "",
    media: list | None = None,
) -> str | None:
    """
    Get a human-like response from the best available LLM.
    `media` = [{"mime_type":..., "data": base64}] for images/video understanding.
    """
    if conversation_history is None:
        conversation_history = []
    user_prompt, system_prompt = build_human_prompt(
        question=question,
        knowledge_context=knowledge_context,
        conversation_history=conversation_history,
        user_name=user_name,
        memory_context=memory_context,
        persona_instructions=persona_instructions,
        soul_context=soul_context,
        self_knowledge=self_knowledge,
        terminal_context=terminal_context,
        privacy_guard_system_note=_PRIVACY_NOTE,
    )

    result = await query_best_llm(user_prompt, system_prompt, media=media)
    return result.get("response")


async def generate_image(prompt: str) -> dict:
    """Generate an image with any configured provider (auto-detect).

    Returns {"mime_type": ..., "data": base64, "provider": ...} or
    {"error": ...}. Tries Google Gemini image generation first, then OpenAI.
    """
    import base64 as _b64

    # 1) Google Gemini (image-capable models return inline_data).
    if get_api_key("google_gemini"):
        try:
            endpoint = f"{LLM_CONFIGS['google_gemini']['endpoint']}/{settings.GEMINI_IMAGE_MODEL}:generateContent"
            async with httpx.AsyncClient(timeout=min(settings.LLM_TIMEOUT_SECONDS * 2, 90)) as client:
                res = await client.post(
                    f"{endpoint}?key={get_api_key('google_gemini')}",
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"], "temperature": 1.0},
                    },
                    headers={"Content-Type": "application/json"},
                )
                if res.status_code == 200:
                    data = res.json()
                    for cand in data.get("candidates", []):
                        for part in cand.get("content", {}).get("parts", []):
                            inline = part.get("inlineData") or part.get("inline_data")
                            if inline and inline.get("data"):
                                return {
                                    "mime_type": inline.get("mimeType", inline.get("mime_type", "image/png")),
                                    "data": inline["data"],
                                    "provider": "google_gemini",
                                }
                    return {"error": "Gemini returned no image"}
                return {"error": f"Gemini image failed ({res.status_code}): {res.text[:200]}"}
        except Exception as e:
            return {"error": f"Gemini image error: {e}"}

    # 2) OpenAI images API.
    api_key = get_api_key("openai")
    if api_key:
        try:
            async with httpx.AsyncClient(timeout=min(settings.LLM_TIMEOUT_SECONDS * 2, 90)) as client:
                res = await client.post(
                    "https://api.openai.com/v1/images/generations",
                    json={
                        "model": settings.OPENAI_IMAGE_MODEL,
                        "prompt": prompt,
                        "n": 1,
                        "size": "1024x1024",
                        "response_format": "b64_json",
                    },
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                )
                if res.status_code == 200:
                    item = res.json().get("data", [{}])[0]
                    if item.get("b64_json"):
                        return {"mime_type": "image/png", "data": item["b64_json"], "provider": "openai"}
                    if item.get("url"):
                        img = await client.get(item["url"])
                        if img.status_code == 200:
                            return {
                                "mime_type": "image/png",
                                "data": _b64.b64encode(img.content).decode(),
                                "provider": "openai",
                            }
                    return {"error": "OpenAI returned no image"}
                return {"error": f"OpenAI image failed ({res.status_code}): {res.text[:200]}"}
        except Exception as e:
            return {"error": f"OpenAI image error: {e}"}

    return {"error": "No image provider configured (set Gemini or OpenAI key in the LLM panel)"}


def media_provider_configured() -> bool:
    """True if at least one provider supports multimodal/vision."""
    return bool(get_api_key("google_gemini") or get_api_key("openai"))


def extract_citations(text: str, sources: list[dict], max_index: int = 9) -> list[dict]:
    """Map [n] markers in an answer back to the numbered sources.

    Returns entries in citation order, each carrying the source fields plus
    the citation index used in the text. Unmatched markers are skipped.
    """
    import re as _re

    citations: list[dict] = []
    seen: set[int] = set()
    for match in _re.finditer(r"\[(\d+)\]", text or ""):
        idx = int(match.group(1))
        if idx < 1 or idx > max_index or idx in seen:
            continue
        seen.add(idx)
        source = sources[idx - 1] if idx - 1 < len(sources) else {}
        if not source:
            continue
        citations.append(
            {
                "document_id": source.get("document_id"),
                "web_id": source.get("web_id"),
                "title": source.get("title", ""),
                "preview": source.get("content", "")[:200],
                "citation": idx,
            }
        )
    return citations
