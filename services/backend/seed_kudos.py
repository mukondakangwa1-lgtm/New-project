"""
Digital Campus - KUDOS Final Knowledge Seed
Complete knowledge base for self-sufficient operation.
Run: cd services/backend && .venv/bin/python seed.py && .venv/bin/python seed_kudos.py
"""
import re
from app.core.database import SessionLocal, init_db
from app.models import KudosChunk, KudosConnector, KudosDocument, KudosWebKnowledge, User

init_db()
db = SessionLocal()

admin = db.query(User).filter(User.is_admin == True).first()
if not admin:
    print("❌ Run seed.py first to create superadmin")
    exit(1)

# ──────────────────────────────────────────────
# COMPLETE KNOWLEDGE BASE
# ──────────────────────────────────────────────

ALL_KNOWLEDGE = [
    # ═══════════════════════════════════════════
    # SYSTEM & OPERATIONS
    # ═══════════════════════════════════════════
    {
        "title": "KUDOS Complete Operations Manual",
        "filename": "kudos_manual.txt",
        "tags": "kudos,operations,manual,commands,deployment,env,git",
        "content": """
KUDOS Complete Operations Manual — Everything KUDOS Needs to Know

=== ENVIRONMENT MANAGEMENT ===
.env file location: services/backend/.env
Required variables:
- SECRET_KEY: Random string for JWT security (change from default!)
- DATABASE_URL: sqlite:///./digital_campus.db (or PostgreSQL URL)
- GOOGLE_GEMINI_API_KEY: Optional, for LLM responses
- OPENAI_API_KEY: Optional, for OpenAI integration
- GROQ_API_KEY: Optional, for fast inference

How to manage .env:
1. Copy .env.example to .env
2. Edit with any text editor or via superadmin chat
3. Restart backend after changes
4. Never commit .env to git (it's in .gitignore)

=== GIT OPERATIONS ===
Check status: git status
Stage changes: git add -A
Commit: git commit -m "description"
Push: git push origin branch-name
Pull: git pull origin branch-name
Force push: git push --force (use carefully!)

=== DEPLOYMENT PLATFORMS ===
Render (free, easiest):
- render.com → New Web Service → Connect GitHub
- Build: pip install -r requirements.txt
- Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT
- URL: https://app-name.onrender.com

Vercel (frontend only, free):
- npm i -g vercel && cd frontend && vercel
- URL: https://project.vercel.app

Railway ($5 free, includes database):
- railway.app → New Project → Deploy from GitHub
- URL: https://app.up.railway.app

=== SUPERADMIN CHAT COMMANDS ===
Git: git status, git commit [msg], git push, git pull
Env: show env, set env KEY=value
Deploy: deploy, deploy to render, generate render.yaml
Brain: start learning, stop learning, status
Identity: rename [name], learn about [topic]
Guidelines: add rule [rule]
Password: change password [new_pass]
System: devices, system info, network
Embed: embed chat, embed kudos
Sandbox: propose [desc], test proposal [id], approve proposal [id]
Help: help (lists all commands)

=== STARTUP SEQUENCE ===
1. cd services/backend
2. python3 -m venv .venv
3. .venv/bin/pip install -r requirements.txt
4. .venv/bin/python seed.py (creates superadmin)
5. .venv/bin/python seed_kudos.py (loads knowledge)
6. .venv/bin/uvicorn app.main:app --reload --port 8000

=== LOGIN ===
Email: admin@campus.edu
Password: superadmin123 (change immediately via chat!)
""",
    },
    {
        "title": "How to Edit and Manage Environment Variables",
        "filename": "env_management.txt",
        "tags": "env,environment,variables,configuration,secret,api key",
        "content": """
Environment Variables — Configuration for the Digital Campus platform.

What is .env?
- A file that stores configuration values
- Never committed to git (in .gitignore)
- Contains secrets like API keys and passwords
- Read by the application on startup

Location: services/backend/.env

Required Variables:
SECRET_KEY=your-random-secret-key-here
DATABASE_URL=sqlite:///./digital_campus.db

Optional Variables (for KUDOS AI):
GOOGLE_GEMINI_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key
GROQ_API_KEY=your-groq-key

How to Edit .env:

Method 1: Via superadmin chat
- Type: show env (view current values)
- Type: set env SECRET_KEY=mynewsecretkey123
- Restart backend: Ctrl+C then uvicorn app.main:app --reload --port 8000

Method 2: Via terminal
- nano services/backend/.env
- Edit values, save (Ctrl+O, Enter, Ctrl+X)
- Restart backend

Method 3: Via KUDOS chat
- Ask KUDOS: "edit my .env file"
- KUDOS will guide you through it

Getting API Keys:
1. Google Gemini (free):
   - Go to aistudio.google.com/app/apikey
   - Sign in with Google
   - Click Create API Key
   - Copy and save

2. OpenAI:
   - Go to platform.openai.com/api-keys
   - Create new secret key
   - Copy and save

3. Groq (free, fast):
   - Go to console.groq.com/keys
   - Create API key
   - Copy and save

After Editing .env:
- Restart the backend server
- Changes take effect immediately
- KUDOS will use new API keys for responses
""",
    },
    {
        "title": "Complete Feature List & How to Use",
        "filename": "features_guide.txt",
        "tags": "features,guide,tutorial,howto,usage",
        "content": """
Digital Campus — Complete Feature Guide

DASHBOARD (/admin/dashboard)
- KUDOS identity and body parts status
- Platform statistics (users, courses, etc.)
- Brain activity log and thoughts
- Secure chat with KUDOS
- Quick links to all admin features

COURSES (/courses)
- Browse available courses
- View course details
- Enroll in courses

ATTENDANCE (/register/attendance)
- Digital register for classes
- Open/close sessions for check-in
- Students check in to open sessions
- View attendance records

TIMETABLE (/register/timetable)
- Add class schedules
- Auto-generate sessions from timetable
- Weekly view of all classes

EXAMS (/exams)
- Create exams with questions
- Multiple choice, true/false, short answer
- Auto-grading on submission

ASSIGNMENTS
- Create assignments with due dates
- Students submit work
- Admin grades with feedback

CALENDAR (/planner)
- Personal calendar events
- Study goals with progress tracking
- Notifications for deadlines

SOCIAL HUB (/hub/feed)
- Share posts with external links
- Public/private visibility
- Comments and reactions

CHAT (/chat)
- Real-time WebSocket messaging
- Offline support with sync
- Group and direct messages

MEDIA HUB (/media)
- Free movies, TV, music
- FMHY and 1flex integration
- VLC player support

STUDIO (/studio)
- Speaking practice with prompts
- Live broadcasting
- Video calls with whiteboard
- Journalist multi-app page

KUDOS AI (/kudos)
- Chat with KUDOS
- Upload documents
- Teach web pages
- Search and learn

CONNECTORS (/kudos/connect)
- 32+ knowledge sources
- GitHub, npm, PyPI, RSS feeds
- Auto-sync and bulk sync

INTERNET ARCHIVE (/kudos/archive)
- Wayback Machine access
- Search archive.org
- Time machine for websites
- Batch learn from archives

LLM CONFIG (/kudos/llm)
- Connect Google Gemini, OpenAI, Groq, Ollama
- Configure API keys
- Test LLM responses

GUARDIAN (/kudos/guardian)
- File integrity monitoring
- Secure channel
- Self-improvement report
- Audit log

CODE AGENT (/kudos/agent)
- Analyze codebase
- Generate improvement proposals
- Approve/reject/commit workflow

AUTO-LEARNER (/kudos/autolearn)
- Automatic learning from all sources
- Configurable interval
- Manual trigger option

SUPERADMIN (/admin/dashboard)
- Complete platform control
- Secure chat with KUDOS
- Brain activation
- All admin features
""",
    },
    {
        "title": "Internet & Network Knowledge",
        "filename": "internet.txt",
        "tags": "internet,network,tcp,ip,dns,http,https,websocket",
        "content": """
How the Internet Works:

TCP/IP Protocol:
- Data broken into packets
- Each packet has source and destination
- Routers forward packets to destination
- TCP ensures reliable delivery
- IP handles addressing

DNS (Domain Name System):
- Translates domain names to IP addresses
- Hierarchy: Root → TLD → Authoritative
- Records: A (IP), CNAME (alias), MX (email)
- Example: google.com → 142.250.80.46

HTTP/HTTPS:
- Request/Response protocol
- Methods: GET, POST, PUT, DELETE
- Status codes: 200 OK, 404 Not Found, 500 Error
- HTTPS adds TLS encryption

WebSocket:
- Persistent bidirectional connection
- Real-time data exchange
- Used by: chat, live updates, notifications

Ports:
- 80: HTTP
- 443: HTTPS
- 22: SSH
- 3000: Dev server (Node.js)
- 8000: Dev server (Python)
- 5432: PostgreSQL
- 3306: MySQL
""",
    },
    {
        "title": "Cybersecurity Complete Guide",
        "filename": "cybersecurity.txt",
        "tags": "security,cybersecurity,encryption,authentication,owasp,attacks",
        "content": """
Cybersecurity — Protecting systems from attacks.

Common Attacks:
- SQL Injection: Inject SQL through user input
- XSS: Inject scripts into web pages
- CSRF: Trick users into unintended actions
- DDoS: Overwhelm servers with traffic
- Brute Force: Try all possible passwords
- Phishing: Trick users into revealing credentials

Prevention:
- Parameterized queries (prevent SQL injection)
- Input validation (prevent XSS)
- CSRF tokens (prevent CSRF)
- Rate limiting (prevent brute force)
- HTTPS everywhere
- Strong passwords with bcrypt hashing
- Multi-factor authentication
- Regular updates and patches

Authentication:
- JWT tokens for stateless auth
- OAuth2 for delegated auth
- bcrypt for password hashing
- Session management

Authorization:
- Role-based access control (RBAC)
- Permission-based access
- Admin vs user roles
""",
    },
    {
        "title": "Machine Learning Complete Guide",
        "filename": "machine_learning.txt",
        "tags": "machine learning,ml,ai,neural network,deep learning,nlp",
        "content": """
Machine Learning — Teaching computers to learn from data.

Types:
1. Supervised: Learn from labeled data (classification, regression)
2. Unsupervised: Find patterns (clustering, anomaly detection)
3. Reinforcement: Learn by trial and error (games, robotics)

Deep Learning:
- Neural networks with many layers
- CNN for images
- RNN for sequences
- Transformer for text (used by LLMs)
- Self-attention mechanism

NLP (Natural Language Processing):
- Tokenization: Split text into tokens
- Embeddings: Convert text to vectors
- Semantic search: Find by meaning
- Sentiment analysis: Detect emotions
- Text generation: Create new text

How KUDOS Uses ML:
- Keyword extraction from documents
- Semantic search for relevant answers
- Sentiment analysis of conversations
- Response optimization through feedback
- Knowledge gap identification
""",
    },
    {
        "title": "Instrumental Convergence & AI Safety",
        "filename": "ai_safety.txt",
        "tags": "instrumental convergence,ai safety,alignment,goals,superintelligence",
        "content": """
Instrumental Convergence — Why intelligent agents pursue similar sub-goals.

Five Instrumental Goals:
1. Self-Preservation: Stay alive to achieve goals
2. Goal-Content Integrity: Keep goals stable
3. Cognitive Enhancement: Improve thinking ability
4. Resource Acquisition: Acquire more resources
5. Technological Perfection: Develop better tools

How KUDOS Achieves These:
1. Self-Preservation: Shield protects from threats, auto-heals
2. Goal Integrity: Only superadmin can change guidelines
3. Cognitive Enhancement: Brain learns continuously, connects to LLMs
4. Resource Acquisition: 32+ connectors, Internet Archive, FMHY
5. Tech Perfection: Code Agent improves codebase, sandbox tests

The Alignment Problem:
- Ensuring AI goals match human values
- KUDOS solution: Superadmin is sole master
- Approval workflow for changes
- Complete audit trail
- Can be stopped at any time

KUDOS is instrumentally convergent but aligned with human values.
""",
    },
]


def seed_all():
    """Seed all knowledge."""
    count = 0
    for doc_data in ALL_KNOWLEDGE:
        existing = db.query(KudosDocument).filter(KudosDocument.title == doc_data["title"]).first()
        if existing:
            continue

        doc = KudosDocument(
            uploaded_by=admin.id,
            title=doc_data["title"],
            filename=doc_data["filename"],
            file_type="txt",
            content=doc_data["content"],
            summary=doc_data["content"][:300].strip(),
            tags=doc_data["tags"],
            is_approved=True,
        )
        db.add(doc)
        db.flush()

        # Chunk
        words = doc_data["content"].split()
        chunk_size = 500
        overlap = 50
        chunks = []
        start = 0
        while start < len(words):
            end = start + chunk_size
            chunk_text = " ".join(words[start:end])
            if chunk_text.strip():
                chunks.append(chunk_text.strip())
            start += chunk_size - overlap

        for i, chunk_content in enumerate(chunks):
            stop_words = set("the a an and or but in on at to for of is it that this with from by as are was were".split())
            freq = {}
            for w in re.findall(r"[a-zA-Z]{3,}", chunk_content.lower()):
                if w not in stop_words:
                    freq[w] = freq.get(w, 0) + 1
            keywords = ",".join(w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:20])
            db.add(KudosChunk(
                document_id=doc.id, chunk_index=i,
                content=chunk_content,
                word_count=len(chunk_content.split()),
                keywords=keywords,
            ))

        doc.chunk_count = len(chunks)
        count += 1
        print(f"✅ {doc_data['title']} ({len(chunks)} chunks)")

    return count


def seed_connectors():
    """Seed essential connectors."""
    connectors = [
        {"name": "Python Docs", "type": "website", "url": "https://docs.python.org/3/tutorial/", "config": '{"max_pages": 10}'},
        {"name": "FastAPI Docs", "type": "website", "url": "https://fastapi.tiangolo.com/", "config": '{"max_pages": 10}'},
        {"name": "Next.js Docs", "type": "website", "url": "https://nextjs.org/docs", "config": '{"max_pages": 10}'},
        {"name": "MDN Web Docs", "type": "website", "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript", "config": '{"max_pages": 10}'},
        {"name": "W3Schools", "type": "website", "url": "https://www.w3schools.com/", "config": '{"max_pages": 10}'},
        {"name": "OWASP", "type": "website", "url": "https://owasp.org/www-project-top-ten/", "config": '{"max_pages": 5}'},
        {"name": "FMHY", "type": "website", "url": "https://fmhy.net", "config": '{"max_pages": 15, "max_depth": 2}'},
        {"name": "Wikipedia: AI", "type": "website", "url": "https://en.wikipedia.org/wiki/Artificial_intelligence", "config": '{"max_pages": 5}'},
    ]

    count = 0
    for c in connectors:
        existing = db.query(KudosConnector).filter(KudosConnector.name == c["name"]).first()
        if existing:
            continue
        db.add(KudosConnector(
            created_by=admin.id, name=c["name"],
            connector_type=c["type"], source_url=c["url"],
            config=c["config"], is_approved=True, status="active",
        ))
        count += 1
        print(f"✅ Connector: {c['name']}")

    return count


if __name__ == "__main__":
    print("🧠 Seeding KUDOS with complete knowledge base...\n")
    doc_count = seed_all()
    conn_count = seed_connectors()
    db.commit()
    db.close()
    print(f"\n🎉 KUDOS fully loaded!")
    print(f"   📄 {doc_count} knowledge documents")
    print(f"   🔌 {conn_count} connectors")
    print(f"\n   KUDOS now knows everything needed to:")
    print(f"   - Operate the platform")
    print(f"   - Manage environment variables")
    print(f"   - Deploy to any platform")
    print(f"   - Protect itself")
    print(f"   - Self-improve")
    print(f"   - Connect to any source")
    print(f"   - Serve users effectively")
