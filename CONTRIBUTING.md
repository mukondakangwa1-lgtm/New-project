# Digital Campus — Contributing Guide

Monorepo for the Digital Campus platform: a Next.js frontend and a FastAPI
backend, running on PostgreSQL (pgvector), Redis and Celery, with the KUDOS AI
assistant, MCP gateway, and CI via GitHub Actions.

## Prerequisites

- Python 3.11+
- Node.js 18+
- Git
- Docker + Docker Compose v2 (recommended)

## Project Structure

```
New-project/
├── frontend/                    # Next.js 14 + TypeScript + Tailwind CSS
│   ├── components/              # Reusable UI components
│   ├── pages/                   # Next.js pages (file-based routing)
│   └── styles/                  # CSS / Tailwind styles
├── services/backend/            # FastAPI + SQLAlchemy + Celery
│   ├── app/
│   │   ├── api/v1/endpoints/    # API route handlers
│   │   ├── core/                # Config, security, LLM adapter, KUDOS systems
│   │   ├── schemas/             # Pydantic models
│   │   ├── celery_app.py        # Celery app (Redis broker)
│   │   ├── tasks.py             # Background tasks
│   │   ├── mcp_server.py        # MCP Streamable HTTP gateway
│   │   ├── models.py / models_extended.py
│   │   └── main.py              # FastAPI entry point
│   ├── alembic/                 # Database migrations
│   ├── initdb/                  # Postgres init SQL (pgvector extension)
│   ├── tests/                   # Pytest suite (59 tests)
│   └── requirements.txt / requirements-dev.txt
├── .github/workflows/ci.yml     # CI pipeline
├── deploy.env.example           # Prod compose secrets template
├── docker-compose.yml           # Dev stack (backend, frontend, db, redis, worker)
├── docker-compose.prod.yml      # Prod stack (+ private mcp service)
├── CONTRIBUTING.md
├── Makefile
└── README.md
```

## Development Setup

Recommended: start the full stack with Docker.

```bash
docker compose up -d --build
docker compose exec backend python -m alembic upgrade head
docker compose exec backend python seed.py   # creates the superadmin account
```

Alternative local setup (SQLite dev fallback or a local Postgres):

```bash
cd services/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env              # edit values; SQLite is fine for throwaway dev
.venv/bin/python -m alembic upgrade head
.venv/bin/python seed.py
.venv/bin/uvicorn app.main:app --reload --port 8000

cd ../../frontend
npm install
npm run dev
```

## Conventions

- **Backend:** FastAPI + SQLAlchemy; Pydantic schemas in `app/schemas`; models
  in `app/models.py` / `app/models_extended.py`; routes under
  `app/api/v1/endpoints`.
- **Schema changes:** add a migration (`python -m alembic revision
  --autogenerate -m "..."`), review it, and run `alembic upgrade head`.
- **Secrets:** never commit `.env` files or API keys. Use
  `services/backend/.env.example` and `deploy.env.example` as templates.

## Quality Gates

Before pushing, run:

```bash
# Backend
cd services/backend
.venv/bin/ruff check app/ tests/ --select F
.venv/bin/python -m pytest tests/ -q

# Frontend
cd frontend
npx tsc --noEmit
npm run build
```

The CI pipeline (`.github/workflows/ci.yml`) enforces all of these on every
push/PR, plus an Alembic migration check against a fresh database.

## Useful Make Targets

```bash
make dev          # start backend (foreground) + frontend (background)
make test         # run backend tests
make lint         # ruff + eslint
make docker-dev   # build and start the dev Compose stack
make docker-prod-migrate   # apply migrations to the prod database
```
