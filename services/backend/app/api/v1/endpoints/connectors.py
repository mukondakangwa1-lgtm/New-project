"""
Digital Campus - KUDOS Connectors
Universal connectors: GitHub, GitLab, websites, APIs, RSS feeds, npm, PyPI.
Crawls, fetches, and learns from any source. Supports offline knowledge packs.
Auto-sync: bulk sync all connectors on a schedule.
"""
import asyncio
import base64
import json
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.deps import get_current_user, require_admin
from app.models import (
    KudosChunk,
    KudosConnector,
    KudosDocument,
    KudosKnowledgePack,
    KudosSyncLog,
    KudosWebKnowledge,
    User,
)
from app.schemas import (
    KudosConnectorCreate,
    KudosConnectorResponse,
    KudosPackCreate,
    KudosPackImport,
    KudosPackResponse,
    KudosSyncLogResponse,
    KudosSyncResult,
)

router = APIRouter()

# Import from kudos module
from app.api.v1.endpoints.kudos import (
    chunk_text,
    extract_keywords,
    simple_summarize,
)

# ──────────────────────────────────────────────
# AUTO-SYNC ENGINE
# ──────────────────────────────────────────────

_auto_sync_thread: Optional[threading.Thread] = None
_auto_sync_running = False
_auto_sync_interval = 3600  # default: 1 hour
_last_auto_sync: Optional[datetime] = None
_auto_sync_results: list[dict] = []


def _run_auto_sync():
    """Background thread that syncs all connectors periodically."""
    global _auto_sync_running, _last_auto_sync, _auto_sync_results
    while _auto_sync_running:
        db = SessionLocal()
        try:
            connectors = (
                db.query(KudosConnector)
                .filter(KudosConnector.is_approved == True, KudosConnector.status != "paused")
                .all()
            )
            admin = db.query(User).filter(User.is_admin == True).first()
            if not admin:
                time.sleep(_auto_sync_interval)
                continue

            results = []
            for conn in connectors:
                try:
                    config = json.loads(conn.config) if conn.config else {}

                    # Run sync in event loop
                    loop = asyncio.new_event_loop()
                    try:
                        if conn.connector_type == "github":
                            result = loop.run_until_complete(_sync_github(db, conn, config, admin))
                        elif conn.connector_type == "gitlab":
                            result = loop.run_until_complete(_sync_gitlab(db, conn, config, admin))
                        elif conn.connector_type == "website":
                            result = loop.run_until_complete(_sync_website(db, conn, config, admin))
                        elif conn.connector_type == "api":
                            result = loop.run_until_complete(_sync_api(db, conn, config, admin))
                        elif conn.connector_type == "rss":
                            result = loop.run_until_complete(_sync_rss(db, conn, config, admin))
                        elif conn.connector_type == "npm":
                            result = loop.run_until_complete(_sync_npm(db, conn, config, admin))
                        elif conn.connector_type == "pypi":
                            result = loop.run_until_complete(_sync_pypi(db, conn, config, admin))
                        else:
                            continue
                    finally:
                        loop.close()

                    conn.last_synced_at = datetime.now(timezone.utc)
                    conn.items_learned += result["items_new"]
                    conn.status = "active"
                    conn.error_message = ""

                    log = KudosSyncLog(
                        connector_id=conn.id,
                        action="auto-sync",
                        items_found=result["items_found"],
                        items_new=result["items_new"],
                        items_updated=result["items_updated"],
                        details=result["details"],
                    )
                    db.add(log)
                    results.append({
                        "connector": conn.name,
                        "items_new": result["items_new"],
                        "status": "success",
                    })

                except Exception as e:
                    conn.status = "error"
                    conn.error_message = str(e)[:500]
                    log = KudosSyncLog(
                        connector_id=conn.id,
                        action="auto-sync-error",
                        details=str(e)[:1000],
                    )
                    db.add(log)
                    results.append({
                        "connector": conn.name,
                        "status": "error",
                        "error": str(e)[:200],
                    })

            db.commit()
            _last_auto_sync = datetime.now(timezone.utc)
            _auto_sync_results = results

        except Exception:
            pass
        finally:
            db.close()

        time.sleep(_auto_sync_interval)


# ──────────────────────────────────────────────
# CONNECTOR CRUD
# ──────────────────────────────────────────────


@router.get("/", response_model=list[KudosConnectorResponse])
def list_connectors(
    db: Session = Depends(get_db),
):
    """List all approved connectors (public)."""
    return (
        db.query(KudosConnector)
        .filter(KudosConnector.is_approved == True)
        .order_by(KudosConnector.created_at.desc())
        .all()
    )


@router.post("/", response_model=KudosConnectorResponse, status_code=201)
def create_connector(
    body: KudosConnectorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new connector to a source."""
    valid_types = ["github", "gitlab", "website", "api", "rss", "npm", "pypi"]
    if body.connector_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid type. Must be one of: {', '.join(valid_types)}",
        )

    connector = KudosConnector(
        created_by=current_user.id,
        name=body.name,
        connector_type=body.connector_type,
        source_url=body.source_url,
        config=body.config,
        is_approved=current_user.is_admin,
    )
    db.add(connector)
    db.commit()
    db.refresh(connector)
    return connector


@router.patch("/{connector_id}", response_model=KudosConnectorResponse)
def update_connector(
    connector_id: int,
    body: dict,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Update connector (admin: approve, pause, etc.)."""
    conn = db.query(KudosConnector).filter(KudosConnector.id == connector_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connector not found")
    for field in ["name", "status", "is_approved", "config"]:
        if field in body:
            setattr(conn, field, body[field])
    db.commit()
    db.refresh(conn)
    return conn


@router.delete("/{connector_id}", status_code=204)
def delete_connector(
    connector_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Delete a connector (admin only)."""
    conn = db.query(KudosConnector).filter(KudosConnector.id == connector_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connector not found")
    db.delete(conn)
    db.commit()


@router.post("/sync-all")
async def sync_all_connectors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sync ALL approved connectors at once."""
    connectors = (
        db.query(KudosConnector)
        .filter(KudosConnector.is_approved == True, KudosConnector.status != "paused")
        .all()
    )
    if not connectors:
        return {"message": "No connectors to sync", "results": []}

    results = []
    total_items = 0

    for conn in connectors:
        config = json.loads(conn.config) if conn.config else {}
        try:
            sync_fn = {
                "github": _sync_github, "gitlab": _sync_gitlab,
                "website": _sync_website, "api": _sync_api,
                "rss": _sync_rss, "npm": _sync_npm, "pypi": _sync_pypi,
            }.get(conn.connector_type)
            if not sync_fn:
                results.append({"connector": conn.name, "status": "skipped"})
                continue

            result = await sync_fn(db, conn, config, current_user)
            conn.last_synced_at = datetime.now(timezone.utc)
            conn.items_learned += result["items_new"]
            conn.status = "active"
            conn.error_message = ""
            db.add(KudosSyncLog(
                connector_id=conn.id, action="bulk-sync",
                items_found=result["items_found"], items_new=result["items_new"],
                items_updated=result["items_updated"], details=result["details"],
            ))
            total_items += result["items_new"]
            results.append({"connector": conn.name, "type": conn.connector_type, "items_new": result["items_new"], "status": "success"})
        except Exception as e:
            conn.status = "error"
            conn.error_message = str(e)[:500]
            db.add(KudosSyncLog(connector_id=conn.id, action="bulk-sync-error", details=str(e)[:1000]))
            results.append({"connector": conn.name, "status": "error", "error": str(e)[:200]})

    db.commit()
    return {"message": f"Synced {len(connectors)} connectors, {total_items} new items", "total_connectors": len(connectors), "total_new_items": total_items, "results": results}


@router.post("/auto-sync/start")
def start_auto_sync(
    interval_minutes: int = 60,
    admin: User = Depends(require_admin),
):
    """Start automatic background sync (superadmin only)."""
    global _auto_sync_thread, _auto_sync_running, _auto_sync_interval
    if _auto_sync_running:
        return {"status": "already_running", "interval_minutes": _auto_sync_interval // 60, "last_sync": _last_auto_sync.isoformat() if _last_auto_sync else None}
    _auto_sync_interval = max(interval_minutes * 60, 300)
    _auto_sync_running = True
    _auto_sync_thread = threading.Thread(target=_run_auto_sync, daemon=True)
    _auto_sync_thread.start()
    return {"status": "started", "interval_minutes": _auto_sync_interval // 60, "message": f"Auto-sync started — every {_auto_sync_interval // 60} minutes"}


@router.post("/auto-sync/stop")
def stop_auto_sync(admin: User = Depends(require_admin)):
    """Stop automatic background sync (superadmin only)."""
    global _auto_sync_running
    _auto_sync_running = False
    return {"status": "stopped", "message": "Auto-sync stopped"}


@router.get("/auto-sync/status")
def auto_sync_status():
    """Get auto-sync status and recent results."""
    return {"running": _auto_sync_running, "interval_minutes": _auto_sync_interval // 60, "last_sync": _last_auto_sync.isoformat() if _last_auto_sync else None, "recent_results": _auto_sync_results[-10:]}


@router.get("/{connector_id}/logs", response_model=list[KudosSyncLogResponse])
def get_sync_logs(
    connector_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get sync logs for a connector."""
    return (
        db.query(KudosSyncLog)
        .filter(KudosSyncLog.connector_id == connector_id)
        .order_by(KudosSyncLog.created_at.desc())
        .limit(50)
        .all()
    )


# ──────────────────────────────────────────────
# SYNC — CONNECT AND LEARN
# ──────────────────────────────────────────────


@router.post("/{connector_id}/sync", response_model=KudosSyncResult)
async def sync_connector(
    connector_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sync a connector — fetch content and learn from it.
    Supports: github, gitlab, website, api, rss, npm, pypi.
    """
    conn = db.query(KudosConnector).filter(KudosConnector.id == connector_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connector not found")

    config = json.loads(conn.config) if conn.config else {}

    try:
        if conn.connector_type == "github":
            result = await _sync_github(db, conn, config, current_user)
        elif conn.connector_type == "gitlab":
            result = await _sync_gitlab(db, conn, config, current_user)
        elif conn.connector_type == "website":
            result = await _sync_website(db, conn, config, current_user)
        elif conn.connector_type == "api":
            result = await _sync_api(db, conn, config, current_user)
        elif conn.connector_type == "rss":
            result = await _sync_rss(db, conn, config, current_user)
        elif conn.connector_type == "npm":
            result = await _sync_npm(db, conn, config, current_user)
        elif conn.connector_type == "pypi":
            result = await _sync_pypi(db, conn, config, current_user)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown connector type: {conn.connector_type}")

        # Update connector
        conn.last_synced_at = datetime.now(timezone.utc)
        conn.items_learned += result["items_new"]
        conn.status = "active"
        conn.error_message = ""

        # Log sync
        log = KudosSyncLog(
            connector_id=conn.id,
            action="sync",
            items_found=result["items_found"],
            items_new=result["items_new"],
            items_updated=result["items_updated"],
            details=result["details"],
        )
        db.add(log)
        db.commit()

        return KudosSyncResult(
            connector_id=conn.id,
            **result,
        )

    except Exception as e:
        conn.status = "error"
        conn.error_message = str(e)[:500]
        log = KudosSyncLog(
            connector_id=conn.id,
            action="error",
            details=str(e)[:1000],
        )
        db.add(log)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")


# ──────────────────────────────────────────────
# CONNECTOR IMPLEMENTATIONS
# ──────────────────────────────────────────────


async def _sync_github(db: Session, conn: KudosConnector, config: dict, user: User) -> dict:
    """
    Sync a GitHub repository.
    Fetches: README, file tree, top code files, issues.
    URL format: https://github.com/owner/repo
    """
    url = conn.source_url.rstrip("/")
    parts = url.replace("https://github.com/", "").split("/")
    if len(parts) < 2:
        raise ValueError("Invalid GitHub URL. Use: https://github.com/owner/repo")

    owner, repo = parts[0], parts[1]
    api_base = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = config.get("token")
    if token:
        headers["Authorization"] = f"token {token}"

    items_found = 0
    items_new = 0

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # 1. Fetch repo info
        repo_res = await client.get(api_base, headers=headers)
        if repo_res.status_code != 200:
            raise ValueError(f"GitHub API error: {repo_res.status_code}")
        repo_data = repo_res.json()
        items_found += 1

        _store_web_knowledge(
            db, conn.source_url,
            f"{owner}/{repo} — GitHub Repository",
            f"Repository: {repo_data.get('full_name', '')}\n"
            f"Description: {repo_data.get('description', '')}\n"
            f"Language: {repo_data.get('language', '')}\n"
            f"Stars: {repo_data.get('stargazers_count', 0)}\n"
            f"Forks: {repo_data.get('forks_count', 0)}\n"
            f"Topics: {', '.join(repo_data.get('topics', []))}\n",
            user.id, conn.is_approved,
        )
        items_new += 1

        # 2. Fetch README
        try:
            readme_res = await client.get(f"{api_base}/readme", headers=headers)
            if readme_res.status_code == 200:
                readme_data = readme_res.json()
                readme_text = base64.b64decode(readme_data.get("content", "")).decode("utf-8", errors="ignore")
                items_found += 1
                _store_web_knowledge(
                    db, f"{url}/blob/main/README.md",
                    f"{owner}/{repo} — README",
                    readme_text,
                    user.id, conn.is_approved,
                )
                items_new += 1
        except Exception:
            pass

        # 3. Fetch file tree (top-level)
        try:
            tree_res = await client.get(f"{api_base}/git/trees/HEAD?recursive=0", headers=headers)
            if tree_res.status_code == 200:
                tree = tree_res.json()
                file_list = "\n".join(
                    f"{'📁' if t['type'] == 'tree' else '📄'} {t['path']}"
                    for t in tree.get("tree", [])[:100]
                )
                items_found += 1
                _store_web_knowledge(
                    db, f"{url}/tree/HEAD",
                    f"{owner}/{repo} — File Tree",
                    f"Repository file structure:\n{file_list}",
                    user.id, conn.is_approved,
                )
                items_new += 1
        except Exception:
            pass

        # 4. Fetch issues (if configured)
        if config.get("include_issues", True):
            try:
                issues_res = await client.get(
                    f"{api_base}/issues?state=open&per_page=20",
                    headers=headers,
                )
                if issues_res.status_code == 200:
                    issues = issues_res.json()
                    if issues:
                        issues_text = "\n\n".join(
                            f"#{i['number']} {i['title']}\n{i.get('body', '')[:300]}"
                            for i in issues[:10]
                        )
                        items_found += 1
                        _store_web_knowledge(
                            db, f"{url}/issues",
                            f"{owner}/{repo} — Open Issues ({len(issues)})",
                            issues_text,
                            user.id, conn.is_approved,
                        )
                        items_new += 1
            except Exception:
                pass

        # 5. Fetch top code files
        code_extensions = config.get("code_extensions", [".py", ".js", ".ts", ".md", ".json", ".yaml", ".yml"])
        try:
            tree_res = await client.get(f"{api_base}/git/trees/HEAD?recursive=1", headers=headers)
            if tree_res.status_code == 200:
                all_files = tree_res.json().get("tree", [])
                code_files = [
                    f for f in all_files
                    if f["type"] == "blob"
                    and any(f["path"].endswith(ext) for ext in code_extensions)
                    and f.get("size", 0) < 50000
                ][:20]

                for f in code_files:
                    try:
                        file_res = await client.get(
                            f"{api_base}/contents/{f['path']}",
                            headers=headers,
                        )
                        if file_res.status_code == 200:
                            content = base64.b64decode(file_res.json().get("content", "")).decode("utf-8", errors="ignore")
                            if len(content) > 100:
                                items_found += 1
                                _store_document(
                                    db, f"{owner}/{repo}/{f['path']}",
                                    f["path"], f["path"].rsplit(".", 1)[-1],
                                    content, user.id, conn.is_approved,
                                )
                                items_new += 1
                    except Exception:
                        continue
        except Exception:
            pass

    return {
        "items_found": items_found,
        "items_new": items_new,
        "items_updated": 0,
        "details": f"Synced {owner}/{repo}: {items_new} items learned",
    }


async def _sync_gitlab(db: Session, conn: KudosConnector, config: dict, user: User) -> dict:
    """Sync a GitLab repository (similar to GitHub but uses GitLab API)."""
    url = conn.source_url.rstrip("/")
    # Extract project path from URL
    project_path = url.replace("https://gitlab.com/", "").replace("/", "%2F")
    api_base = f"https://gitlab.com/api/v4/projects/{project_path}"

    items_found = 0
    items_new = 0

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        headers = {}
        token = config.get("token")
        if token:
            headers["PRIVATE-TOKEN"] = token

        # Fetch project info
        res = await client.get(api_base, headers=headers)
        if res.status_code != 200:
            raise ValueError(f"GitLab API error: {res.status_code}")
        project = res.json()
        items_found += 1

        _store_web_knowledge(
            db, url,
            f"{project.get('path_with_namespace', '')} — GitLab Repository",
            f"Project: {project.get('name', '')}\n"
            f"Description: {project.get('description', '')}\n"
            f"Language: {project.get('language', '')}\n"
            f"Stars: {project.get('star_count', 0)}\n",
            user.id, conn.is_approved,
        )
        items_new += 1

        # Fetch README
        try:
            readme_res = await client.get(f"{api_base}/repository/files/README.md/raw?ref=main", headers=headers)
            if readme_res.status_code == 200:
                items_found += 1
                _store_web_knowledge(
                    db, f"{url}/-/blob/main/README.md",
                    f"{project.get('path_with_namespace', '')} — README",
                    readme_res.text,
                    user.id, conn.is_approved,
                )
                items_new += 1
        except Exception:
            pass

    return {
        "items_found": items_found,
        "items_new": items_new,
        "items_updated": 0,
        "details": f"Synced GitLab project: {items_new} items",
    }


async def _sync_website(db: Session, conn: KudosConnector, config: dict, user: User) -> dict:
    """
    Crawl a website — follows links up to depth N.
    Great for documentation sites, wikis, etc.
    """
    max_pages = config.get("max_pages", 20)
    max_depth = config.get("max_depth", 2)
    url = conn.source_url.rstrip("/")

    items_found = 0
    items_new = 0
    visited = set()
    to_visit = [(url, 0)]

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        while to_visit and len(visited) < max_pages:
            page_url, depth = to_visit.pop(0)
            if page_url in visited or depth > max_depth:
                continue
            visited.add(page_url)

            try:
                res = await client.get(page_url)
                if res.status_code != 200:
                    continue

                soup = BeautifulSoup(res.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()

                title = soup.title.string if soup.title else page_url
                text = soup.get_text(separator="\n", strip=True)

                if len(text) > 100:
                    items_found += 1
                    _store_web_knowledge(
                        db, page_url, title[:255], text,
                        user.id, conn.is_approved,
                    )
                    items_new += 1

                # Follow links (same domain only)
                if depth < max_depth:
                    from urllib.parse import urljoin, urlparse
                    base_domain = urlparse(url).netloc
                    for a in soup.find_all("a", href=True):
                        link = urljoin(page_url, a["href"]).split("#")[0].split("?")[0]
                        if urlparse(link).netloc == base_domain and link not in visited:
                            to_visit.append((link, depth + 1))

            except Exception:
                continue

    return {
        "items_found": items_found,
        "items_new": items_new,
        "items_updated": 0,
        "details": f"Crawled {len(visited)} pages, learned {items_new}",
    }


async def _sync_api(db: Session, conn: KudosConnector, config: dict, user: User) -> dict:
    """Fetch and learn from a REST API endpoint."""
    url = conn.source_url
    method = config.get("method", "GET").upper()
    headers = config.get("headers", {})

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.request(method, url, headers=headers)
        res.raise_for_status()

        content_type = res.headers.get("content-type", "")
        if "json" in content_type:
            data = res.json()
            text = json.dumps(data, indent=2, ensure_ascii=False)[:50000]
        else:
            text = res.text[:50000]

    items_found = 1
    _store_web_knowledge(
        db, url,
        config.get("title", f"API: {url}"),
        text,
        user.id, conn.is_approved,
    )

    return {
        "items_found": items_found,
        "items_new": 1,
        "items_updated": 0,
        "details": f"Fetched API response from {url}",
    }


async def _sync_rss(db: Session, conn: KudosConnector, config: dict, user: User) -> dict:
    """Fetch and learn from an RSS/Atom feed."""
    url = conn.source_url
    max_items = config.get("max_items", 20)

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        res = await client.get(url)
        res.raise_for_status()

    soup = BeautifulSoup(res.text, "xml")
    items = soup.find_all("item") or soup.find_all("entry")

    items_found = len(items)
    items_new = 0

    for item in items[:max_items]:
        title = item.find("title")
        title_text = title.get_text(strip=True) if title else "Untitled"

        # Get content from description or content:encoded
        desc = item.find("description") or item.find("content") or item.find("summary")
        desc_text = desc.get_text(strip=True) if desc else ""

        link = item.find("link")
        link_text = link.get_text(strip=True) if link else url

        if desc_text and len(desc_text) > 50:
            _store_web_knowledge(
                db, link_text,
                f"[RSS] {title_text}",
                f"{title_text}\n\n{desc_text}",
                user.id, conn.is_approved,
            )
            items_new += 1

    return {
        "items_found": items_found,
        "items_new": items_new,
        "items_updated": 0,
        "details": f"RSS feed: {items_new} items from {url}",
    }


async def _sync_npm(db: Session, conn: KudosConnector, config: dict, user: User) -> dict:
    """Learn about an npm package."""
    package = conn.source_url.replace("https://www.npmjs.com/package/", "").strip("/")

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.get(f"https://registry.npmjs.org/{package}")
        if res.status_code != 200:
            raise ValueError(f"Package not found: {package}")
        data = res.json()

    latest = data.get("dist-tags", {}).get("latest", "")
    latest_data = data.get("versions", {}).get(latest, {})
    readme = data.get("readme", "")[:10000]

    text = (
        f"Package: {data.get('name', package)}\n"
        f"Description: {data.get('description', '')}\n"
        f"Latest version: {latest}\n"
        f"License: {latest_data.get('license', '')}\n"
        f"Keywords: {', '.join(latest_data.get('keywords', []))}\n\n"
        f"README:\n{readme}"
    )

    _store_web_knowledge(
        db, f"https://www.npmjs.com/package/{package}",
        f"[npm] {data.get('name', package)}",
        text, user.id, conn.is_approved,
    )

    return {
        "items_found": 1,
        "items_new": 1,
        "items_updated": 0,
        "details": f"Learned npm package: {package}",
    }


async def _sync_pypi(db: Session, conn: KudosConnector, config: dict, user: User) -> dict:
    """Learn about a PyPI package."""
    package = conn.source_url.replace("https://pypi.org/project/", "").strip("/")

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.get(f"https://pypi.org/pypi/{package}/json")
        if res.status_code != 200:
            raise ValueError(f"Package not found: {package}")
        data = res.json()

    info = data.get("info", {})
    text = (
        f"Package: {info.get('name', package)}\n"
        f"Version: {info.get('version', '')}\n"
        f"Summary: {info.get('summary', '')}\n"
        f"License: {info.get('license', '')}\n"
        f"Author: {info.get('author', '')}\n"
        f"Home page: {info.get('home_page', '')}\n\n"
        f"Description:\n{info.get('description', '')[:10000]}"
    )

    _store_web_knowledge(
        db, f"https://pypi.org/project/{package}/",
        f"[PyPI] {info.get('name', package)}",
        text, user.id, conn.is_approved,
    )

    return {
        "items_found": 1,
        "items_new": 1,
        "items_updated": 0,
        "details": f"Learned PyPI package: {package}",
    }


# ──────────────────────────────────────────────
# KNOWLEDGE PACKS — OFFLINE SYNC
# ──────────────────────────────────────────────


@router.post("/packs", response_model=KudosPackResponse, status_code=201)
def create_knowledge_pack(
    body: KudosPackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export the current knowledge base into a portable pack.
    Can be shared and imported by other users for offline use.
    """
    # Gather all approved knowledge
    docs = db.query(KudosDocument).filter(
        KudosDocument.is_approved == True, KudosDocument.is_active == True
    ).all()

    web = db.query(KudosWebKnowledge).filter(
        KudosWebKnowledge.is_approved == True, KudosWebKnowledge.is_active == True
    ).all()

    pack_items = []
    for doc in docs:
        chunks = db.query(KudosChunk).filter(KudosChunk.document_id == doc.id).all()
        pack_items.append({
            "type": "document",
            "title": doc.title,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "summary": doc.summary,
            "tags": doc.tags,
            "chunks": [
                {"content": c.content, "keywords": c.keywords}
                for c in chunks
            ],
        })

    for item in web:
        pack_items.append({
            "type": "web",
            "url": item.url,
            "title": item.title,
            "summary": item.summary,
            "content": item.content[:5000],
        })

    pack_data = json.dumps(pack_items, ensure_ascii=False)
    pack = KudosKnowledgePack(
        created_by=current_user.id,
        name=body.name,
        description=body.description,
        pack_data=pack_data,
        item_count=len(pack_items),
        size_bytes=len(pack_data.encode("utf-8")),
        is_shared=body.is_shared,
    )
    db.add(pack)
    db.commit()
    db.refresh(pack)
    return pack


@router.get("/packs", response_model=list[KudosPackResponse])
def list_knowledge_packs(
    db: Session = Depends(get_db),
):
    """List available shared knowledge packs (public)."""
    return (
        db.query(KudosKnowledgePack)
        .filter(KudosKnowledgePack.is_shared == True)
        .order_by(KudosKnowledgePack.created_at.desc())
        .all()
    )


@router.post("/packs/{pack_id}/import")
def import_knowledge_pack(
    pack_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import a knowledge pack — adds all items to the knowledge base."""
    pack = db.query(KudosKnowledgePack).filter(KudosKnowledgePack.id == pack_id).first()
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")

    if not pack.is_shared and pack.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="This pack is not shared")

    items = json.loads(pack.pack_data)
    imported = 0

    for item in items:
        if item["type"] == "document":
            doc = KudosDocument(
                uploaded_by=current_user.id,
                title=item["title"],
                filename=item.get("filename", ""),
                file_type=item.get("file_type", ""),
                content="",
                summary=item.get("summary", ""),
                tags=item.get("tags", ""),
                is_approved=True,  # imported packs are pre-approved
            )
            db.add(doc)
            db.flush()
            for i, chunk_data in enumerate(item.get("chunks", [])):
                chunk = KudosChunk(
                    document_id=doc.id,
                    chunk_index=i,
                    content=chunk_data["content"],
                    word_count=len(chunk_data["content"].split()),
                    keywords=chunk_data.get("keywords", ""),
                )
                db.add(chunk)
            doc.chunk_count = len(item.get("chunks", []))
            imported += 1

        elif item["type"] == "web":
            web = KudosWebKnowledge(
                url=item.get("url", ""),
                title=item.get("title", ""),
                content=item.get("content", ""),
                summary=item.get("summary", ""),
                is_approved=True,
                learned_by=current_user.id,
            )
            db.add(web)
            imported += 1

    db.commit()
    return {"imported": imported, "pack_name": pack.name}


@router.delete("/packs/{pack_id}", status_code=204)
def delete_knowledge_pack(
    pack_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a knowledge pack."""
    pack = db.query(KudosKnowledgePack).filter(
        KudosKnowledgePack.id == pack_id,
        KudosKnowledgePack.created_by == current_user.id,
    ).first()
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found or not yours")
    db.delete(pack)
    db.commit()


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────


def _store_web_knowledge(db, url, title, content, user_id, is_approved):
    """Store web knowledge and auto-chunk."""
    summary = simple_summarize(content)
    web = KudosWebKnowledge(
        url=url, title=title[:255], content=content,
        summary=summary, is_approved=is_approved, learned_by=user_id,
    )
    db.add(web)
    db.flush()
    return web


def _store_document(db, title, filename, file_type, content, user_id, is_approved):
    """Store a document with chunking."""
    summary = simple_summarize(content)
    doc = KudosDocument(
        uploaded_by=user_id, title=title[:255], filename=filename,
        file_type=file_type, content=content, summary=summary,
        is_approved=is_approved,
    )
    db.add(doc)
    db.flush()

    chunks = chunk_text(content)
    for i, chunk_content in enumerate(chunks):
        chunk = KudosChunk(
            document_id=doc.id, chunk_index=i,
            content=chunk_content,
            word_count=len(chunk_content.split()),
            keywords=extract_keywords(chunk_content),
        )
        db.add(chunk)
    doc.chunk_count = len(chunks)
    return doc
