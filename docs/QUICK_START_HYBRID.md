# Quick Start — Hybrid DB (Postgres + SQLite)

> **You create the Postgres account once, then just `connect`. SQLite: download → `execute`. That's it.**

---

## Option A — SQLite on Laptop (2 minutes, no Docker)

**1. Download SQLite (Windows):**
```
winget install SQLite.SQLite
# OR download zip from https://www.sqlite.org/download.html → unzip to C:\sqlite → add to PATH
sqlite3 --version   # verify
```
macOS/Linux: `brew install sqlite` / `sudo apt install sqlite3`

**2. One-command setup (Windows):**
```bat
setup.bat sqlite
```
Linux/macOS:
```bash
bash setup.sh sqlite
# or
make setup-sqlite
```

**What it does:**
- Copies `.env.sqlite` → `.env` (`DATABASE_URL=sqlite:///./digital_campus.db`)
- `pip install`
- Creates `digital_campus.db` file + all tables + pgvector-skip
- Seeds `admin@campus.edu / superadmin123`
- Runs `db_check.py` → ✅

**3. Run:**
```bat
cd services\backend
.venv\Scripts\uvicorn app.main:app --reload --port 8000
```
Open http://localhost:8000/docs → Login. Done.

**Manual alternative (if you prefer):**
```bat
cd services\backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.sqlite .env
.venv\Scripts\python scripts\init_db.py --seed
.venv\Scripts\python scripts\db_check.py
```

---

## Option B — PostgreSQL (production / shared)

**1. Create Postgres account/DB (once):**

**With Docker (easiest):**
```bash
docker-compose up -d db redis   # creates dc_user / dc_pass / digital_campus + pgvector
```

**Without Docker (native Postgres):**
```sql
-- psql -U postgres
CREATE USER dc_user WITH PASSWORD 'dc_pass';
CREATE DATABASE digital_campus OWNER dc_user;
GRANT ALL PRIVILEGES ON DATABASE digital_campus TO dc_user;
\c digital_campus
CREATE EXTENSION IF NOT EXISTS vector;
```

**2. One-command setup:**
```bat
setup.bat postgres
```
or
```bash
bash setup.sh postgres
# or
make setup-postgres
```

**What it does:**
- Copies `.env.postgres` → `.env` (`DATABASE_URL=postgresql+psycopg2://dc_user:dc_pass@localhost:5432/digital_campus`)
- Creates all tables + `CREATE EXTENSION vector`
- Seeds superadmin
- Checks connection

**For Docker service name `db`:**
Edit `.env`: `DATABASE_URL=postgresql+psycopg2://dc_user:dc_pass@db:5432/digital_campus`

**3. Run:**
```bash
# Native
cd services/backend && .venv/bin/uvicorn app.main:app --reload --port 8000
# Docker
docker-compose up -d
```

---

## Switching Anytime (one command)

```bash
# Switch to SQLite
python services/backend/scripts/switch_db.py sqlite --apply
# or
make switch-sqlite

# Switch to Postgres
python services/backend/scripts/switch_db.py postgres --apply
# or
make switch-postgres

# Check which DB is active
python services/backend/scripts/db_check.py
curl http://localhost:8000/api/v1/health/db
```

---

## After Creating an Account — Just Connect

Once `init_db.py --seed` has run:

| Action | How |
|---|---|
| **Login** | `POST /api/v1/auth/login` with `admin@campus.edu / superadmin123` |
| **Create user** | `POST /api/v1/auth/register` → auto-works on current DB (Postgres or SQLite) |
| **Verify DB** | `GET /api/v1/health/db` → shows `type: PostgreSQL` or `SQLite` + `latency_ms` + `pgvector` |
| **Switch DB later** | Change `DATABASE_URL` in `.env`, restart server — accounts are per-DB (SQLite file vs Postgres server). To migrate: `python scripts/sync_pg_to_sqlite.py` |

**No code change needed** — `app/core/database.py` auto-detects `sqlite://` vs `postgresql://` and sets pragmas/pools.

---

## Troubleshooting

| Error | Fix |
|---|---|
| `could not connect to server` (Postgres) | `docker-compose up -d db` or `pg_ctl start` + check `DATABASE_URL` host/port |
| `password authentication failed` | Check `dc_user`/`dc_pass` in `.env` matches `CREATE USER` |
| `sqlite3 not found` | Install SQLite, restart terminal |
| `No such file .env` | `copy .env.sqlite .env` (Windows) or `cp services/backend/.env.sqlite services/backend/.env` |

---

## Files

- `services/backend/.env.sqlite` — ready SQLite config
- `services/backend/.env.postgres` — ready Postgres config
- `services/backend/scripts/init_db.py` — create tables for either DB
- `services/backend/scripts/db_check.py` — test connection + helpful fix
- `services/backend/scripts/switch_db.py` — flip with one command
- `setup.bat` / `setup.sh` / `Makefile` — one-click setup
