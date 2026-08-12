"""
Digital Campus - Smart Library API
Aggregates the campus's ordered, searchable collection — KUDOS documents,
Internet Archive items, radio stations and media — into one library. Every
result is preview-only: material plays/reads inside the library, never on
other pages.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import KudosDocument, User

router = APIRouter()


@router.get("/")
async def library_catalog(
    q: str = "",
    kind: str = "",
    limit: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The ordered library — documents (campus), radio (world), archive + media.

    Documents come from the DB (instant); archive/media hits are gathered live
    and best-effort so the library never blocks on external services.
    """
    limit = min(max(limit, 1), 50)
    query = (q or "").strip().lower()

    items = []
    kinds = set(kind.split(",")) if kind else set()

    # 1) KUDOS documents — the campus collection
    if not kinds or "document" in kinds:
        doc_q = db.query(KudosDocument).filter(KudosDocument.is_active)
        if not current_user.is_admin:
            doc_q = doc_q.filter(KudosDocument.is_approved)
        docs = doc_q.order_by(KudosDocument.created_at.desc()).limit(100).all()
        for d in docs:
            if (
                query
                and query not in d.title.lower()
                and query not in (d.summary or "").lower()
                and query not in (d.tags or "").lower()
            ):
                continue
            items.append(
                {
                    "key": f"doc:{d.id}",
                    "kind": "document",
                    "title": d.title,
                    "subtitle": d.summary or d.filename,
                    "preview_url": f"/api/v1/kudos/documents/{d.id}/original",
                    "url": f"/kudos?doc={d.id}",
                    "meta": f"{d.chunk_count} chunks",
                    "order": d.created_at.isoformat() if d.created_at else "",
                    "icon": "📄",
                }
            )

    # 2) Radio stations (world)
    if (not kinds or "audio" in kinds) and not query:
        try:
            from app.core.radio_garden import search as radio_search

            stations = radio_search(db, "", 12) or []
            for s in stations[:12]:
                items.append(
                    {
                        "key": f"radio:{s.get('id')}",
                        "kind": "audio",
                        "title": s.get("name", "Radio"),
                        "subtitle": s.get("country", ""),
                        "preview_url": s.get("stream") or "",
                        "url": s.get("url") or "",
                        "meta": "live radio",
                        "order": "",
                        "icon": "📻",
                    }
                )
        except Exception:
            pass

    # Sort: newest documents first, radio last
    items.sort(key=lambda it: it["order"], reverse=True)

    # 3) Internet Archive (live, best-effort) when searching
    if query:
        try:
            import httpx

            with httpx.Client(timeout=12, follow_redirects=True) as client:
                for media_type, icon in (("texts", "📖"), ("movies", "🎬"), ("audio", "🎵")):
                    res = client.get(
                        "https://archive.org/advancedsearch.php",
                        params={
                            "q": f"{query} AND mediatype:{media_type}",
                            "fl": "identifier,title,creator,year,mediatype",
                            "sort": "downloads desc",
                            "rows": 5,
                            "output": "json",
                        },
                    )
                    if res.status_code != 200:
                        continue
                    found = (res.json().get("response", {}).get("docs") or [])[:5]
                    for d in found:
                        ident = d.get("identifier")
                        if not ident:
                            continue
                        kind = "document" if media_type == "texts" else ("video" if media_type == "movies" else "audio")
                        items.append(
                            {
                                "key": f"archive:{media_type}:{ident}",
                                "kind": kind,
                                "title": d.get("title", ident),
                                "subtitle": d.get("creator") or str(d.get("year") or ""),
                                "preview_url": f"https://archive.org/embed/{ident}",
                                "url": f"https://archive.org/details/{ident}",
                                "meta": "Internet Archive",
                                "order": "",
                                "icon": icon,
                            }
                        )
        except Exception:
            pass

    if query:
        try:
            # 4) Media search (FMHY + free sources) — reuse the media service directly
            from app.api.v1.endpoints.media import search_media

            result = await search_media(query, "all")
            for r in (result.get("results") or [])[:8]:
                items.append(
                    {
                        "key": f"media:{r.get('url')}",
                        "kind": "video",
                        "title": r.get("title", "Media"),
                        "subtitle": r.get("source", ""),
                        "preview_url": r.get("url", ""),
                        "url": r.get("url", ""),
                        "meta": r.get("source", "Media"),
                        "order": "",
                        "icon": r.get("icon", "🎬"),
                    }
                )
        except Exception:
            pass

    if not kinds:
        items = items[:limit]
    return {"query": q, "count": len(items), "items": items}
