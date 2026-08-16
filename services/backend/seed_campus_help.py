"""
Digital Campus — KUDOS campus-help knowledge.
Teaches the in-app KUDOS guide how students and staff use the platform.
Does not touch superadmin accounts or the local 270-agent HQ.
Run: cd services/backend && python seed_campus_help.py
"""
import re

from app.core.database import SessionLocal, init_db
from app.models import KudosChunk, KudosDocument, User

init_db()
db = SessionLocal()

admin = db.query(User).filter(User.is_admin == True).first()
if not admin:
    print("❌ Run seed.py first to create superadmin")
    raise SystemExit(1)

HELP_DOCS = [
    {
        "title": "How to use Digital Campus",
        "filename": "campus_help.txt",
        "tags": "help,guide,howto,campus,login,courses,attendance,kudos",
        "content": """
Digital Campus is the public university platform. KUDOS on this site is the in-app guide.
The 270-agent KUDOS HQ stays on the superadmin PC and is not exposed to the world.

Create an account:
1. Open Register
2. Enter your name, email, and a password
3. Submit, then go to Login
4. After login you can open Dashboard, Courses, Register, Chat, Hub, and KUDOS

Login:
- Use the email and password you registered with
- Superadmin login is only for the platform owner
- If login fails, check that the backend health card on the home page says healthy

Courses:
- Open Courses to browse the catalog
- Each course shows title, code, instructor, and credits
- Enroll from the course page when you are logged in
- Your enrollments appear on Dashboard

Attendance / Register:
- Open Register → Attendance to see today's sessions
- Students check in to a live session
- Lecturers can mark a whole session
- Timetable lets staff create recurring class times
- Report shows attendance totals per course

Assignments and grades:
- Academic tools live under the API prefix /academic and lecturer dashboards
- Students submit work, lecturers grade and leave feedback
- Check Dashboard and notifications after a grade is posted

Exams and quizzes:
- Lecturers create exams with multiple choice, true/false, or short answer
- Students attempt an exam once it is published
- Auto-grading covers objective questions

Chat:
- Open Chat, create or join a room, then send messages
- Live chat uses WebSocket; if the socket is down, messages queue offline and sync later
- You must be logged in

Hub (social):
- Open Hub to read campus posts
- Create a post from Hub → New
- React to posts from the feed

KUDOS campus guide:
- Open KUDOS and ask how to use any page
- Example questions: How do I take attendance? How do I join a course? Where is Chat?
- Upload Doc / Teach Web / Connectors are optional extras
- Campus KUDOS does not run the 270 local agents and does not spend HQ quota by default

Studio and Media are not available to normal users. They stay on the Superadmin dashboard.

Superadmin (unchanged):
- Only admin@campus.edu (or another admin account) can open Superadmin
- Superadmin dashboard, root terminal, guardian, code agent, auto-learn, and LLM config stay as they are
- Studio (speaking, broadcast, video calls, journal) and Media Hub stay on Superadmin only
- Change the default password immediately: Superadmin chat → change password YOUR_NEW_PASSWORD
- Do not share superadmin credentials

If something looks offline:
- Home page Backend card should say healthy
- Try Login again
- Ask KUDOS: "the site looks broken, what should I check?"
""",
    },
    {
        "title": "Digital Campus page map",
        "filename": "campus_pages.txt",
        "tags": "help,pages,navigation,menu,map",
        "content": """
Digital Campus page map — tell users where to click.

Public / student pages:
- / Home — health status, course count, link to KUDOS help
- /register Sign up
- /login Sign in
- /dashboard Your profile and activity
- /courses Course catalog
- /register/attendance Today's attendance
- /register/timetable Class timetable
- /register/report Attendance reports
- /chat Real-time rooms
- /hub/feed Campus social feed
- /hub/new New social post
- /kudos Campus KUDOS guide

KUDOS extra pages (still on campus, optional):
- /kudos/upload Upload a document
- /kudos/learn Teach a web page
- /kudos/connect Knowledge connectors
- /kudos/archive Internet Archive
- /kudos/autolearn Auto-learner status
- /kudos/llm LLM keys (admin)
- /kudos/agent Code agent (admin)
- /kudos/guardian Security dashboard (admin)
- /kudos/admin KUDOS moderation (admin)

Superadmin only (unchanged):
- /admin/dashboard Superadmin control room
- /root Root terminal
- /studio Speaking, broadcast, calls, journalist
- /media Media Hub

Mobile: use the hamburger menu. Desktop: use the top nav. The purple KUDOS link is the help desk.
""",
    },
]


def _chunk(text: str) -> list[str]:
    words = text.split()
    size, overlap = 500, 50
    if len(words) <= size:
        return [text.strip()] if text.strip() else []
    chunks = []
    start = 0
    while start < len(words):
        piece = " ".join(words[start : start + size]).strip()
        if piece:
            chunks.append(piece)
        start += size - overlap
    return chunks


def _keywords(text: str) -> str:
    stop = set("the a an and or but in on at to for of is it that this with from by as are was were".split())
    freq: dict[str, int] = {}
    for word in re.findall(r"[a-zA-Z]{3,}", text.lower()):
        if word not in stop:
            freq[word] = freq.get(word, 0) + 1
    return ",".join(word for word, _ in sorted(freq.items(), key=lambda item: -item[1])[:20])


count = 0
for doc_data in HELP_DOCS:
    existing = db.query(KudosDocument).filter(KudosDocument.title == doc_data["title"]).first()
    if existing:
        db.query(KudosChunk).filter(KudosChunk.document_id == existing.id).delete()
        existing.content = doc_data["content"]
        existing.summary = doc_data["content"][:300].strip()
        existing.tags = doc_data["tags"]
        existing.is_approved = True
        existing.is_active = True
        doc = existing
        print(f"↻ updated: {doc_data['title']}")
    else:
        doc = KudosDocument(
            uploaded_by=admin.id,
            title=doc_data["title"],
            filename=doc_data["filename"],
            file_type="txt",
            content=doc_data["content"],
            summary=doc_data["content"][:300].strip(),
            tags=doc_data["tags"],
            is_approved=True,
            is_active=True,
        )
        db.add(doc)
        db.flush()
        print(f"✅ {doc_data['title']}")
    chunks = _chunk(doc_data["content"])
    for index, content in enumerate(chunks):
        db.add(
            KudosChunk(
                document_id=doc.id,
                chunk_index=index,
                content=content,
                word_count=len(content.split()),
                keywords=_keywords(content),
            )
        )
    doc.chunk_count = len(chunks)
    count += 1

db.commit()
db.close()
print(f"\n🎉 Campus help ready ({count} new docs). KUDOS on Digital Campus can now teach the app.")
