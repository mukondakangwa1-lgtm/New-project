"""
Digital Campus - KUDOS LLM API
Configure and use external LLMs (Google Gemini, OpenAI, Groq, Ollama).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.llm_engine import (
    set_api_key, get_llm_status, query_best_llm, get_llm_response,
    build_human_prompt, LLM_CONFIGS,
)
from app.models import User

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
    provider: str,
    api_key: str,
    admin: User = Depends(require_admin),
):
    """Configure an LLM provider with API key (superadmin only)."""
    if provider not in LLM_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider. Use: {', '.join(LLM_CONFIGS.keys())}")

    set_api_key(provider, api_key)
    return {
        "status": "configured",
        "provider": provider,
        "name": LLM_CONFIGS[provider]["name"],
        "message": f"✅ {LLM_CONFIGS[provider]['name']} configured successfully!",
    }


@router.post("/test")
async def test_llm(
    provider: str = "",
    prompt: str = "Hello, who are you?",
    admin: User = Depends(require_admin),
):
    """Test an LLM provider (superadmin only)."""
    if provider:
        # Test specific provider
        api_key = (await __import__('app.core.llm_engine', fromlist=['get_api_key']).get_api_key(provider)) if False else None
        from app.core.llm_engine import get_api_key as gak
        if not gak(provider):
            raise HTTPException(status_code=400, detail=f"No API key configured for {provider}")

    result = await query_best_llm(prompt)
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
