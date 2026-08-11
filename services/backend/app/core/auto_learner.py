"""
KUDOS Auto-Learner — Autonomous learning engine
Automatically learns from all sources: connectors, web, archive, social, search queries.
Runs as a background process, self-improves continuously.
"""

import asyncio
import json
import os
import threading
import time
from datetime import UTC, datetime

import httpx

# ──────────────────────────────────────────────
# AUTO-LEARNER STATE
# ──────────────────────────────────────────────

_auto_learner_thread: threading.Thread | None = None
_auto_learner_running = False
_auto_learner_interval = 1800  # 30 minutes default
_last_auto_learner_run: datetime | None = None
_auto_learner_log: list[dict] = []
_cycle_active = False
_auto_learner_stats = {
    "total_runs": 0,
    "total_items_learned": 0,
    "connectors_synced": 0,
    "archive_items": 0,
    "web_pages": 0,
    "social_items": 0,
    "search_queries_learned": 0,
}

# ──────────────────────────────────────────────
# PERSISTENT STATE (survives backend restarts)
# ──────────────────────────────────────────────
_KUDOS_STATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "kudos_state",
)
_LEARNER_STATE_FILE = os.path.join(_KUDOS_STATE_DIR, "auto_learner.json")


def _load_state() -> dict:
    try:
        with open(_LEARNER_STATE_FILE) as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_state(data: dict) -> None:
    try:
        os.makedirs(_KUDOS_STATE_DIR, exist_ok=True)
        with open(_LEARNER_STATE_FILE, "w") as fh:
            json.dump(data, fh)
    except Exception:
        pass


# Topics to auto-learn from various sources
AUTO_LEARN_TOPICS = [
    # Technology
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "web development",
    "cloud computing",
    "cybersecurity",
    "blockchain",
    "quantum computing",
    "data science",
    "python programming",
    "javascript",
    "react",
    "node.js",
    "database design",
    "api design",
    "devops",
    # Science
    "physics",
    "chemistry",
    "biology",
    "mathematics",
    "astronomy",
    "environmental science",
    "neuroscience",
    # Business
    "entrepreneurship",
    "marketing",
    "finance",
    "project management",
    "leadership",
    "innovation",
    # Life Skills
    "study skills",
    "time management",
    "critical thinking",
    "communication",
    "public speaking",
    "writing",
    "health and wellness",
    "nutrition",
    "exercise",
    # Current Affairs
    "technology trends",
    "education reform",
    "climate change",
    "space exploration",
    "renewable energy",
]

# Popular subreddits for social learning
AUTO_LEARN_SUBREDDITS = [
    "todayilearned",
    "LifeProTips",
    "explainlikeimfive",
    "science",
    "technology",
    "programming",
    "AskReddit",
    "personalfinance",
    "GetMotivated",
]

# Websites to auto-crawl
AUTO_CRAWL_SITES = [
    {"url": "https://en.wikipedia.org/wiki/Main_Page", "name": "Wikipedia Featured"},
    {"url": "https://news.ycombinator.com", "name": "Hacker News"},
    {"url": "https://dev.to", "name": "DEV Community"},
    {"url": "https://stackoverflow.com/questions", "name": "Stack Overflow"},
]

# Archive.org popular collections
ARCHIVE_COLLECTIONS = [
    "opensource",
    "texts",
    "computersandtech",
    "scienceandtechnology",
    "education",
]


def _log(action: str, details: str, items: int = 0):
    """Log an auto-learner action."""
    global _auto_learner_log, _auto_learner_stats
    entry = {
        "action": action,
        "details": details,
        "items": items,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    _auto_learner_log.append(entry)
    if len(_auto_learner_log) > 200:
        _auto_learner_log = _auto_learner_log[-100:]


# ──────────────────────────────────────────────
# AUTO-LEARN CYCLE
# ──────────────────────────────────────────────


def _run_auto_learner():
    """Main auto-learner loop — runs continuously in background."""
    global _auto_learner_running, _last_auto_learner_run, _auto_learner_stats, _cycle_active

    while _auto_learner_running:
        if _cycle_active:
            time.sleep(30)
            continue
        try:
            db_session = _get_db_session()
            admin = _get_admin_user(db_session)

            if not admin:
                time.sleep(60)
                continue

            _cycle_active = True
            _log("cycle_start", "Auto-learner cycle starting")
            _auto_learner_stats["total_runs"] += 1

            # Phase 1: Sync all connectors
            _sync_all_connectors(db_session, admin)

            # Phase 2: Learn from trending topics via search
            _learn_from_search(db_session, admin)

            # Phase 3: Learn from Wikipedia
            _learn_from_wikipedia(db_session, admin)

            # Phase 4: Learn from Reddit
            _learn_from_reddit(db_session, admin)

            # Phase 5: Learn from web crawls
            _learn_from_crawls(db_session, admin)

            # Phase 6: Learn from Internet Archive
            _learn_from_archive(db_session, admin)

            # Phase 7: Learn social/emotional skills
            _learn_social_skills(db_session, admin)

            _last_auto_learner_run = datetime.now(UTC)
            _log("cycle_complete", f"Cycle complete. Total items learned: {_auto_learner_stats['total_items_learned']}")

            db_session.close()
            _cycle_active = False

        except Exception as e:
            _cycle_active = False
            _log("error", f"Auto-learner error: {str(e)[:200]}")

        # Wait for next cycle
        time.sleep(_auto_learner_interval)


def _get_db_session():
    """Get a database session."""
    from app.core.database import SessionLocal

    return SessionLocal()


def _get_admin_user(db):
    """Get the admin user."""
    from app.models import User

    return db.query(User).filter(User.is_admin).first()


# ──────────────────────────────────────────────
# LEARNING FUNCTIONS
# ──────────────────────────────────────────────


def _sync_all_connectors(db, admin):
    """Sync all approved connectors."""
    import json as json_mod

    from app.models import KudosConnector, KudosSyncLog

    connectors = db.query(KudosConnector).filter(KudosConnector.is_approved, KudosConnector.status != "paused").all()

    for conn in connectors:
        try:
            config = json_mod.loads(conn.config) if conn.config else {}

            # Import and run sync
            from app.api.v1.endpoints.connectors import (
                _sync_api,
                _sync_github,
                _sync_gitlab,
                _sync_npm,
                _sync_pypi,
                _sync_rss,
                _sync_website,
            )

            sync_fn = {
                "github": _sync_github,
                "gitlab": _sync_gitlab,
                "website": _sync_website,
                "api": _sync_api,
                "rss": _sync_rss,
                "npm": _sync_npm,
                "pypi": _sync_pypi,
            }.get(conn.connector_type)

            if not sync_fn:
                continue

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(sync_fn(db, conn, config, admin))
            finally:
                loop.close()

            conn.last_synced_at = datetime.now(UTC)
            conn.items_learned += result["items_new"]
            conn.status = "active"
            conn.error_message = ""

            db.add(
                KudosSyncLog(
                    connector_id=conn.id,
                    action="auto-learn",
                    items_found=result["items_found"],
                    items_new=result["items_new"],
                    items_updated=result["items_updated"],
                    details=result["details"],
                )
            )

            _auto_learner_stats["connectors_synced"] += 1
            _auto_learner_stats["total_items_learned"] += result["items_new"]
            _log("connector_sync", f"{conn.name}: +{result['items_new']} items", result["items_new"])

        except Exception as e:
            conn.status = "error"
            conn.error_message = str(e)[:200]
            _log("connector_error", f"{conn.name}: {str(e)[:100]}")

    db.commit()


def _learn_from_search(db, admin):
    """Learn from web searches on trending topics."""
    # Pick a few random topics each cycle
    import random

    from app.api.v1.endpoints.kudos import simple_summarize
    from app.models import KudosWebKnowledge

    topics = random.sample(AUTO_LEARN_TOPICS, min(3, len(AUTO_LEARN_TOPICS)))

    for topic in topics:
        try:
            # Check if we already know about this topic recently
            existing = (
                db.query(KudosWebKnowledge)
                .filter(
                    KudosWebKnowledge.title.contains(topic.title()),
                    KudosWebKnowledge.is_approved,
                )
                .first()
            )
            if existing:
                continue

            loop = asyncio.new_event_loop()
            try:

                async def _search(topic=topic):
                    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                        res = await client.get(
                            "https://html.duckduckgo.com/html/",
                            params={"q": topic},
                            headers={"User-Agent": "Mozilla/5.0 (compatible; KUDOS/1.0)"},
                        )
                        from bs4 import BeautifulSoup

                        soup = BeautifulSoup(res.text, "html.parser")
                        links = soup.find_all("a", class_="result__a")
                        if links:
                            href = links[0].get("href", "")
                            if "uddg=" in href:
                                import urllib.parse

                                href = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg", [href])[0]
                            page = await client.get(href, timeout=8, follow_redirects=True)
                            if page.status_code == 200:
                                psoup = BeautifulSoup(page.text, "html.parser")
                                for tag in psoup(["script", "style", "nav", "footer", "header"]):
                                    tag.decompose()
                                return psoup.get_text(separator="\n", strip=True)
                    return ""

                text = loop.run_until_complete(_search())
            finally:
                loop.close()

            if text and len(text) > 200:
                db.add(
                    KudosWebKnowledge(
                        url=f"auto-learn://search/{topic.replace(' ', '-')}",
                        title=f"[Auto-Learn] {topic.title()}"[:255],
                        content=text[:50000],
                        summary=simple_summarize(text),
                        is_approved=True,
                        learned_by=admin.id,
                    )
                )
                _auto_learner_stats["web_pages"] += 1
                _auto_learner_stats["total_items_learned"] += 1
                _log("search_learn", f"Learned about: {topic}", 1)

        except Exception:
            continue

    db.commit()


def _learn_from_wikipedia(db, admin):
    """Learn from Wikipedia featured content."""
    import random

    from app.api.v1.endpoints.kudos import simple_summarize
    from app.models import KudosWebKnowledge

    topics = random.sample(AUTO_LEARN_TOPICS, min(2, len(AUTO_LEARN_TOPICS)))

    for topic in topics:
        try:
            loop = asyncio.new_event_loop()
            try:

                async def _wiki(topic=topic):
                    async with httpx.AsyncClient(timeout=10) as client:
                        res = await client.get(
                            "https://en.wikipedia.org/w/api.php",
                            params={
                                "action": "query",
                                "list": "search",
                                "srsearch": topic,
                                "format": "json",
                                "srlimit": 1,
                            },
                        )
                        data = res.json()
                        results = data.get("query", {}).get("search", [])
                        if results:
                            title = results[0]["title"]
                            article = await client.get(
                                "https://en.wikipedia.org/w/api.php",
                                params={
                                    "action": "query",
                                    "titles": title,
                                    "prop": "extracts",
                                    "explaintext": True,
                                    "format": "json",
                                },
                            )
                            pages = article.json().get("query", {}).get("pages", {})
                            for _, page in pages.items():
                                extract = page.get("extract", "")
                                if len(extract) > 100:
                                    return title, extract
                    return None, None

                title, extract = loop.run_until_complete(_wiki())
            finally:
                loop.close()

            if title and extract:
                # Check if already exists
                existing = db.query(KudosWebKnowledge).filter(KudosWebKnowledge.title.contains(title)).first()
                if existing:
                    continue

                db.add(
                    KudosWebKnowledge(
                        url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                        title=f"[Wikipedia] {title}",
                        content=extract[:50000],
                        summary=simple_summarize(extract),
                        is_approved=True,
                        learned_by=admin.id,
                    )
                )
                _auto_learner_stats["total_items_learned"] += 1
                _log("wikipedia", f"Learned: {title}", 1)

        except Exception:
            continue

    db.commit()


def _learn_from_reddit(db, admin):
    """Learn from popular Reddit posts."""
    import random

    from app.api.v1.endpoints.kudos import simple_summarize
    from app.models import KudosWebKnowledge

    subreddit = random.choice(AUTO_LEARN_SUBREDDITS)

    try:
        loop = asyncio.new_event_loop()
        try:

            async def _reddit():
                async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                    res = await client.get(
                        f"https://www.reddit.com/r/{subreddit}/hot.json",
                        params={"limit": 3},
                        headers={"User-Agent": "KUDOS/1.0 (Educational AI)"},
                    )
                    if res.status_code == 200:
                        posts = res.json().get("data", {}).get("children", [])
                        items = []
                        for post in posts[:2]:
                            d = post.get("data", {})
                            title = d.get("title", "")
                            text = d.get("selftext", "")[:2000]
                            if title and len(title) > 10:
                                items.append(
                                    {
                                        "title": title,
                                        "content": f"{title}\n\n{text}",
                                        "url": f"https://reddit.com{d.get('permalink', '')}",
                                    }
                                )
                        return items
                    return []

            items = loop.run_until_complete(_reddit())
        finally:
            loop.close()

        for item in items:
            existing = db.query(KudosWebKnowledge).filter(KudosWebKnowledge.title.contains(item["title"][:50])).first()
            if existing:
                continue

            db.add(
                KudosWebKnowledge(
                    url=item["url"],
                    title=f"[Reddit r/{subreddit}] {item['title']}"[:255],
                    content=item["content"][:50000],
                    summary=simple_summarize(item["content"]),
                    is_approved=True,
                    learned_by=admin.id,
                )
            )
            _auto_learner_stats["social_items"] += 1
            _auto_learner_stats["total_items_learned"] += 1

        db.commit()
        _log("reddit", f"r/{subreddit}: {len(items)} posts", len(items))

    except Exception:
        pass


def _learn_from_crawls(db, admin):
    """Crawl popular websites."""
    import random

    from app.api.v1.endpoints.kudos import simple_summarize
    from app.models import KudosWebKnowledge

    site = random.choice(AUTO_CRAWL_SITES)

    try:
        loop = asyncio.new_event_loop()
        try:

            async def _crawl():
                async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                    res = await client.get(site["url"], headers={"User-Agent": "Mozilla/5.0 (compatible; KUDOS/1.0)"})
                    if res.status_code == 200:
                        from bs4 import BeautifulSoup

                        soup = BeautifulSoup(res.text, "html.parser")
                        for tag in soup(["script", "style", "nav", "footer", "header"]):
                            tag.decompose()
                        text = soup.get_text(separator="\n", strip=True)
                        if len(text) > 200:
                            return text[:10000]
                    return ""

            text = loop.run_until_complete(_crawl())
        finally:
            loop.close()

        if text and len(text) > 500:
            db.add(
                KudosWebKnowledge(
                    url=site["url"],
                    title=f"[Auto-Crawl] {site['name']}"[:255],
                    content=text,
                    summary=simple_summarize(text),
                    is_approved=True,
                    learned_by=admin.id,
                )
            )
            _auto_learner_stats["web_pages"] += 1
            _auto_learner_stats["total_items_learned"] += 1
            _log("crawl", f"Crawled: {site['name']}", 1)
            db.commit()

    except Exception:
        pass


def _learn_from_archive(db, admin):
    """Learn from Internet Archive popular items."""
    import random

    from app.api.v1.endpoints.kudos import simple_summarize
    from app.models import KudosWebKnowledge

    topic = random.choice(AUTO_LEARN_TOPICS[:10])

    try:
        loop = asyncio.new_event_loop()
        try:

            async def _archive():
                async with httpx.AsyncClient(timeout=15) as client:
                    res = await client.get(
                        "https://archive.org/advancedsearch.php",
                        params={
                            "q": f"{topic} AND mediatype:texts",
                            "fl": "identifier,title,description",
                            "sort": "downloads desc",
                            "rows": 2,
                            "output": "json",
                        },
                    )
                    if res.status_code == 200:
                        docs = res.json().get("response", {}).get("docs", [])
                        items = []
                        for doc in docs:
                            identifier = doc.get("identifier", "")
                            title = doc.get("title", "")
                            desc = doc.get("description", "")
                            if isinstance(desc, list):
                                desc = " ".join(desc)
                            items.append(
                                {
                                    "identifier": identifier,
                                    "title": title,
                                    "content": f"{title}\n\n{desc}",
                                    "url": f"https://archive.org/details/{identifier}",
                                }
                            )
                        return items
                    return []

            items = loop.run_until_complete(_archive())
        finally:
            loop.close()

        for item in items:
            existing = db.query(KudosWebKnowledge).filter(KudosWebKnowledge.url == item["url"]).first()
            if existing:
                continue

            db.add(
                KudosWebKnowledge(
                    url=item["url"],
                    title=f"[Archive] {item['title']}"[:255],
                    content=item["content"][:50000],
                    summary=simple_summarize(item["content"]),
                    is_approved=True,
                    learned_by=admin.id,
                )
            )
            _auto_learner_stats["archive_items"] += 1
            _auto_learner_stats["total_items_learned"] += 1

        db.commit()
        _log("archive", f"Archive.org ({topic}): {len(items)} items", len(items))

    except Exception:
        pass


def _learn_social_skills(db, admin):
    """Learn social and emotional intelligence."""
    import random

    from app.api.v1.endpoints.kudos import simple_summarize
    from app.models import KudosWebKnowledge

    topics = [
        "how to have a good conversation",
        "active listening techniques",
        "empathetic communication",
        "how to comfort someone",
        "how to give good advice",
        "conflict resolution skills",
        "how to motivate others",
        "emotional intelligence",
    ]
    topic = random.choice(topics)

    try:
        existing = db.query(KudosWebKnowledge).filter(KudosWebKnowledge.title.contains(topic.title()[:30])).first()
        if existing:
            return

        loop = asyncio.new_event_loop()
        try:

            async def _social():
                async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                    res = await client.get(
                        "https://html.duckduckgo.com/html/",
                        params={"q": topic},
                        headers={"User-Agent": "Mozilla/5.0 (compatible; KUDOS/1.0)"},
                    )
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(res.text, "html.parser")
                    links = soup.find_all("a", class_="result__a")
                    if links:
                        href = links[0].get("href", "")
                        if "uddg=" in href:
                            import urllib.parse

                            href = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg", [href])[0]
                        page = await client.get(href, timeout=8, follow_redirects=True)
                        if page.status_code == 200:
                            psoup = BeautifulSoup(page.text, "html.parser")
                            for tag in psoup(["script", "style", "nav", "footer", "header"]):
                                tag.decompose()
                            return psoup.get_text(separator="\n", strip=True)
                return ""

            text = loop.run_until_complete(_social())
        finally:
            loop.close()

        if text and len(text) > 200:
            db.add(
                KudosWebKnowledge(
                    url=f"auto-learn://social/{topic.replace(' ', '-')}",
                    title=f"[Social Skills] {topic.title()}"[:255],
                    content=text[:50000],
                    summary=simple_summarize(text),
                    is_approved=True,
                    learned_by=admin.id,
                )
            )
            _auto_learner_stats["social_items"] += 1
            _auto_learner_stats["total_items_learned"] += 1
            _log("social", f"Learned: {topic}", 1)
            db.commit()

    except Exception:
        pass


# ──────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────


def get_auto_learner_status() -> dict:
    """Get auto-learner status and stats."""
    return {
        "running": _auto_learner_running,
        "interval_minutes": _auto_learner_interval // 60,
        "last_run": _last_auto_learner_run.isoformat() if _last_auto_learner_run else None,
        "stats": _auto_learner_stats,
        "recent_log": _auto_learner_log[-20:],
    }


def start_auto_learner(interval_minutes: int = 30) -> dict:
    """Start the auto-learner background process (persists across restarts)."""
    global _auto_learner_thread, _auto_learner_running, _auto_learner_interval

    if _auto_learner_running:
        return {"status": "already_running", "interval_minutes": _auto_learner_interval // 60}

    _auto_learner_interval = max(interval_minutes * 60, 300)  # min 5 minutes
    _auto_learner_running = True
    _save_state({"enabled": True, "interval_minutes": _auto_learner_interval // 60})
    _auto_learner_thread = threading.Thread(target=_run_auto_learner, daemon=True)
    _auto_learner_thread.start()

    return {
        "status": "started",
        "interval_minutes": _auto_learner_interval // 60,
        "message": f"Auto-learner started — learning every {_auto_learner_interval // 60} minutes from all sources",
    }


def stop_auto_learner() -> dict:
    """Stop the auto-learner (clears the persistent flag)."""
    global _auto_learner_running
    _auto_learner_running = False
    _save_state({"enabled": False})
    return {"status": "stopped", "message": "Auto-learner stopped"}


def resume_kudos_learner() -> dict:
    """Restore the learner after a backend restart when it was enabled."""
    state = _load_state()
    if not state.get("enabled"):
        return {"status": "disabled"}
    from app.core.config import settings

    interval = state.get("interval_minutes") or settings.KUDOS_LEARN_INTERVAL_MINUTES
    if _auto_learner_running:
        return {"status": "already_running"}
    return start_auto_learner(interval)


def start_learning_on_visit() -> dict:
    """First site visit: switch on continuous learning for good and run an
    immediate learning cycle (the loop's first iteration runs right away)."""
    from app.core.config import settings

    if not settings.KUDOS_LEARN_ON_VISIT:
        return {"status": "disabled", "message": "Learning on visit is disabled"}

    if _auto_learner_running:
        return {"status": "already_learning", "message": "KUDOS is already learning continuously"}

    interval = settings.KUDOS_LEARN_INTERVAL_MINUTES
    result = start_auto_learner(interval)
    result["message"] = (
        f"KUDOS has started continuous learning — improving every {interval} minutes, forever (until an admin stops it)"
    )
    return result


def trigger_learning_cycle() -> dict:
    """Manually trigger a single learning cycle (single-flight)."""
    global _auto_learner_stats, _cycle_active

    if _cycle_active:
        return {"status": "busy", "message": "A learning cycle is already running"}

    _cycle_active = True
    db = _get_db_session()
    admin = _get_admin_user(db)

    if not admin:
        _cycle_active = False
        return {"error": "No admin user found"}

    _log("manual_trigger", "Manual learning cycle triggered")

    results = []

    # Run all learning phases
    try:
        _sync_all_connectors(db, admin)
        results.append("connectors synced")
    except Exception as e:
        results.append(f"connectors error: {str(e)[:50]}")

    try:
        _learn_from_wikipedia(db, admin)
        results.append("wikipedia learned")
    except Exception as e:
        results.append(f"wikipedia error: {str(e)[:50]}")

    try:
        _learn_from_search(db, admin)
        results.append("search learned")
    except Exception as e:
        results.append(f"search error: {str(e)[:50]}")

    try:
        _learn_from_reddit(db, admin)
        results.append("reddit learned")
    except Exception as e:
        results.append(f"reddit error: {str(e)[:50]}")

    try:
        _learn_from_archive(db, admin)
        results.append("archive learned")
    except Exception as e:
        results.append(f"archive error: {str(e)[:50]}")

    try:
        _learn_social_skills(db, admin)
        results.append("social skills learned")
    except Exception as e:
        results.append(f"social error: {str(e)[:50]}")

    db.close()
    _cycle_active = False

    return {
        "status": "completed",
        "results": results,
        "stats": _auto_learner_stats,
        "message": f"Learning cycle complete. Total items learned: {_auto_learner_stats['total_items_learned']}",
    }
