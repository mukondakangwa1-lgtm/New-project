"""
Digital Campus - Embed & Sandbox API
Embeddable widgets for any website + KUDOS sandbox for testing.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.deps import get_current_user, require_admin
from app.core.embed_engine import (
    generate_embed_code, register_embed, list_embeds, get_embed_types,
    EMBED_TYPES,
)
from app.core.sandbox import (
    create_proposal, list_proposals, get_proposal, test_proposal,
    approve_proposal, reject_proposal, deploy_proposal,
    sandbox_write_file, sandbox_read_file, rollback_file,
    get_sandbox_status, get_sandbox_log,
)
from app.models import User

router = APIRouter()


# ──────────────────────────────────────────────
# EMBED ENDPOINTS
# ──────────────────────────────────────────────

@router.get("/embed/types")
def embed_types():
    """List all available embed types."""
    return {"types": get_embed_types()}


@router.post("/embed/generate")
def generate_embed(
    embed_type: str,
    base_url: str = "http://localhost:3000",
    width: str = "100%",
    height: str = "600px",
    theme: str = "light",
    admin: User = Depends(require_admin),
):
    """Generate embed code for a widget."""
    result = generate_embed_code(embed_type, base_url, {"width": width, "height": height, "theme": theme})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/embed/register", status_code=201)
def register_new_embed(
    embed_type: str,
    base_url: str = "http://localhost:3000",
    admin: User = Depends(require_admin),
):
    """Register an embed and get its configuration."""
    result = register_embed(embed_type, base_url, created_by=admin.id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/embed/list")
def list_registered_embeds(admin: User = Depends(require_admin)):
    """List all registered embeds."""
    return {"embeds": list_embeds()}


@router.get("/embed/widget/{embed_type}")
def get_widget_page(embed_type: str, base_url: str = ""):
    """Get a standalone widget page that can be embedded anywhere."""
    if embed_type not in EMBED_TYPES:
        raise HTTPException(404, "Widget not found")

    if not base_url:
        base_url = "http://localhost:3000"

    return {
        "type": embed_type,
        "name": EMBED_TYPES[embed_type]["name"],
        "url": f"{base_url}/{embed_type.replace('_', '/')}",
        "iframe_code": f'<iframe src="{base_url}/{embed_type.replace("_", "/")}" width="100%" height="600" frameborder="0"></iframe>',
    }


# ──────────────────────────────────────────────
# SANDBOX ENDPOINTS
# ──────────────────────────────────────────────

class ProposalCreate(BaseModel):
    title: str
    description: str
    category: str = "feature"
    changes: list = []
    test_code: str = ""


@router.get("/sandbox/status")
def sandbox_status(admin: User = Depends(require_admin)):
    """Get sandbox status."""
    return get_sandbox_status()


@router.post("/sandbox/propose", status_code=201)
def propose_change(body: ProposalCreate, admin: User = Depends(require_admin)):
    """KUDOS proposes a change for superadmin review."""
    return create_proposal(body.title, body.description, body.category, body.changes, body.test_code)


@router.get("/sandbox/proposals")
def get_proposals(status: Optional[str] = None, admin: User = Depends(require_admin)):
    """List all proposals."""
    return {"proposals": list_proposals(status)}


@router.get("/sandbox/proposals/{proposal_id}")
def get_single_proposal(proposal_id: int, admin: User = Depends(require_admin)):
    """Get a specific proposal."""
    p = get_proposal(proposal_id)
    if not p:
        raise HTTPException(404, "Proposal not found")
    return p


@router.post("/sandbox/proposals/{proposal_id}/test")
def test_change(proposal_id: int, admin: User = Depends(require_admin)):
    """Test a proposal in the sandbox."""
    result = test_proposal(proposal_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/sandbox/proposals/{proposal_id}/approve")
def approve_change(proposal_id: int, admin: User = Depends(require_admin)):
    """Approve a proposal."""
    result = approve_proposal(proposal_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/sandbox/proposals/{proposal_id}/reject")
def reject_change(proposal_id: int, reason: str = "", admin: User = Depends(require_admin)):
    """Reject a proposal."""
    result = reject_proposal(proposal_id, reason)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/sandbox/proposals/{proposal_id}/deploy")
def deploy_change(proposal_id: int, admin: User = Depends(require_admin)):
    """Deploy an approved proposal."""
    result = deploy_proposal(proposal_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/sandbox/log")
def get_log(limit: int = 50, admin: User = Depends(require_admin)):
    """Get sandbox activity log."""
    return {"log": get_sandbox_log(limit)}
