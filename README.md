# 🎓 Digital Campus

**Unified university platform powered by KUDOS AI — a self-learning, self-protecting AI assistant.**

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue)
![pgvector](https://img.shields.io/badge/pgvector-embeddings-blue)
![Redis](https://img.shields.io/badge/Redis-7-red)
![Celery](https://img.shields.io/badge/Celery-async_jobs-green)
![CI](https://img.shields.io/badge/CI-GitHub_Actions-green)
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
- **Semantic Search** — Optional pgvector embeddings with OpenAI text-embedding models
- **Internet Archive** — Access 25+ years of web history
- **Search Engines** — DuckDuckGo, Wikipedia, Reddit integration
- **LLM Integration** — Google Gemini, OpenAI, Groq, Ollama support (provider-neutral adapter)
- **Model Context Protocol** — Private MCP gateway exposing KUDOS tools over Streamable HTTP
- **Arena AI** — Multi-source query with best answer selection
- **Conversational** — Empathetic, context-aware, follows conversation
- **Self-Improvement** — Autonomous learning, knowledge gap detection
- **Background Tasks** — Celery workers for connector syncs and long-running jobs

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
├── services/backend/            # FastAPI + SQLAlchemy + Celery
│   ├── app/
│   │   ├── api/v1/endpoints/    # API endpoints (28 modules)
│   │   ├── core/                # Core systems
│   │   │   ├── arena_engine.py  # Multi-source AI query
│   │   │   ├── auto_learner.py  # Autonomous learning
│   │   │   ├── code_agent.py    # Code improvement agent
│   │   │   ├── conversation_engine.py  # Human-like responses
│   │   │   ├── embeddings.py    # Embedding provider abstraction
│   │   │   ├── vector_store.py  # Optional pgvector semantic storage
│   │   │   ├── kudos_brain.py   # Autonomous thinking
│   │   │   ├── kudos_guardian.py # File integrity
│   │   │   ├── kudos_identity.py # KUDOS identity system
│   │   │   ├── kudos_shield.py  # Self-protection
│   │   │   ├── llm_adapter.py   # Provider-neutral LLM adapter
│   │   │   └── llm_engine.py    # LLM integration
│   │   ├── celery_app.py        # Celery app (Redis broker)
│   │   ├── tasks.py             # Background tasks (connector sync, learning)
│   │   ├── mcp_server.py        # MCP Streamable HTTP gateway
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── models_extended.py   # Extended models
│   │   └── schemas/             # Pydantic schemas
│   ├── alembic/                 # Database migrations (Alembic)
│   │   └── versions/            # Initial schema + studio tables
│   ├── initdb/pgvector.sql      # Postgres init: CREATE EXTENSION vector
│   ├── tests/                   # Pytest test suite (77 tests)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-dev.txt     # Pinned: ruff, black, pytest, pytest-asyncio
│   ├── seed.py                  # Creates the superadmin account only
│   └── seed_kudos.py            # KUDOS knowledge seeder
│
├── .github/workflows/ci.yml     # CI: backend pytest+ruff, frontend build, migrations
├── deploy.env.example           # Prod compose secrets template
├── docker-compose.yml           # Dev stack: backend, frontend, pgvector db, redis, worker
├── docker-compose.prod.yml      # Prod stack: + private mcp service
├── CONTRIBUTING.md
├── Makefile
└── README.md
```

---

## 🛠️ Quick Start

The recommended development path is the Docker Compose stack, which matches
production: PostgreSQL (with pgvector), Redis, Celery workers, backend and
frontend all start with one command.

### Option A — Docker Compose (recommended)

Prerequisites: Docker + Docker Compose v2.

```bash
cp deploy.env.example .env          # for prod only — not needed for dev
docker compose up -d --build
```

The stack starts `backend`, `frontend`, `db` (pgvector/pgvector:pg15), `redis`,
and `worker` (Celery). Apply migrations, then seed the superadmin:

```bash
docker compose exec backend python -m alembic upgrade head
docker compose exec backend python seed.py
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000 (Swagger at http://localhost:8000/docs)
- Postgres: localhost:5432 (`dc_user` / `dc_pass`, database `digital_campus`)
- Redis: localhost:6379

### Option B — Local (no Docker)

Prerequisites:
- Python 3.11+
- Node.js 18+
- Git

```bash
git clone git@github.com:mukondakangwa1-lgtm/New-project.git
cd New-project

# Backend
cd services/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env                # edit values; for local dev you may use SQLite:
#   DATABASE_URL=sqlite:///./digital_campus.db   (AUTO_CREATE_TABLES=true for throwaway DBs)
#   DATABASE_URL=postgresql://dc_user:dc_pass@localhost:5432/digital_campus

# Apply migrations (or set AUTO_CREATE_TABLES=true for a throwaway SQLite DB)
.venv/bin/python -m alembic upgrade head
.venv/bin/python seed.py            # creates the superadmin account only
.venv/bin/python seed_kudos.py      # optional KUDOS knowledge seeder

# Frontend
cd ../../frontend
npm install
```

### 2. Run

**Terminal 1 (Backend):**
```bash
cd services/backend
.venv/bin/uvicorn app.main:app --reload --port 8000
```

**Terminal 2 (Frontend):**
```bash
cd frontend
npm run dev
```

**Terminal 3 (optional — Celery worker):**
```bash
cd services/backend
.venv/bin/celery -A app.celery_app.celery worker --loglevel=info
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
LAN/VPS Compose file. Commands below use the Compose v2 syntax (`docker
compose`); on older systems without the v2 plugin, replace `docker compose`
with the legacy `docker-compose` spelling.

### Development

```bash
docker compose up -d --build
```

The stack starts five services: `backend`, `frontend`, `db`
(`pgvector/pgvector:pg15` — PostgreSQL with the vector extension),
`redis`, and `worker` (Celery with the Redis broker). The frontend is
available at http://localhost:3000 and the backend at http://localhost:8000.
The frontend uses a server-side rewrite, so browser requests stay same-origin
and never depend on a browser-visible localhost API.

Apply migrations before first use:

```bash
docker compose exec backend python -m alembic upgrade head
docker compose exec backend python seed.py
```

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
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d db redis
```

3. Apply migrations on a new database, then start the application:

```bash
docker compose -f docker-compose.prod.yml run --rm backend python -m alembic upgrade head
docker compose -f docker-compose.prod.yml up -d backend worker frontend
```

The LAN frontend is available at `http://SERVER_IP:3000`. The backend is bound
to host loopback and is reached by the frontend over the internal Compose
network. Postgres and Redis are not published to the host in the production
file.

If the database already contains tables created by the old startup code, take
a backup first and mark it at the initial migration instead of running the
create-table migration against existing tables:

```bash
docker compose -f docker-compose.prod.yml run --rm backend \
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
| `/api/v1/health` | Health check |
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
| `/api/v1/tools` | Embed & sandbox |
| `/api/v1/media` | Media hub |
| `/api/v1/admin/analytics` | Analytics |
| `/mcp` | MCP Streamable HTTP endpoint (prod `mcp` service, token auth) |

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                        │
│   Pages │ Components │ API Proxy │ WebSocket │ PWA            │
└───────────────────────┬──────────────────────────────────────┘
                        │ HTTP / WebSocket
┌───────────────────────┴──────────────────────────────────────┐
│                     Backend (FastAPI)                          │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐ │
│  │  Auth   │  │  KUDOS   │  │  Studio  │  │  MCP Gateway   │ │
│  └────┬────┘  └────┬─────┘  └────┬─────┘  └───────┬────────┘ │
│       │            │             │                 │          │
│  ┌────┴────────────┴─────────────┴──────────────┐  │          │
│  │                Core Systems                  │  │          │
│  │ Brain │ Shield │ Guardian │ Identity │ Arena │  │          │
│  └───────────────┬──────────────────────────────┘  │          │
│                  │ Celery workers (sync, learning) │          │
│  ┌───────────────┴──────────────────────────┐  ┌───┴────────┐ │
│  │        PostgreSQL 15 + pgvector          │  │   Redis    │ │
│  │  Users │ Courses │ KUDOS │ Chat │ Social │  │  broker +  │ │
│  │  embeddings (vector) │ migrations (Alembic) │   cache    │ │
│  └──────────────────────────────────────────┘  └────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

- **Database** — PostgreSQL 15 with the `vector` extension (pgvector) for
  semantic embeddings; SQLite remains a supported dev fallback via
  `DATABASE_URL`.
- **Migrations** — Alembic versioned schema (`services/backend/alembic`);
  applied with `python -m alembic upgrade head`.
- **Async jobs** — Celery with Redis broker: connector syncs, knowledge
  learning, and other long-running work (`app/celery_app.py`, `app/tasks.py`).
- **MCP** — the private `mcp` service (prod Compose) exposes KUDOS tools over
  Streamable HTTP; the backend consumes them via `app/core/mcp_client.py`.

---

## 🔒 Security

- **JWT Authentication** — Stateless, scalable
- **bcrypt Password Hashing** — Industry standard
- **CORS Protection** — Configurable origins
- **Rate Limiting** — Shield middleware: 100 requests/minute per IP, blocking
- **File Integrity** — SHA-256 monitoring
- **Intrusion Detection** — Brute force protection
- **Auto-Backup** — Hourly knowledge backups (Shield)
- **Self-Healing** — Auto-recovery from errors
- **Fail-fast configuration** — `APP_ENV=production` refuses to start with a
  default `SECRET_KEY` or with `DEBUG=true`
- **Correlation IDs** — every response and error carries an `X-Request-ID`;
  all logs include it for end-to-end tracing

## 📊 Operations

### Health & readiness

- `GET /api/v1/health` — liveness
- `GET /api/v1/health/ready` — database round-trip latency, Redis state;
  returns `503` when the database is unreachable

### Metrics

`GET /api/v1/admin/metrics` (superadmin only) reports host stats (CPU load,
memory, disk), database latency, Redis state, request counters, and Shield
(blocked IPs, performance, threat log) — no external tooling required.

### Logging

All requests are logged with method, path, status, duration and a
`request_id`, with a single uniform format on stdout.

### Database backups

PostgreSQL dumps via `pg_dump` (custom format), with automatic pruning:

```bash
make backup                     # dump to backups/ < TIMESTAMP >.dump
make backup-restore FILE=backups/digital_campus_20260101_120000.dump
make backup-prune               # keep newest BACKUP_KEEP (default 14)
```

In Docker:

```bash
docker compose exec backend python -m app.core.backup dump
```

---

## 🧪 Testing

```bash
cd services/backend
.venv/bin/python -m pytest tests/ -v
```

77 tests covering:
- Health, readiness, metrics, correlation IDs, error envelopes, fail-fast config
- Authentication, user management, course CRUD, authorization
- Academic: assignments, grades, exams, planner, timetable, community
- Studio: speaking sessions, broadcasts, video calls, journal blocks
- KUDOS: documents, connectors, web knowledge, sync tasks, embeddings
- MCP: HTTP auth middleware, tool registration, mutation guard, DB-backed tools,
  and end-to-end tests against a live uvicorn subprocess via the real client
- Backup helpers: filename format, pruning policy, PostgreSQL-only guard

Frontend typecheck (`npx tsc --noEmit`) and production build (`npm run build`)
are part of the same gates.

### CI (GitHub Actions)

`.github/workflows/ci.yml` runs on every push/PR:
- **Backend** — `ruff check --select F` (pyflakes) + full pytest suite
- **Frontend** — TypeScript typecheck + Next.js production build
- **Migration** — `alembic upgrade head` on a fresh SQLite database and
  verifies the expected tables exist

## 📦 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 14, React 18, TypeScript, Tailwind CSS |
| **Backend** | FastAPI, Python 3.11+, SQLAlchemy, Pydantic |
| **Database** | PostgreSQL 15 + pgvector (primary), SQLite dev fallback |
| **Migrations** | Alembic versioned schema |
| **Async jobs** | Celery with Redis broker (7.x) |
| **Vector search** | pgvector with OpenAI text-embedding models (optional) |
| **AI** | Google Gemini, OpenAI, Groq, Ollama via provider-neutral adapter |
| **MCP** | MCP Python SDK, Streamable HTTP gateway, token auth |
| **Real-time** | WebSocket (chat), SSE (notifications) |
| **Testing** | Pytest (77 tests), pytest-asyncio, FastAPI TestClient, ruff |
| **CI** | GitHub Actions (backend, frontend, migrations) |
| **Deployment** | Docker, Docker Compose (dev + prod stacks) |

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
