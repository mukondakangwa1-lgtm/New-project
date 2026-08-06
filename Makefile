# =============================================
# Digital Campus - Makefile
# =============================================
.PHONY: help backend frontend dev install lint test clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --------------- Install ---------------
install: ## Install all dependencies (backend + frontend)
	cd services/backend && python3 -m venv .venv && \
		.venv/bin/pip install -r requirements.txt
	cd frontend && npm install

# --------------- Dev servers ---------------
backend: ## Start backend dev server
	cd services/backend && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend: ## Start frontend dev server
	cd frontend && npm run dev

dev: ## Start both backend + frontend (foreground: backend, background: frontend)
	@echo "Starting frontend on :3000 (background)..."
	cd frontend && npm run dev &
	@echo "Starting backend on :8000 (foreground)..."
	cd services/backend && .venv/bin/uvicorn app.main:app --reload --port 8000

# --------------- Lint & Test ---------------
lint: ## Lint backend (ruff) and frontend (eslint)
	cd services/backend && .venv/bin/ruff check app/
	cd frontend && npm run lint || true

test: ## Run backend tests
	cd services/backend && .venv/bin/pytest tests/ -v

# --------------- Clean ---------------
clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf services/backend/.venv frontend/.next frontend/node_modules
