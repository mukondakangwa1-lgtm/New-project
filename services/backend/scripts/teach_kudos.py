"""Teach KUDOS everything — one-shot curriculum + library book/media guide.

Run inside the backend container (or any process with app importable):

    docker compose -f docker-compose.prod.yml exec backend python scripts/teach_kudos.py

Learns the full requested curriculum from Wikipedia (creating approved web
knowledge that feeds answers immediately) and stores a curated "Where to
find free books & media" guide as a real library document with chunks.
"""
from __future__ import annotations

import asyncio

import httpx

from app.api.v1.endpoints.kudos import chunk_text, extract_keywords, simple_summarize
from app.core.database import SessionLocal
from app.core.wikipedia import WIKIPEDIA_HEADERS
from app.models import KudosChunk, KudosDocument, KudosWebKnowledge, User

TOPICS = [
    # Core knowledge
    "mathematics",
    "science",
    "sociology",
    "psychology",
    "time",
    "time zone",
    # Culture, tribes, tongues
    "culture",
    "cultural studies",
    "tribe",
    "language",
    "dialect",
    "history of writing",
    "Ethiopian Orthodox Tewahedo Church",
    "Ge'ez language",
    "Ethiopian literature",
    # Thinking & growing
    "critical thinking",
    "philosophy of mind",
    "epistemology",
    "learning",
    "study skills",
    # The heart
    "love",
    "humility",
    "patience",
    "empathy",
    "ethics",
    # Faith, mysticism & esoterica
    "grimoire",
    "occult",
    "Hermeticism",
    "alchemy",
    "kabbalah",
    "mysticism",
    # Astrology as culture
    "astrology",
    "history of astronomy",
    # Books & media — where to get them
    "Project Gutenberg",
    "Open Library",
    "Internet Archive",
    "public domain",
    "digital library",
    "open educational resources",
    "free textbook",
    "audiobook",
    "library science",
]

LIBRARY_GUIDE_TITLE = "Where to Find Free Books and Media"
LIBRARY_GUIDE = """\
A learner's guide to free, legal books and media — everything a reader needs.

BOOKS AND TEXTS
- Project Gutenberg (gutenberg.org) — 70,000+ public domain ebooks: free
  classics, no sign-up, plain-text, ePub and Kindle formats.
- Open Library (openlibrary.org) — 3 million+ scanning lending library run by
  the Internet Archive; borrow books straight in the browser.
- Internet Archive Texts (archive.org/details/texts) — millions of scanned,
  borrowable and fully public domain books, newspapers and magazines.
- Wikisource (wikisource.org) — free human-curated source texts and classics.
- Standard Ebooks (standardebooks.org) — gorgeously formatted free classics.
- OER Commons and MIT OpenCourseWare (ocw.mit.edu) — free textbooks, course
  readers and full courses from top universities (Open Educational Resources).
- DOAB / Directory of Open Access Books (directory.doabooks.org) — peer
  reviewed open-access scholarly books.

MOVIES, TV AND FILMS
- Internet Archive Movies (archive.org/details/moviesandfilms) — public
  domain films and old movies.
- Tubi, Pluto TV, Plex, Vudu Free, Crackle, Peacock Free, Roku Channel and
  Samsung TV Plus — free ad-supported movies and TV.
- Kanopy and Hoopla — free movies and shows with a public library card.
- Open Culture and YouTube Movies — free curated cinema lists.

MUSIC AND AUDIO
- Free Music Archive and Internet Archive Audio — Creative Commons and public
  domain music.
- Bandcamp (free section), SoundCloud and YouTube Music — free streaming.
- LibriVox (librivox.org) — free audiobooks read by volunteers from the
  public domain.

COURSES AND LEARNING
- Khan Academy, TED Talks, YouTube Edu, Coursera (free audit) and edX —
  free learning on every subject.
- FMHY (fmhy.net) — the community-maintained directory that points to almost
  every free resource above plus countless more.

HOW TO USE THIS GUIDE
1. Ask KUDOS to search the library (Internet Archive, Open Library, media).
2. Search the Smart Library with any title or subject.
3. Download public domain works freely; borrow from lending libraries; stream
   legally on ad-supported platforms.
"""


async def _fetch_wikipedia(topic: str) -> httpx.Response:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=WIKIPEDIA_HEADERS) as client:
        search = await client.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": topic, "format": "json", "srlimit": 1},
        )
        data = search.json()
        results = data.get("query", {}).get("search", [])
        if not results:
            return search
        title = results[0]["title"]
        article = await client.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "titles": title, "prop": "extracts", "explaintext": True, "format": "json"},
        )
        pages = article.json().get("query", {}).get("pages", {})
        for _, page in pages.items():
            extract = page.get("extract", "")
            if len(extract) > 100:
                return httpx.Response(200, json={"title": title, "extract": extract})
    return httpx.Response(404, json={})


async def _teach(db, admin: User) -> int:
    learned = 0
    for topic in TOPICS:
        try:
            res = await _fetch_wikipedia(topic)
            data = res.json()
            title = data.get("title", "")
            extract = data.get("extract", "")
            if not title or not extract:
                print(f"  ⚠ {topic}: no article")
                continue
            exists = db.query(KudosWebKnowledge).filter(KudosWebKnowledge.title.contains(title)).first()
            if exists:
                print(f"  – {topic}: already learned")
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
            learned += 1
            print(f"  ✅ {topic} → {title}")
        except Exception as e:
            print(f"  ⚠ {topic}: {type(e).__name__}")
    db.commit()
    return learned


def _seed_library_guide(db, admin: User) -> bool:
    existing = db.query(KudosDocument).filter(KudosDocument.title == LIBRARY_GUIDE_TITLE).first()
    if existing:
        print(f"  – guide already in library ({existing.chunk_count} chunks)")
        return False
    text = LIBRARY_GUIDE.strip()
    doc = KudosDocument(
        uploaded_by=admin.id,
        title=LIBRARY_GUIDE_TITLE,
        filename="book-and-media-guide.txt",
        file_type="txt",
        storage_key="",
        content=text,
        summary=simple_summarize(text),
        tags="books,media,library,free,gutenberg,open-library,internet-archive,learning",
        is_approved=True,
    )
    db.add(doc)
    db.flush()
    chunks = chunk_text(text)
    for i, chunk_content in enumerate(chunks):
        db.add(
            KudosChunk(
                document_id=doc.id,
                chunk_index=i,
                content=chunk_content,
                word_count=len(chunk_content.split()),
                keywords=extract_keywords(chunk_content),
            )
        )
    doc.chunk_count = len(chunks)
    print(f"  ✅ guide stored in library ({len(chunks)} chunks)")
    return True


def main() -> None:
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.is_admin).first()
        if not admin:
            print("❌ No admin user found — nothing taught.")
            return
        print(f"Teaching KUDOS {len(TOPICS)} topics (curriculum + books/media)...")
        learned = asyncio.run(_teach(db, admin))
        print(f"\n=====================")
        print(f"  {learned} new topics learned from Wikipedia")
        print(f"  None skipped = already known")
        print(f"=====================\n")
        _seed_library_guide(db, admin)
        db.commit()
    finally:
        db.close()
    print("\n🎉 Teaching complete — KUDOS knows where to find books and media.")


if __name__ == "__main__":
    main()