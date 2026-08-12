"""Digital Campus - KUDOS Sites API

KUDOS generates websites, CVs, and company profiles and launches them LIVE on
the network in seconds. Generated sites are stored under the ``sites/`` storage
prefix and served publicly — no login required to view.

Endpoints:
  POST   /sites                  — (auth) generate + launch a site
  GET    /sites                  — public list of launched sites
  GET    /sites/{site_id}/       — public index.html
  GET    /sites/{site_id}/{path} — public static asset
  DELETE /sites/{site_id}        — (auth) remove a site
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.core import site_builder, storage
from app.core.deps import get_current_user

router = APIRouter()


class SiteRequest(BaseModel):
    name: str = Field(default="", max_length=120)
    kind: str = Field(default="site", max_length=32)
    prompt: str = Field(default="", max_length=2000)
    profile_data: dict | None = None


def _serve_site(site_id: str, path: str) -> Response:
    if not site_builder.valid_site_id(site_id):
        raise HTTPException(status_code=404, detail="Site not found")
    try:
        key = site_builder.resolve_site_key(site_id, path)
    except site_builder.SiteBuildError:
        raise HTTPException(status_code=400, detail="Invalid site path") from None
    if not storage.exists(key):
        raise HTTPException(status_code=404, detail="Site not found")
    content = storage.download(key)
    filename = key.rsplit("/", 1)[-1]
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    media_type = site_builder.SITE_MIME.get(ext, "application/octet-stream")
    if ext == "html":
        content = site_builder.inject_base(content, site_id)
    return Response(
        content=content,
        media_type=media_type,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "public, max-age=300"},
    )


@router.post("/sites", status_code=201)
async def create_site(
    body: SiteRequest,
    user=Depends(get_current_user),
):
    """KUDOS builds a site (website / CV / company profile) and launches it live."""
    try:
        return await site_builder.generate_site(
            name=body.name,
            kind=body.kind,
            prompt=body.prompt,
            profile_data=body.profile_data,
        )
    except site_builder.SiteBuildError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None


@router.get("/sites")
def list_sites():
    return {"sites": site_builder.list_sites()}


@router.get("/sites/{site_id}/")
def get_site_index(site_id: str):
    return _serve_site(site_id, "index.html")


@router.get("/sites/{site_id}")
def get_site_index_noslash(site_id: str):
    """Serve the site root without a trailing slash too.

    The frontend proxy (Next.js) normalizes ``/sites/{id}/`` to ``/sites/{id}``
    with a 308 redirect; without this route that path only matched DELETE and
    returned 405 on the first click.
    """
    return _serve_site(site_id, "index.html")


@router.get("/sites/{site_id}/{path:path}")
def get_site_asset(site_id: str, path: str):
    return _serve_site(site_id, path)


@router.delete("/sites/{site_id}", status_code=204)
def remove_site(
    site_id: str,
    user=Depends(get_current_user),
):
    if not site_builder.valid_site_id(site_id):
        raise HTTPException(status_code=404, detail="Site not found")
    if not site_builder.delete_site(site_id) and not storage.exists(
        f"{site_builder.SITES_PREFIX}{site_id}/index.html"
    ):
        raise HTTPException(status_code=404, detail="Site not found")
    return None
