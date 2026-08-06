"""
Digital Campus - Media Hub
Movies, shows, audio — sourced from free legal platforms.
VLC integration for playback, FMHY resources for discovery.
"""
import json
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User

router = APIRouter()


# ──────────────────────────────────────────────
# FREE LEGAL MEDIA SOURCES (from FMHY)
# ──────────────────────────────────────────────

FREE_SOURCES = {
    "movies": [
        {"name": "Tubi", "url": "https://tubitv.com", "description": "Free movies & TV with ads", "icon": "🎬"},
        {"name": "Pluto TV", "url": "https://pluto.tv", "description": "Free live TV & on-demand", "icon": "📺"},
        {"name": "Crackle", "url": "https://crackle.com", "description": "Free movies & originals", "icon": "🎥"},
        {"name": "Plex", "url": "https://plex.tv", "description": "Free movies & TV", "icon": "🎞️"},
        {"name": "Kanopy", "url": "https://kanopy.com", "description": "Free with library card", "icon": "📚"},
        {"name": "Hoopla", "url": "https://hoopladigital.com", "description": "Free with library card", "icon": "📖"},
        {"name": "Vudu Free", "url": "https://vudu.com", "description": "Free section with ads", "icon": "🎭"},
        {"name": "YouTube Movies", "url": "https://youtube.com/feed/storefront?bp=ogUCKAQ%3D", "description": "Free movies on YouTube", "icon": "▶️"},
        {"name": "Internet Archive Movies", "url": "https://archive.org/details/moviesandfilms", "description": "Public domain films", "icon": "🕰️"},
        {"name": "Open Culture", "url": "https://openculture.com/free-movies-online", "description": "Curated free movies list", "icon": "🎓"},
    ],
    "tv": [
        {"name": "Tubi TV", "url": "https://tubitv.com/category/tv", "description": "Free TV shows", "icon": "📺"},
        {"name": "Pluto TV", "url": "https://pluto.tv/live-tv", "description": "Live TV channels", "icon": "📡"},
        {"name": "Samsung TV Plus", "url": "https://samsungtvplus.com", "description": "Free live TV", "icon": "📱"},
        {"name": "Roku Channel", "url": "https://therokuchannel.roku.com", "description": "Free movies & TV", "icon": "📺"},
        {"name": "Peacock Free", "url": "https://peacocktv.com", "description": "Free tier available", "icon": "🦚"},
    ],
    "anime": [
        {"name": "Crunchyroll Free", "url": "https://crunchyroll.com", "description": "Free anime with ads", "icon": "🎌"},
        {"name": "Anime-Planet", "url": "https://anime-planet.com", "description": "Free anime streaming", "icon": "⛩️"},
        {"name": "9anime (via FMHY)", "url": "https://fmhy.net", "description": "Check FMHY for current links", "icon": "🗡️"},
    ],
    "music": [
        {"name": "Spotify Free", "url": "https://open.spotify.com", "description": "Free with ads", "icon": "🎵"},
        {"name": "YouTube Music", "url": "https://music.youtube.com", "description": "Free with ads", "icon": "🎶"},
        {"name": "SoundCloud", "url": "https://soundcloud.com", "description": "Free music streaming", "icon": "🔊"},
        {"name": "Bandcamp", "url": "https://bandcamp.com", "description": "Free & paid music", "icon": "🎸"},
        {"name": "Free Music Archive", "url": "https://freemusicarchive.org", "description": "CC-licensed music", "icon": "🎼"},
        {"name": "Internet Archive Audio", "url": "https://archive.org/details/audio", "description": "Public domain audio", "icon": "🕰️"},
    ],
    "educational": [
        {"name": "Khan Academy", "url": "https://khanacademy.org", "description": "Free courses & videos", "icon": "🎓"},
        {"name": "MIT OpenCourseWare", "url": "https://ocw.mit.edu", "description": "Free MIT lectures", "icon": "🏛️"},
        {"name": "Coursera Free", "url": "https://coursera.org", "description": "Free audit mode", "icon": "📚"},
        {"name": "YouTube Edu", "url": "https://youtube.com/education", "description": "Educational videos", "icon": "▶️"},
        {"name": "TED Talks", "url": "https://ted.com", "description": "Free talks on everything", "icon": "🎤"},
    ],
}


# ──────────────────────────────────────────────
# MEDIA SEARCH & DISCOVERY
# ──────────────────────────────────────────────

@router.get("/sources")
def list_sources(category: Optional[str] = None):
    """List all free media sources."""
    if category:
        sources = FREE_SOURCES.get(category, [])
        return {"category": category, "sources": sources, "count": len(sources)}
    return {"categories": {k: len(v) for k, v in FREE_SOURCES.items()}, "sources": FREE_SOURCES}


@router.get("/search")
async def search_media(
    query: str,
    category: str = "all",
):
    """Search for free media across all sources."""
    results = []

    # Search FMHY
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            res = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": f"site:fmhy.net {query}"},
                headers={"User-Agent": "Mozilla/5.0 (compatible; DigitalCampus/1.0)"},
            )
            soup = BeautifulSoup(res.text, "html.parser")
            links = soup.find_all("a", class_="result__a")
            for link in links[:5]:
                href = link.get("href", "")
                title = link.get_text(strip=True)
                if href and "fmhy" in href.lower():
                    results.append({
                        "title": title,
                        "url": href,
                        "source": "FMHY",
                        "icon": "📚",
                    })
    except Exception:
        pass

    # Search 1flex
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            res = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": f"site:1flex.org {query}"},
                headers={"User-Agent": "Mozilla/5.0 (compatible; DigitalCampus/1.0)"},
            )
            soup = BeautifulSoup(res.text, "html.parser")
            links = soup.find_all("a", class_="result__a")
            for link in links[:5]:
                href = link.get("href", "")
                title = link.get_text(strip=True)
                if href:
                    results.append({
                        "title": title,
                        "url": href,
                        "source": "1flex",
                        "icon": "🎬",
                    })
    except Exception:
        pass

    # Search free sources
    for cat, sources in FREE_SOURCES.items():
        if category != "all" and category != cat:
            continue
        for source in sources:
            if query.lower() in source["name"].lower() or query.lower() in source["description"].lower():
                results.append({
                    "title": source["name"],
                    "url": source["url"],
                    "source": cat,
                    "icon": source["icon"],
                    "description": source["description"],
                })

    return {"query": query, "results": results[:20], "count": len(results)}


# ──────────────────────────────────────────────
# VLC INTEGRATION
# ──────────────────────────────────────────────

@router.get("/vlc-link")
def get_vlc_link(url: str, title: str = ""):
    """Generate a VLC deep link for playing media."""
    return {
        "vlc_link": f"vlc://{url}",
        "html5_fallback": url,
        "title": title,
        "instructions": "If VLC is installed, click the link to open directly in VLC. Otherwise, use the HTML5 player.",
    }


@router.post("/play")
def play_in_vlc(url: str, title: str = "", user: User = Depends(get_current_user)):
    """Generate playback links for a media URL."""
    return {
        "vlc_link": f"vlc://{url}",
        "html5_video": f'<video controls src="{url}" style="width:100%;max-width:800px;"></video>',
        "html5_audio": f'<audio controls src="{url}"></audio>',
        "iframe": f'<iframe src="{url}" style="width:100%;height:500px;border:none;"></iframe>',
        "title": title,
    }


# ──────────────────────────────────────────────
# FMHY RESOURCE FINDER
# ──────────────────────────────────────────────

@router.get("/fmhy")
async def search_fmhy(query: str):
    """Search FMHY for free resources."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            res = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": f"site:fmhy.net {query}"},
                headers={"User-Agent": "Mozilla/5.0 (compatible; DigitalCampus/1.0)"},
            )
            soup = BeautifulSoup(res.text, "html.parser")
            links = soup.find_all("a", class_="result__a")
            snippets = soup.find_all("a", class_="result__snippet")

            for i, link in enumerate(links[:10]):
                href = link.get("href", "")
                title = link.get_text(strip=True)
                snippet = snippets[i].get_text(strip=True) if i < len(snippets) else ""

                # Clean DuckDuckGo redirect
                if "uddg=" in href:
                    import urllib.parse
                    href = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg", [href])[0]

                results.append({
                    "title": title,
                    "url": href,
                    "snippet": snippet[:200],
                    "source": "FMHY",
                })
    except Exception:
        pass

    return {"query": query, "results": results, "count": len(results), "note": "Results from fmhy.net — the ultimate free resources directory"}


# ──────────────────────────────────────────────
# 1FLEX SEARCH
# ──────────────────────────────────────────────

@router.get("/1flex")
async def search_1flex(query: str):
    """Search 1flex.org for media."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            res = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": f"site:1flex.org {query}"},
                headers={"User-Agent": "Mozilla/5.0 (compatible; DigitalCampus/1.0)"},
            )
            soup = BeautifulSoup(res.text, "html.parser")
            links = soup.find_all("a", class_="result__a")

            for link in links[:10]:
                href = link.get("href", "")
                title = link.get_text(strip=True)
                if href:
                    if "uddg=" in href:
                        import urllib.parse
                        href = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg", [href])[0]
                    results.append({"title": title, "url": href, "source": "1flex"})
    except Exception:
        pass

    return {"query": query, "results": results, "count": len(results)}
