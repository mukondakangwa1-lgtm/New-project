#!/usr/bin/env bash
# Digital Campus — One-command setup (Linux/macOS)
# Usage:  bash setup.sh           # interactive
#         bash setup.sh sqlite     # auto SQLite
#         bash setup.sh postgres   # auto Postgres (needs running Postgres)
set -e
MODE="${1:-}"

echo "========================================"
echo "  Digital Campus — Setup"
echo "========================================"

# 1. Check Python
if ! command -v python3 &>/dev/null; then
  echo "❌ python3 not found — install Python 3.11+"
  exit 1
fi
echo "✅ Python: $(python3 --version)"

# 2. Backend venv + deps
echo ""
echo "→ Installing backend deps..."
cd services/backend
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt
echo "✅ Deps installed"

# 3. Choose DB if not passed
if [ -z "$MODE" ]; then
  echo ""
  echo "Which database? "
  echo "  1) SQLite  (laptop, zero setup — recommended for first run)"
  echo "  2) PostgreSQL (Docker or installed Postgres)"
  read -p "Choose [1/2]: " CHOICE
  if [ "$CHOICE" = "2" ]; then MODE="postgres"; else MODE="sqlite"; fi
fi

if [ "$MODE" = "postgres" ] || [ "$MODE" = "pg" ]; then
  echo ""
  echo "→ Switching to PostgreSQL..."
  python scripts/switch_db.py postgres --apply
  echo ""
  echo "→ If using Docker, starting Postgres..."
  if command -v docker &>/dev/null; then
    cd ../..
    docker-compose up -d db redis || echo "⚠️  docker-compose failed — start Postgres manually"
    cd services/backend
    sleep 3
  fi
else
  echo ""
  echo "→ Switching to SQLite..."
  python scripts/switch_db.py sqlite --apply
fi

# 4. Init DB + seed
echo ""
echo "→ Initializing database..."
.venv/bin/python scripts/init_db.py --seed

# 5. Check
echo ""
.venv/bin/python scripts/db_check.py

echo ""
echo "========================================"
echo "  ✅ Setup complete!"
echo "  Start server: cd services/backend && .venv/bin/uvicorn app.main:app --reload --port 8000"
echo "  Login: admin@campus.edu / superadmin123"
echo "  Docs: http://localhost:8000/docs  |  Health: http://localhost:8000/api/v1/health/db"
echo "========================================"
