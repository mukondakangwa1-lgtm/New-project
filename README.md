# 🎓 Digital Campus

**Unified university platform powered by KUDOS AI — a self-learning, self-protecting AI assistant.**

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 🚀 Features

### Core Platform
- **Course Management** — Create, enroll, track progress
- **Attendance System** — Digital register with timetable, auto-sessions, bulk generation
- **Assignments & Grades** — Submit, grade, feedback, grade dashboard
- **Exams & Quizzes** — Create exams with MC/T/F/short-answer, auto-grading
- **Study Groups & Forums** — Collaborative learning, course discussions
- **Calendar & Goals** — Personal schedule, study goals, notifications

### 🧠 KUDOS AI Assistant
- **Knowledge Learning** — Upload documents, teach web pages, connect 32+ sources
- **Internet Archive** — Access 25+ years of web history
- **Search Engines** — DuckDuckGo, Wikipedia, Reddit integration
- **LLM Integration** — Google Gemini, OpenAI, Groq, Ollama support
- **Arena AI** — Multi-source query with best answer selection
- **Conversational** — Empathetic, context-aware, follows conversation
- **Self-Improvement** — Autonomous learning, knowledge gap detection

### 🛡️ KUDOS Guardian
- **File Integrity** — SHA-256 monitoring of critical files
- **Intrusion Detection** — Brute force protection, rate limiting
- **Self-Healing** — Auto-recovery from errors
- **Backup System** — Hourly auto-backups, restore capability
- **Performance Monitoring** — Response time tracking

### 🔌 Connectors (32+ Sources)
- **Code Repos** — GitHub, GitLab (README, code, issues)
- **Package Registries** — npm, PyPI
- **Documentation** — Python, FastAPI, React, Next.js, MDN
- **Knowledge** — Wikipedia, W3Schools
- **RSS Feeds** — Hacker News, Python Blog, GitHub Trending
- **Social** — Reddit, social skills, emotional intelligence

### 🎙️ Studio
- **Speaking Practice** — 4 difficulty levels, timer, self-rating
- **Live Broadcasting** — Radio-style broadcasts with Radio Garden
- **Video Calls** — P2P & group calls with canvas whiteboard
- **Journalist Page** — Multi-platform dashboard (embed YouTube, Twitter, etc.)

### 💬 Communication
- **Real-time Chat** — WebSocket-based, offline support
- **Social Hub** — Posts, comments, reactions, external storage links
- **Notifications** — Assignment grades, attendance, messages

---

## 📁 Project Structure

```
New-project/
├── frontend/                    # Next.js 14 + TypeScript + Tailwind CSS
│   ├── pages/                   # File-based routing
│   │   ├── index.tsx            # Home page
│   │   ├── courses.tsx          # Course browser
│   │   ├── dashboard.tsx        # User dashboard
│   │   ├── login.tsx            # Authentication
│   │   ├── register.tsx         # User registration
│   │   ├── chat/index.tsx       # Real-time chat
│   │   ├── studio/              # Speaking, broadcast, video calls
│   │   ├── kudos/               # KUDOS AI pages
│   │   │   ├── index.tsx        # KUDOS chat
│   │   │   ├── connect.tsx      # Connectors management
│   │   │   ├── guardian.tsx     # Security dashboard
│   │   │   ├── agent.tsx        # Code agent
│   │   │   ├── archive.tsx      # Internet Archive
│   │   │   ├── autolearn.tsx    # Auto-learner dashboard
│   │   │   └── llm.tsx          # LLM configuration
│   │   ├── admin/               # Admin pages
│   │   │   └── dashboard.tsx    # Superadmin dashboard
│   │   └── register/            # Attendance pages
│   ├── components/              # Reusable components
│   └── styles/                  # CSS
│
├── services/backend/            # FastAPI + SQLAlchemy
│   ├── app/
│   │   ├── api/v1/endpoints/    # API endpoints (20+ modules)
│   │   ├── core/                # Core systems
│   │   │   ├── arena_engine.py  # Multi-source AI query
│   │   │   ├── auto_learner.py  # Autonomous learning
│   │   │   ├── code_agent.py    # Code improvement agent
│   │   │   ├── conversation_engine.py  # Human-like responses
│   │   │   ├── kudos_brain.py   # Autonomous thinking
│   │   │   ├── kudos_guardian.py # File integrity
│   │   │   ├── kudos_identity.py # KUDOS identity system
│   │   │   ├── kudos_shield.py  # Self-protection
│   │   │   └── llm_engine.py    # LLM integration
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── models_extended.py   # Extended models
│   │   └── schemas/             # Pydantic schemas
│   ├── tests/                   # Pytest test suite
│   ├── seed.py                  # Database seeder (superadmin only)
│   └── seed_kudos.py            # KUDOS knowledge seeder
│
├── .gitignore
├── docker-compose.yml
├── Makefile
└── README.md
```

---

## 🛠️ Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Git

### 1. Clone & Setup

```bash
git clone git@github.com:mukondakangwa1-lgtm/New-project.git
cd New-project

# Backend
cd services/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Initialize database
.venv/bin/python seed.py
.venv/bin/python seed_kudos.py

# Frontend
cd ../../frontend
npm install
```

### 2. Run

**Terminal 1 (Backend):**
```bash
cd ~/New-project/services/backend
.venv/bin/uvicorn app.main:app --reload --port 8000
```

**Terminal 2 (Frontend):**
```bash
cd ~/New-project/frontend
npm run dev
```

Open **http://localhost:3000**

### 3. Login

| Email | Password |
|-------|----------|
| `admin@campus.edu` | `superadmin123` |

⚠️ **Change password immediately** via Superadmin Dashboard → Chat → `change password YOUR_NEW_PASSWORD`

---

## 🐳 Docker

The repository includes a development Compose file and a production-style
LAN/VPS Compose file. This project currently uses the legacy command spelling
`docker-compose` on systems without the Compose v2 plugin.

### Development

```bash
docker-compose up -d --build
```

The frontend is available at http://localhost:3000 and the backend at
http://localhost:8000. The frontend uses a server-side rewrite, so browser
requests stay same-origin and never depend on a browser-visible localhost API.

### LAN/VPS deployment

1. Create the ignored deployment and backend environment files and replace
   every development secret/value:

```bash
cp deploy.env.example .env
cp services/backend/.env.example services/backend/.env
# Edit both files. Use the same Postgres values in .env and services/backend/.env
```

`docker-compose.prod.yml` builds the internal `DATABASE_URL` from the root
`.env` values. Configure `LLM_PROVIDER` plus at least one supported provider
key in `services/backend/.env`. API keys belong in the server environment or a
secret manager; do not commit or paste them into chat.

2. Build and start the data services:

```bash
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d db redis
```

3. Apply migrations on a new database, then start the application:

```bash
docker-compose -f docker-compose.prod.yml run --rm backend python -m alembic upgrade head
docker-compose -f docker-compose.prod.yml up -d backend worker frontend
```

The LAN frontend is available at `http://SERVER_IP:3000`. The backend is bound
to host loopback and is reached by the frontend over the internal Compose
network. Postgres and Redis are not published to the host in the production
file.

If the database already contains tables created by the old startup code, take
a backup first and mark it at the initial migration instead of running the
create-table migration against existing tables:

```bash
docker-compose -f docker-compose.prod.yml run --rm backend \
  python -m alembic stamp 39101dd01b2e
```

The Arena.ai agent helping develop this repository is not a runtime API endpoint
that can be embedded into the deployed application. KUDOS uses a provider-
neutral adapter; configure Gemini, OpenAI, Groq, or an Ollama server through
`services/backend/.env`.

### Model Context Protocol (MCP)

KUDOS can connect to its tools through the official MCP Python SDK. The
production Compose file includes a private `mcp` service exposing Streamable
HTTP tools for:

- approved document and web-knowledge search;
- web and Wikipedia search;
- connector status and database health;
- optionally queued connector syncs when mutations are explicitly enabled.

The MCP service is not published to the LAN. Backend-to-MCP calls use the
shared `MCP_AUTH_TOKEN`, and mutating tools are disabled by default. Add a
random token to `services/backend/.env`, then start the production stack; the
backend uses `MCP_ENABLED=true` and `MCP_URL=http://mcp:8765/mcp` in the
production Compose definition.

---

## 📡 API Documentation

After starting the backend, visit:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### API Endpoints

| Prefix | Description |
|--------|-------------|
| `/api/v1/auth` | Authentication (register, login, token) |
| `/api/v1/users` | User management |
| `/api/v1/courses` | Course CRUD |
| `/api/v1/register` | Attendance & timetable |
| `/api/v1/academic` | Assignments & grades |
| `/api/v1/exams` | Exams & quizzes |
| `/api/v1/groups` | Study groups & forums |
| `/api/v1/planner` | Calendar & goals |
| `/api/v1/social` | Social hub |
| `/api/v1/chat` | Real-time chat (WebSocket) |
| `/api/v1/kudos` | KUDOS AI (ask, learn, upload) |
| `/api/v1/kudos/connectors` | 32+ knowledge connectors |
| `/api/v1/kudos/arena` | Multi-source AI query |
| `/api/v1/kudos/archive` | Internet Archive |
| `/api/v1/kudos/agent` | Code improvement agent |
| `/api/v1/kudos/learn` | Auto-learner |
| `/api/v1/kudos/llm` | LLM configuration |
| `/api/v1/kudos/search` | Search & social learning |
| `/api/v1/kudos/social` | Social learning |
| `/api/v1/kudos/guardian` | Security & integrity |
| `/api/v1/studio` | Speaking, broadcast, video calls |
| `/api/v1/superadmin` | Superadmin dashboard |
| `/api/v1/root` | Root terminal |
| `/api/v1/shield` | Self-protection |
| `/api/v1/admin/analytics` | Analytics |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                     │
│  Pages │ Components │ API Proxy │ WebSocket │ PWA        │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP / WebSocket
┌───────────────────────┴─────────────────────────────────┐
│                   Backend (FastAPI)                       │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │  Auth   │  │  KUDOS   │  │  Studio  │  │  Admin   │ │
│  └────┬────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │
│       │            │             │              │        │
│  ┌────┴────────────┴─────────────┴──────────────┴─────┐ │
│  │              Core Systems                           │ │
│  │  Brain │ Shield │ Guardian │ Identity │ Arena       │ │
│  └────────────────────────┬───────────────────────────┘ │
│                           │                              │
│  ┌────────────────────────┴───────────────────────────┐ │
│  │              Database (SQLAlchemy + SQLite)          │ │
│  │  Users │ Courses │ KUDOS │ Chat │ Social │ Studio   │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## 🔒 Security

- **JWT Authentication** — Stateless, scalable
- **bcrypt Password Hashing** — Industry standard
- **CORS Protection** — Configurable origins
- **Rate Limiting** — 100 requests/minute per IP
- **File Integrity** — SHA-256 monitoring
- **Intrusion Detection** — Brute force protection
- **Auto-Backup** — Hourly knowledge backups
- **Self-Healing** — Auto-recovery from errors

---

## 🧪 Testing

```bash
cd services/backend
.venv/bin/python -m pytest tests/ -v
```

14 tests covering:
- Health endpoints
- Authentication
- User management
- Course CRUD
- Authorization

---

## 📦 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 14, React 18, TypeScript, Tailwind CSS |
| **Backend** | FastAPI, Python 3.11+, SQLAlchemy, Pydantic |
| **Database** | SQLite (dev), PostgreSQL (production) |
| **Real-time** | WebSocket (chat), SSE (notifications) |
| **AI** | Google Gemini, OpenAI, Groq, Ollama, custom engine |
| **Deployment** | Docker, Docker Compose |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- Built with ❤️ for Digital Campus
- Powered by KUDOS AI — Knowledge Unified Digital Operating System
- Connected to the entire internet via 32+ connectors and Internet Archive

---

**KUDOS Motto:** *"Learn everything. Help everyone. Improve always."*
