"""
Digital Campus - KUDOS Social & Search Learning
Connects to Google, Reddit, social platforms to learn human interaction patterns.
"""
import json
import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models import KudosWebKnowledge, User
from app.api.v1.endpoints.kudos import simple_summarize, extract_keywords

router = APIRouter()


# ──────────────────────────────────────────────
# GOOGLE SEARCH (requires API key)
# ──────────────────────────────────────────────

@router.post("/google")
async def google_search_learn(
    query: str,
    api_key: str = "",
    search_engine_id: str = "",
    max_results: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search Google and learn from results.
    Requires Google Custom Search API key (free tier: 100 queries/day).
    Get one at: https://programmablesearchengine.google.com/
    """
    # Use default public search engine if no ID provided
    cx = search_engine_id or "017576662512468239146:omuauf_lfve"

    if not api_key:
        # Fallback: scrape Google search results via DuckDuckGo
        return await _fallback_search_learn(query, max_results, db, current_user)

    results = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": api_key,
                    "cx": cx,
                    "q": query,
                    "num": min(max_results, 10),
                },
            )
            if res.status_code != 200:
                # Fallback to DuckDuckGo
                return await _fallback_search_learn(query, max_results, db, current_user)

            data = res.json()
            items = data.get("items", [])

            for item in items:
                title = item.get("title", "")
                link = item.get("link", "")
                snippet = item.get("snippet", "")

                if not link:
                    continue

                # Fetch full page content
                try:
                    page_res = await client.get(link, timeout=8, follow_redirects=True)
                    if page_res.status_code == 200:
                        soup = BeautifulSoup(page_res.text, "html.parser")
                        for tag in soup(["script", "style", "nav", "footer", "header"]):
                            tag.decompose()
                        text = soup.get_text(separator="\n", strip=True)
                        if len(text) > 200:
                            web = KudosWebKnowledge(
                                url=link,
                                title=f"[Google: {query}] {title}"[:255],
                                content=text[:50000],
                                summary=simple_summarize(text),
                                is_approved=current_user.is_admin,
                                learned_by=current_user.id,
                            )
                            db.add(web)
                            results.append({"title": title, "url": link, "chars": len(text)})
                except Exception:
                    # Store snippet at least
                    if snippet:
                        web = KudosWebKnowledge(
                            url=link,
                            title=f"[Google: {query}] {title}"[:255],
                            content=snippet,
                            summary=snippet,
                            is_approved=current_user.is_admin,
                            learned_by=current_user.id,
                        )
                        db.add(web)
                        results.append({"title": title, "url": link, "chars": len(snippet)})

        db.commit()
        return {
            "query": query,
            "pages_learned": len(results),
            "results": results,
            "source": "google",
            "message": f"KUDOS searched Google for '{query}' and learned from {len(results)} pages",
        }

    except Exception as e:
        # Fallback to DuckDuckGo
        return await _fallback_search_learn(query, max_results, db, current_user)


async def _fallback_search_learn(query: str, max_results: int, db, current_user):
    """Fallback: use DuckDuckGo when Google API key not provided."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
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

                if "uddg=" in href:
                    import urllib.parse
                    href = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg", [href])[0]

                try:
                    page_res = await client.get(href, timeout=8, follow_redirects=True)
                    if page_res.status_code == 200:
                        page_soup = BeautifulSoup(page_res.text, "html.parser")
                        for tag in page_soup(["script", "style", "nav", "footer", "header"]):
                            tag.decompose()
                        text = page_soup.get_text(separator="\n", strip=True)
                        if len(text) > 200:
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
    except Exception:
        pass

    return {
        "query": query,
        "pages_learned": len(results),
        "results": results,
        "source": "duckduckgo",
        "message": f"KUDOS searched for '{query}' and learned from {len(results)} pages",
    }


# ──────────────────────────────────────────────
# SOCIAL MEDIA LEARNING
# ──────────────────────────────────────────────

@router.post("/learn-social")
async def learn_social_interaction(
    platform: str = "general",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Teach KUDOS human social interaction patterns from public sources.
    Platforms: general, reddit, twitter, linkedin, discord
    """
    social_queries = {
        "general": [
            "how to have a great conversation",
            "empathetic communication techniques",
            "understanding human emotions in text",
            "how to be a good listener",
            "reading between the lines in conversations",
            "how to give thoughtful advice",
            "how to comfort someone who is sad",
            "how to celebrate someone's success",
            "how to disagree respectfully",
            "how to tell a good story",
        ],
        "reddit": [
            "reddit how to help someone with a problem",
            "reddit best advice for students",
            "reddit how to make friends",
            "reddit dealing with stress",
            "reddit career advice",
            "reddit life lessons learned",
        ],
        "twitter": [
            "how to communicate concisely",
            "how to be witty in conversations",
            "how to express emotions briefly",
            "how to give quick helpful advice",
        ],
        "linkedin": [
            "professional communication skills",
            "how to network effectively",
            "how to give professional advice",
            "how to respond to career questions",
        ],
        "discord": [
            "how to moderate a community",
            "how to welcome new members",
            "how to resolve conflicts in groups",
            "how to keep conversations engaging",
        ],
    }

    queries = social_queries.get(platform, social_queries["general"])
    learned = 0

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        for query in queries[:5]:  # Limit to 5 per call to avoid rate limiting
            try:
                res = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0 (compatible; KUDOS/1.0)"},
                )
                soup = BeautifulSoup(res.text, "html.parser")
                links = soup.find_all("a", class_="result__a")

                if links:
                    href = links[0].get("href", "")
                    if "uddg=" in href:
                        import urllib.parse
                        href = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg", [href])[0]

                    page_res = await client.get(href, timeout=8, follow_redirects=True)
                    if page_res.status_code == 200:
                        page_soup = BeautifulSoup(page_res.text, "html.parser")
                        for tag in page_soup(["script", "style", "nav", "footer", "header"]):
                            tag.decompose()
                        text = page_soup.get_text(separator="\n", strip=True)
                        if len(text) > 200:
                            web = KudosWebKnowledge(
                                url=href,
                                title=f"[Social: {platform}] {query.title()}"[:255],
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
        "platform": platform,
        "pages_learned": learned,
        "message": f"KUDOS learned {platform} social interaction patterns from {learned} sources",
    }


# ──────────────────────────────────────────────
# REDDIT LEARNING (public posts)
# ──────────────────────────────────────────────

@router.post("/learn-reddit")
async def learn_from_reddit(
    subreddit: str = "LifeProTips",
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Learn from public Reddit posts.
    Good subreddits: LifeProTips, AskReddit, explainlikeimfive, advice
    """
    results = []
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            res = await client.get(
                f"https://www.reddit.com/r/{subreddit}/hot.json",
                params={"limit": limit},
                headers={"User-Agent": "KUDOS/1.0 (Educational AI)"},
            )
            if res.status_code != 200:
                return {"subreddit": subreddit, "posts_learned": 0, "message": f"Could not access r/{subreddit}"}

            data = res.json()
            posts = data.get("data", {}).get("children", [])

            for post in posts:
                post_data = post.get("data", {})
                title = post_data.get("title", "")
                selftext = post_data.get("selftext", "")
                permalink = post_data.get("permalink", "")
                score = post_data.get("score", 0)

                if not title or len(title) < 10:
                    continue

                content = f"Title: {title}"
                if selftext:
                    content += f"\n\n{selftext}"

                # Get top comments
                try:
                    comments_res = await client.get(
                        f"https://www.reddit.com{permalink}.json",
                        params={"limit": 5, "sort": "top"},
                        headers={"User-Agent": "KUDOS/1.0 (Educational AI)"},
                    )
                    if comments_res.status_code == 200:
                        comments_data = comments_res.json()
                        if len(comments_data) > 1:
                            comments = comments_data[1].get("data", {}).get("children", [])
                            for comment in comments[:3]:
                                body = comment.get("data", {}).get("body", "")
                                if body and len(body) > 20:
                                    content += f"\n\nComment: {body}"
                except Exception:
                    pass

                if len(content) > 100:
                    web = KudosWebKnowledge(
                        url=f"https://reddit.com{permalink}",
                        title=f"[Reddit r/{subreddit}] {title}"[:255],
                        content=content[:50000],
                        summary=simple_summarize(content),
                        is_approved=True,
                        learned_by=current_user.id,
                    )
                    db.add(web)
                    results.append({"title": title[:80], "score": score})

        db.commit()
    except Exception as e:
        return {"subreddit": subreddit, "posts_learned": 0, "message": f"Error: {str(e)[:200]}"}

    return {
        "subreddit": subreddit,
        "posts_learned": len(results),
        "results": results,
        "message": f"KUDOS learned from {len(results)} posts in r/{subreddit}",
    }


# ──────────────────────────────────────────────
# HUMAN EMOTION LEARNING
# ──────────────────────────────────────────────

@router.post("/learn-emotions")
async def learn_human_emotions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Teach KUDOS to understand and respond to human emotions."""
    emotion_topics = [
        "how to respond when someone is sad",
        "how to celebrate good news with someone",
        "how to comfort someone who failed an exam",
        "how to motivate someone who is giving up",
        "how to apologize sincerely",
        "how to express gratitude meaningfully",
        "how to handle someone who is angry",
        "how to support someone going through tough times",
    ]

    learned = 0
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        for topic in emotion_topics:
            try:
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

                    page_res = await client.get(href, timeout=8, follow_redirects=True)
                    if page_res.status_code == 200:
                        page_soup = BeautifulSoup(page_res.text, "html.parser")
                        for tag in page_soup(["script", "style", "nav", "footer", "header"]):
                            tag.decompose()
                        text = page_soup.get_text(separator="\n", strip=True)
                        if len(text) > 200:
                            web = KudosWebKnowledge(
                                url=href,
                                title=f"[Emotions] {topic.title()}"[:255],
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
        "message": f"KUDOS learned about human emotions from {learned} sources",
    }


# ──────────────────────────────────────────────
# WIKIPEDIA LEARNING (broad knowledge)
# ──────────────────────────────────────────────

@router.post("/learn-wikipedia-batch")
async def learn_wikipedia_batch(
    topics: str = "artificial intelligence,machine learning,psychology,sociology,communication,education",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Learn about multiple topics from Wikipedia at once."""
    topic_list = [t.strip() for t in topics.split(",") if t.strip()]
    learned = 0

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        for topic in topic_list:
            try:
                res = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={"action": "query", "list": "search", "srsearch": topic, "format": "json", "srlimit": 1},
                )
                data = res.json()
                results = data.get("query", {}).get("search", [])
                if results:
                    title = results[0]["title"]
                    article = await client.get(
                        "https://en.wikipedia.org/w/api.php",
                        params={"action": "query", "titles": title, "prop": "extracts", "explaintext": True, "format": "json"},
                    )
                    pages = article.json().get("query", {}).get("pages", {})
                    for _, page in pages.items():
                        extract = page.get("extract", "")
                        if len(extract) > 100:
                            web = KudosWebKnowledge(
                                url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                                title=f"[Wikipedia] {title}",
                                content=extract[:50000],
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
        "topics": topic_list,
        "pages_learned": learned,
        "message": f"KUDOS learned about {learned} topics from Wikipedia",
    }
