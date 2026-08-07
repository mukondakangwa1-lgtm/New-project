"""
Digital Campus - KUDOS LLM API
Configure and use external LLMs (Google Gemini, OpenAI, Groq, Ollama).
"""
from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import require_admin
from app.core.llm_engine import (
    set_api_key,
    get_llm_status,
    query_best_llm,
    provider_is_configured,
    LLM_CONFIGS,
)
from app.models import User
from app.schemas import LLMConfigureRequest

router = APIRouter()


@router.get("/status")
def llm_status(admin: User = Depends(require_admin)):
    """Get status of all LLM providers (superadmin only)."""
    return {
        "providers": get_llm_status(),
        "total_configured": sum(1 for p in get_llm_status() if p["configured"]),
    }


@router.post("/configure")
def configure_llm(
    body: LLMConfigureRequest,
    admin: User = Depends(require_admin),
):
    """Configure an LLM provider for the current process (superadmin only).

    API keys are accepted in the JSON body rather than query parameters so
    reverse proxies and access logs do not record them. For persistent
    production configuration, use environment variables or a secret manager.
    """
    provider = body.provider.strip().lower()
    if provider not in LLM_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider. Use: {', '.join(LLM_CONFIGS.keys())}")

    set_api_key(provider, body.api_key.strip())
    return {
        "status": "configured",
        "provider": provider,
        "name": LLM_CONFIGS[provider]["name"],
        "persistent": False,
        "message": f"✅ {LLM_CONFIGS[provider]['name']} configured for this process. Use deployment secrets for persistence.",
    }


@router.post("/test")
async def test_llm(
    provider: str = "",
    prompt: str = "Hello, who are you?",
    admin: User = Depends(require_admin),
):
    """Test an LLM provider (superadmin only)."""
    provider = provider.strip().lower()
    if provider:
        # Test specific provider
        if provider not in LLM_CONFIGS or not provider_is_configured(provider):
            raise HTTPException(status_code=400, detail=f"Provider {provider} is not configured")

    result = await query_best_llm(prompt, provider=provider or None)
    return result


@router.get("/providers")
def list_providers():
    """List all available LLM providers (public)."""
    providers = []
    for key, config in LLM_CONFIGS.items():
        providers.append({
            "id": key,
            "name": config["name"],
            "icon": config["icon"],
            "endpoint": config["endpoint"],
        })
    return {"providers": providers}
