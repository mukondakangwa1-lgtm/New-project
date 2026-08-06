"""
Digital Campus - KUDOS Search & Social Connectors
Connects to search engines, Wikipedia, social APIs for learning.
"""
import json
import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models import KudosWebKnowledge, User
from app.api.v1.endpoints.kudos import simple_summarize

router = APIRouter()


# ──────────────────────────────────────────────
# DUCKDUCKGO SEARCH (No API key needed)
# ──────────────────────────────────────────────

@router.post("/search")
async def search_and_learn(
    query: str,
    max_results: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search DuckDuckGo and learn from results.
    KUDOS searches, reads pages, and stores knowledge.
    """
    results = []

    try:
        # DuckDuckGo HTML search (no API key needed)
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            res = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (compatible; KUDOS/1.0)"},
            )

            soup = BeautifulSoup(res.text, "html.parser")
            links = soup.find_all("a", class_="result__a")

            for link in links[:max_results]:
                href = link.get("href", "")
                title = link.get_text(strip=True)

                if not href or href.startswith("javascript:"):
                    continue

                # Extract actual URL from DuckDuckGo redirect
                if "uddg=" in href:
                    import urllib.parse
                    href = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg", [href])[0]

                # Fetch and learn from the page
                try:
                    page_res = await client.get(href, timeout=10, follow_redirects=True)
                    if page_res.status_code != 200:
                        continue

                    page_soup = BeautifulSoup(page_res.text, "html.parser")
                    for tag in page_soup(["script", "style", "nav", "footer", "header"]):
                        tag.decompose()

                    text = page_soup.get_text(separator="\n", strip=True)
                    if len(text) < 100:
                        continue

                    # Store knowledge
                    web = KudosWebKnowledge(
                        url=href,
                        title=f"[Search: {query}] {title}"[:255],
                        content=text[:50000],
                        summary=simple_summarize(text),
                        is_approved=current_user.is_admin,
                        learned_by=current_user.id,
                    )
                    db.add(web)
                    results.append({"title": title, "url": href, "chars": len(text)})

                except Exception:
                    continue

        db.commit()

        return {
            "query": query,
            "pages_learned": len(results),
            "results": results,
            "message": f"KUDOS searched for '{query}' and learned from {len(results)} pages",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")


# ──────────────────────────────────────────────
# WIKIPEDIA CONNECTOR (Vast free knowledge)
# ──────────────────────────────────────────────

@router.post("/wikipedia")
async def learn_from_wikipedia(
    topic: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Learn about a topic from Wikipedia."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            # Search Wikipedia
            search_res = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": topic,
                    "format": "json",
                    "srlimit": 3,
                },
            )
            search_data = search_res.json()
            pages = search_data.get("query", {}).get("search", [])

            if not pages:
                return {"message": f"No Wikipedia articles found for '{topic}'", "pages_learned": 0}

            learned = []
            for page in pages:
                title = page["title"]

                # Get full article
                article_res = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "titles": title,
                        "prop": "extracts",
                        "explaintext": True,
                        "format": "json",
                    },
                )
                article_data = article_res.json()
                pages_data = article_data.get("query", {}).get("pages", {})

                for page_id, page_info in pages_data.items():
                    extract = page_info.get("extract", "")
                    if len(extract) < 100:
                        continue

                    web = KudosWebKnowledge(
                        url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                        title=f"[Wikipedia] {title}",
                        content=extract,
                        summary=simple_summarize(extract),
                        is_approved=True,  # Wikipedia is always approved
                        learned_by=current_user.id,
                    )
                    db.add(web)
                    learned.append({"title": title, "chars": len(extract)})

            db.commit()

            return {
                "topic": topic,
                "pages_learned": len(learned),
                "results": learned,
                "message": f"KUDOS learned about '{topic}' from {len(learned)} Wikipedia articles",
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Wikipedia lookup failed: {e}")


# ──────────────────────────────────────────────
# HUMAN INTERACTION LEARNING (Social patterns)
# ──────────────────────────────────────────────

@router.post("/learn-conversation")
async def learn_conversation_patterns(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Teach KUDOS human conversation patterns.
    Learns from social interaction guides and communication resources.
    """
    topics = [
        "how to have a good conversation",
        "active listening techniques",
        "empathetic communication",
        "small talk tips",
        "asking good questions",
    ]

    learned = 0
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for topic in topics:
            try:
                # Search DuckDuckGo
                res = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": topic},
                    headers={"User-Agent": "Mozilla/5.0 (compatible; KUDOS/1.0)"},
                )
                soup = BeautifulSoup(res.text, "html.parser")
                links = soup.find_all("a", class_="result__a")

                if links:
                    href = links[0].get("href", "")
                    if "uddg=" in href:
                        import urllib.parse
                        href = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg", [href])[0]

                    page_res = await client.get(href, timeout=10, follow_redirects=True)
                    if page_res.status_code == 200:
                        page_soup = BeautifulSoup(page_res.text, "html.parser")
                        for tag in page_soup(["script", "style", "nav", "footer", "header"]):
                            tag.decompose()
                        text = page_soup.get_text(separator="\n", strip=True)
                        if len(text) > 200:
                            web = KudosWebKnowledge(
                                url=href,
                                title=f"[Conversation Skills] {topic.title()}"[:255],
                                content=text[:50000],
                                summary=simple_summarize(text),
                                is_approved=True,
                                learned_by=current_user.id,
                            )
                            db.add(web)
                            learned += 1
            except Exception:
                continue

    db.commit()
    return {
        "pages_learned": learned,
        "message": f"KUDOS learned human conversation patterns from {learned} sources",
    }


# ──────────────────────────────────────────────
# LLM LEARNING MODE
# ──────────────────────────────────────────────

@router.post("/learn-llm-style")
async def learn_llm_style(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Teach KUDOS how to respond like an LLM.
    Learns prompt engineering, conversation flow, and response patterns.
    """
    llm_resources = [
        ("https://en.wikipedia.org/wiki/Large_language_model", "Large Language Models"),
        ("https://en.wikipedia.org/wiki/Natural_language_processing", "Natural Language Processing"),
        ("https://en.wikipedia.org/wiki/Chatbot", "Chatbots and Conversational AI"),
        ("https://en.wikipedia.org/wiki/Prompt_engineering", "Prompt Engineering"),
    ]

    learned = 0
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for url, topic in llm_resources:
            try:
                res = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "titles": topic,
                        "prop": "extracts",
                        "explaintext": True,
                        "format": "json",
                    },
                )
                data = res.json()
                pages = data.get("query", {}).get("pages", {})

                for page_id, page_info in pages.items():
                    extract = page_info.get("extract", "")
                    if len(extract) > 100:
                        web = KudosWebKnowledge(
                            url=url,
                            title=f"[LLM Knowledge] {topic}",
                            content=extract,
                            summary=simple_summarize(extract),
                            is_approved=True,
                            learned_by=current_user.id,
                        )
                        db.add(web)
                        learned += 1
            except Exception:
                continue

    db.commit()
    return {
        "pages_learned": learned,
        "message": f"KUDOS learned about LLMs and conversational AI from {learned} sources",
    }
