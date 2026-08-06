"""
Digital Campus - KUDOS Internet Archive Connector
Connects to archive.org — the world's largest digital library.
Wayback Machine, books, texts, media, software, and more.
"""
import json
import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models import KudosWebKnowledge, User
from app.api.v1.endpoints.kudos import simple_summarize

router = APIRouter()

ARCHIVE_ORG_API = "https://archive.org"
WAYBACK_API = "https://web.archive.org"


# ──────────────────────────────────────────────
# WAYBACK MACHINE — Archived Web Pages
# ──────────────────────────────────────────────

@router.post("/wayback")
async def learn_from_wayback(
    url: str,
    year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Learn from an archived web page on the Wayback Machine.
    If year is specified, fetches that year's snapshot.
    Otherwise fetches the most recent snapshot.
    """
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            # Find available snapshots
            cdx_url = f"https://web.archive.org/cdx/search/cdx"
            params = {
                "url": url,
                "output": "json",
                "limit": 5,
                "fl": "timestamp,statuscode,mimetype",
                "filter": "statuscode:200",
                "collapse": "timestamp:8",  # one per year
            }
            if year:
                params["from"] = f"{year}0101"
                params["to"] = f"{year}1231"

            cdx_res = await client.get(cdx_url, params=params)
            if cdx_res.status_code != 200:
                raise HTTPException(400, "Failed to query Wayback Machine")

            rows = cdx_res.json()
            if len(rows) < 2:  # First row is header
                raise HTTPException(404, f"No archived snapshots found for {url}")

            # Use the most recent snapshot
            timestamp = rows[1][0]
            wayback_url = f"https://web.archive.org/web/{timestamp}/{url}"

            # Fetch the archived page
            page_res = await client.get(wayback_url, timeout=15)
            if page_res.status_code != 200:
                raise HTTPException(400, f"Failed to fetch archived page")

            soup = BeautifulSoup(page_res.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                tag.decompose()

            title = soup.title.string if soup.title else url
            text = soup.get_text(separator="\n", strip=True)

            if len(text) < 100:
                raise HTTPException(400, "Archived page has too little text content")

            # Store knowledge
            web = KudosWebKnowledge(
                url=wayback_url,
                title=f"[Wayback {timestamp[:4]}] {title}"[:255],
                content=text[:50000],
                summary=simple_summarize(text),
                is_approved=current_user.is_admin,
                learned_by=current_user.id,
            )
            db.add(web)
            db.commit()
            db.refresh(web)

            return {
                "url": url,
                "wayback_url": wayback_url,
                "timestamp": timestamp,
                "year": timestamp[:4],
                "title": title[:200],
                "chars": len(text),
                "message": f"Learned from Wayback Machine snapshot of {url} from {timestamp[:4]}",
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error fetching from Wayback Machine: {str(e)[:200]}")


@router.get("/wayback/history")
async def wayback_history(url: str, limit: int = 20):
    """Get available snapshots for a URL on the Wayback Machine."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(
                "https://web.archive.org/cdx/search/cdx",
                params={
                    "url": url,
                    "output": "json",
                    "limit": limit + 1,
                    "fl": "timestamp,statuscode,mimetype",
                    "filter": "statuscode:200",
                    "collapse": "timestamp:6",  # one per month
                },
            )
            if res.status_code != 200:
                return {"url": url, "snapshots": [], "count": 0}

            rows = res.json()
            snapshots = []
            for row in rows[1:]:  # Skip header
                ts = row[0]
                snapshots.append({
                    "timestamp": ts,
                    "year": ts[:4],
                    "month": ts[4:6],
                    "day": ts[6:8],
                    "url": f"https://web.archive.org/web/{ts}/{url}",
                })

            return {"url": url, "snapshots": snapshots, "count": len(snapshots)}
    except Exception as e:
        return {"url": url, "snapshots": [], "count": 0, "error": str(e)[:200]}


# ──────────────────────────────────────────────
# INTERNET ARCHIVE SEARCH — Books, Texts, Media
# ──────────────────────────────────────────────

@router.post("/search")
async def search_archive(
    query: str,
    media_type: str = "texts",
    max_results: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search the Internet Archive and learn from results.
    Media types: texts, movies, audio, software, image, web
    """
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            # Search archive.org
            search_res = await client.get(
                f"{ARCHIVE_ORG_API}/advancedsearch.php",
                params={
                    "q": f"{query} AND mediatype:{media_type}",
                    "fl": "identifier,title,description,creator,year,mediatype",
                    "sort": "downloads desc",
                    "rows": max_results,
                    "output": "json",
                },
            )
            if search_res.status_code != 200:
                raise HTTPException(400, "Failed to search Internet Archive")

            data = search_res.json()
            docs = data.get("response", {}).get("docs", [])

            if not docs:
                return {"query": query, "media_type": media_type, "results": [], "message": f"No results found for '{query}' in {media_type}"}

            results = []
            for doc in docs:
                identifier = doc.get("identifier", "")
                title = doc.get("title", "Untitled")
                description = doc.get("description", "")
                creator = doc.get("creator", "Unknown")
                year = doc.get("year", "")

                if isinstance(description, list):
                    description = " ".join(description)
                if isinstance(creator, list):
                    creator = ", ".join(creator[:3])

                # Get full metadata/metadata text
                content = f"Title: {title}\nCreator: {creator}\nYear: {year}\nDescription: {description}"

                # For texts, try to get the actual text content
                if media_type == "texts":
                    try:
                        # Try to get OCR text
                        text_res = await client.get(
                            f"{ARCHIVE_ORG_API}/download/{identifier}/{identifier}_djvu.txt",
                            timeout=10,
                        )
                        if text_res.status_code == 200 and len(text_res.text) > 200:
                            content += f"\n\nExcerpt:\n{text_res.text[:5000]}"
                    except Exception:
                        pass

                # Store knowledge
                web = KudosWebKnowledge(
                    url=f"https://archive.org/details/{identifier}",
                    title=f"[Archive.org] {title}"[:255],
                    content=content[:50000],
                    summary=simple_summarize(content),
                    is_approved=current_user.is_admin,
                    learned_by=current_user.id,
                )
                db.add(web)
                results.append({
                    "identifier": identifier,
                    "title": title[:100],
                    "creator": creator[:100],
                    "year": year,
                    "url": f"https://archive.org/details/{identifier}",
                    "chars": len(content),
                })

            db.commit()

            return {
                "query": query,
                "media_type": media_type,
                "results": results,
                "count": len(results),
                "message": f"Learned from {len(results)} items on Internet Archive",
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error searching Internet Archive: {str(e)[:200]}")


# ──────────────────────────────────────────────
# SPECIFIC ITEM — Fetch details and content
# ──────────────────────────────────────────────

@router.post("/item/{identifier}")
async def learn_from_item(
    identifier: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Learn from a specific Internet Archive item by its identifier."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            # Get metadata
            meta_res = await client.get(f"{ARCHIVE_ORG_API}/metadata/{identifier}")
            if meta_res.status_code != 200:
                raise HTTPException(404, f"Item '{identifier}' not found")

            meta = meta_res.json()
            metadata = meta.get("metadata", {})

            title = metadata.get("title", identifier)
            description = metadata.get("description", "")
            creator = metadata.get("creator", "Unknown")
            year = metadata.get("year", "")
            subject = metadata.get("subject", "")

            if isinstance(description, list):
                description = " ".join(description)
            if isinstance(subject, list):
                subject = ", ".join(subject[:10])

            content = f"Title: {title}\nCreator: {creator}\nYear: {year}\nSubject: {subject}\nDescription: {description}"

            # Try to get text content for texts
            files = meta.get("files", [])
            text_files = [f for f in files if f.get("name", "").endswith(("_djvu.txt", ".txt"))]

            for tf in text_files[:1]:
                try:
                    text_res = await client.get(
                        f"{ARCHIVE_ORG_API}/download/{identifier}/{tf['name']}",
                        timeout=10,
                    )
                    if text_res.status_code == 200 and len(text_res.text) > 200:
                        content += f"\n\nContent:\n{text_res.text[:10000]}"
                except Exception:
                    pass

            # Store knowledge
            web = KudosWebKnowledge(
                url=f"https://archive.org/details/{identifier}",
                title=f"[Archive.org] {title}"[:255],
                content=content[:50000],
                summary=simple_summarize(content),
                is_approved=current_user.is_admin,
                learned_by=current_user.id,
            )
            db.add(web)
            db.commit()

            return {
                "identifier": identifier,
                "title": title[:200],
                "creator": creator[:200],
                "year": year,
                "subject": subject[:200],
                "chars": len(content),
                "files_available": len(files),
                "url": f"https://archive.org/details/{identifier}",
                "message": f"Learned from Internet Archive item: {title}",
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error fetching item: {str(e)[:200]}")


# ──────────────────────────────────────────────
# BATCH LEARN — Popular topics from Internet Archive
# ──────────────────────────────────────────────

@router.post("/batch-learn")
async def batch_learn_archive(
    topics: str = "computer science,mathematics,physics,history,philosophy",
    media_type: str = "texts",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Batch learn from Internet Archive on multiple topics."""
    topic_list = [t.strip() for t in topics.split(",") if t.strip()]
    total_learned = 0

    for topic in topic_list:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                search_res = await client.get(
                    f"{ARCHIVE_ORG_API}/advancedsearch.php",
                    params={
                        "q": f"{topic} AND mediatype:{media_type}",
                        "fl": "identifier,title,description,creator,year",
                        "sort": "downloads desc",
                        "rows": 3,
                        "output": "json",
                    },
                )
                if search_res.status_code != 200:
                    continue

                docs = search_res.json().get("response", {}).get("docs", [])
                for doc in docs:
                    identifier = doc.get("identifier", "")
                    title = doc.get("title", "Untitled")
                    description = doc.get("description", "")
                    if isinstance(description, list):
                        description = " ".join(description)

                    content = f"Topic: {topic}\nTitle: {title}\nDescription: {description}"

                    # Try to get text
                    try:
                        text_res = await client.get(
                            f"{ARCHIVE_ORG_API}/download/{identifier}/{identifier}_djvu.txt",
                            timeout=10,
                        )
                        if text_res.status_code == 200 and len(text_res.text) > 200:
                            content += f"\n\n{text_res.text[:5000]}"
                    except Exception:
                        pass

                    db.add(KudosWebKnowledge(
                        url=f"https://archive.org/details/{identifier}",
                        title=f"[Archive] {title}"[:255],
                        content=content[:50000],
                        summary=simple_summarize(content),
                        is_approved=True,
                        learned_by=current_user.id,
                    ))
                    total_learned += 1

        except Exception:
            continue

    db.commit()
    return {
        "topics": topic_list,
        "items_learned": total_learned,
        "message": f"Learned from {total_learned} Internet Archive items across {len(topic_list)} topics",
    }


# ──────────────────────────────────────────────
# TIMEMACHINE — Browse website history
# ──────────────────────────────────────────────

@router.post("/timemachine")
async def timemachine_learn(
    url: str,
    start_year: int = 2010,
    end_year: int = 2024,
    interval: int = 2,  # every N years
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Learn how a website changed over time by fetching snapshots from different years.
    Great for understanding how technology, organizations, and ideas evolved.
    """
    learned = 0
    years = list(range(start_year, end_year + 1, interval))

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            for year in years:
                try:
                    # Find snapshot for this year
                    cdx_res = await client.get(
                        "https://web.archive.org/cdx/search/cdx",
                        params={
                            "url": url,
                            "output": "json",
                            "limit": 2,
                            "from": f"{year}0601",
                            "to": f"{year}1231",
                            "fl": "timestamp,statuscode",
                            "filter": "statuscode:200",
                        },
                    )
                    if cdx_res.status_code != 200:
                        continue

                    rows = cdx_res.json()
                    if len(rows) < 2:
                        continue

                    timestamp = rows[1][0]
                    wayback_url = f"https://web.archive.org/web/{timestamp}/{url}"

                    page_res = await client.get(wayback_url, timeout=10)
                    if page_res.status_code != 200:
                        continue

                    soup = BeautifulSoup(page_res.text, "html.parser")
                    for tag in soup(["script", "style", "nav", "footer", "header"]):
                        tag.decompose()

                    title = soup.title.string if soup.title else url
                    text = soup.get_text(separator="\n", strip=True)

                    if len(text) > 200:
                        db.add(KudosWebKnowledge(
                            url=wayback_url,
                            title=f"[{year}] {title}"[:255],
                            content=text[:30000],
                            summary=simple_summarize(text),
                            is_approved=current_user.is_admin,
                            learned_by=current_user.id,
                        ))
                        learned += 1

                except Exception:
                    continue

        db.commit()
        return {
            "url": url,
            "years_scanned": years,
            "snapshots_learned": learned,
            "message": f"Learned {learned} snapshots of {url} from {start_year}-{end_year}",
        }

    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)[:200]}")
