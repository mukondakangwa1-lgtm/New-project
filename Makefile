# =============================================
# Digital Campus - Makefile (Hybrid DB)
# =============================================
.PHONY: help backend frontend dev install lint test clean setup-sqlite setup-postgres db-check db-init switch-sqlite switch-postgres

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --------------- Install ---------------
install: ## Install all dependencies (backend + frontend)
	cd services/backend && python3 -m venv .venv && \
		.venv/bin/pip install -r requirements.txt
	cd frontend && npm install

# --------------- Database (Hybrid) ---------------
setup-sqlite: ## One-command SQLite setup (laptop) — creates file + seed + check
	cd services/backend && python scripts/switch_db.py sqlite --apply && .venv/bin/python scripts/init_db.py --seed && .venv/bin/python scripts/db_check.py

setup-postgres: ## One-command Postgres setup — needs running Postgres or Docker
	cd services/backend && python scripts/switch_db.py postgres --apply && .venv/bin/python scripts/init_db.py --seed && .venv/bin/python scripts/db_check.py

db-check: ## Check current DB connection (Postgres or SQLite)
	cd services/backend && .venv/bin/python scripts/db_check.py

db-init: ## Init DB tables for current DATABASE_URL (no seed)
	cd services/backend && .venv/bin/python scripts/init_db.py

db-init-seed: ## Init + seed superadmin
	cd services/backend && .venv/bin/python scripts/init_db.py --seed

switch-sqlite: ## Switch .env to SQLite
	cd services/backend && python scripts/switch_db.py sqlite --apply

switch-postgres: ## Switch .env to PostgreSQL
	cd services/backend && python scripts/switch_db.py postgres --apply

# Postgres helpers
postgres-create: ## Create Postgres DB/user (needs psql)
	@echo "Creating Postgres user/db..."
	psql -U postgres -c "CREATE USER dc_user WITH PASSWORD 'dc_pass';" || true
	psql -U postgres -c "CREATE DATABASE digital_campus OWNER dc_user;" || true
	psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE digital_campus TO dc_user;" || true
	psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;" -d digital_campus || true

# --------------- Dev servers ---------------
backend: ## Start backend dev server (uses current DATABASE_URL)
	cd services/backend && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend: ## Start frontend dev server
	cd frontend && npm run dev

dev: ## Start both backend + frontend
	@echo "Starting frontend on :3000 (background)..."
	cd frontend && npm run dev &
	@echo "Starting backend on :8000 (foreground)..."
	cd services/backend && .venv/bin/uvicorn app.main:app --reload --port 8000

docker-up: ## Start Postgres + Redis via Docker
	docker-compose up -d db redis

docker-down: ## Stop Docker services
	docker-compose down

# --------------- Lint & Test ---------------
lint: ## Lint backend (ruff) and frontend (eslint)
	cd services/backend && .venv/bin/ruff check app/
	cd frontend && npm run lint || true

test: ## Run backend tests (uses SQLite test.db)
	cd services/backend && .venv/bin/pytest tests/ -v

# --------------- Clean ---------------
clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf services/backend/.venv frontend/.next frontend/node_modules
	rm -f services/backend/*.db services/backend/*.db-* services/backend/test.db
