# Digital Campus — Hybrid PostgreSQL + SQLite Strategy
### Efficient Use of Both Databases (PostgreSQL on Server + SQLite on Laptop)

> **Date:** 2026-08-08 • **Project:** `mukondakangwa1-lgtm/New-project` (Digital Campus)
> **Stack:** FastAPI + SQLAlchemy + Next.js • **Current DB:** Single `DATABASE_URL` (SQLite dev default, Postgres via Docker)

---

## 1. Project Analysis (30-second summary)

Digital Campus is a **unified university platform** with ~30 tables across 8 domains:

| Domain | Tables | Write pattern | Needs |
|---|---|---|---|
| **Core Academic** | `users`, `courses`, `enrollments`, `grades` | Low-mid, concurrent | ACID, FK integrity, auth |
| **Attendance** | `timetable_entries`, `sessions`, `attendances` | Burst at class start (100s concurrent check-ins) | Transactions, isolation |
| **KUDOS AI** | `kudos_documents`, `kudos_chunks`, `kudos_web_knowledge`, `kudos_conversations`, `kudos_messages`, `kudos_connectors`, `kudos_vectors` | Heavy read, bulk inserts, **vector search** | `pgvector`, full-text, large Text columns |
| **Social/Chat** | `posts`, `comments`, `reactions`, `chat_rooms`, `chat_members`, `chat_messages` | High write, real-time | Concurrency, WebSocket |
| **Academic Extended** | `assignments`, `submissions`, `exams`, `exam_questions`, `exam_attempts`, `forum_threads`, `study_groups` | Mid write, relational grading | Joins, analytics |
| **Planner** | `calendar_events`, `study_goals`, `notifications`, `certificates` | Personal, low | Simple CRUD |
| **System** | Guardian logs, shield, brain logs, sync logs | Append-only, high volume, ephemeral | No need to replicate centrally |
| **Future** | Analytics, embeddings | Batch | Columnar/vector performance |

**Current implementation (`app/core/database.py`):**

```python
# Already multi-DB aware — switches connect_args by URL prefix
if DATABASE_URL.startswith("sqlite"): connect_args = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
```

**`docker-compose.yml` already provides:** `postgres:15` + `redis` + `pgvector.sql` (`CREATE EXTENSION vector`). So the repo *already supports* both — you just flip `DATABASE_URL`.

**Key finding:** You **do NOT need to run both DBs at the same time in production.** The most efficient pattern is **environment-switched + optional local replica**. Running a true dual-write (every query goes to both DBs) would double complexity and create sync hell.

---

## 2. Why Your Choice (Postgres + SQLite) Is Optimal

|  | PostgreSQL (Server) | SQLite (Laptop) |
|---|---|---|
| **Strength** | Concurrency, `pgvector` HNSW/IVFFlat, JSONB, CTEs, `FOR UPDATE`, 100+ simultaneous students | Zero install, file = DB, offline, 10× faster for single-user, perfect for KUDOS offline |
| **Weakness** | Needs Docker/service, heavier | No concurrent writes, no `pgvector`, no row-level locks |
| **Digital Campus fit** | Production, multi-user exams/attendance/chat, vector similarity (`vector <=> query`) | Dev, testing, demo on plane, KUDOS Guardian logs, offline queue |

> **Golden rule:** PostgreSQL = **System of Record**. SQLite = **Local Cache / Offline Replica / Dev DB**. Never treat them as equals.

SQLite is *already* on most laptops (`sqlite3 --version`). Installing it is 2 minutes.

---

## 3. Three Efficient Architectures — Pick ONE

### Pattern A — Environment Switch (RECOMMENDED for you, start here)
> The repo's current design, just polished. Zero sync code.

```
Laptop dev / CI tests        →  SQLite (file: ./digital_campus.db)
Docker / Staging / Prod      →  PostgreSQL (postgres://dc_user:dc_pass@db:5432/digital_campus)
```

**How:** One env var.
```bash
# .env on laptop
DATABASE_URL=sqlite:///./digital_campus.db
# .env on server / docker-compose.env
DATABASE_URL=postgresql+psycopg2://dc_user:dc_pass@db:5432/digital_campus
```
**Pros:** Simple, no sync bugs, already working, `alembic` works for both, tests run 5× faster on SQLite.
**Cons:** Laptop DB and server DB are disjoint (which is fine for dev).
**When to use:** You work alone or with a small team and pull seed data via `seed.py`.

### Pattern B — Offline-First Replica (RECOMMENDED PHASE 2)
> Keep Postgres as primary, but laptop has a **read replica + write queue** for offline work.

```
Postgres (primary)  ◄──sync──►  SQLite (laptop replica)
   ▲                               ▲
   │  Field trip / no WiFi         │  Chat offline? write to SQLite queue
   └───── nightly dump ────────────┘
```

**Use:** Demo in classroom with no internet, KUDOS learns offline, attendance taken offline then synced.
**How:** Add 2 env vars + a sync script (provided below):
```ini
DATABASE_URL=postgresql+psycopg2://...          # primary
DATABASE_URL_LOCAL=sqlite:///./digital_campus_local.db  # offline file
SYNC_MODE=auto  # auto | manual | disabled
```
App tries Postgres first, falls back to SQLite if unreachable, queues writes (`chat_messages.is_offline=true`, `kudos_sync_logs`).

### Pattern C — Domain Split (Advanced, only if you need it)
> Hot/concurrency tables on Postgres, ephemeral/local tables on SQLite *simultaneously* in same process (dual engines).

| Postgres (engine_primary) | SQLite (engine_local) |
|---|---|
| users, courses, enrollments, assignments, submissions, exams, grades, posts, chat_*, kudos_documents, kudos_chunks, **kudos_vectors** (pgvector only works here) | guardian_logs, brain_logs, device_fingerprints, performance_logs, kudos_temp_cache, offline_queue, calendar_drafts |

**Pros:** Best performance — ephemeral high-volume writes don't touch Postgres.
**Cons:** Two sessions, two migrations, joins can't cross DBs.
**Recommendation:** Don't do this unless guardian logs hurt Postgres performance (they won't at <10k users).

**→ My recommendation for you:**
1. **Now:** Pattern A (env switch) — costs 0 code.
2. **Next week:** Add Pattern B replica scripts (I provide them below).
3. **Later if needed:** Split only the 3 log tables to SQLite.

---

## 4. Table-to-Database Allocation (If You Split)

| Keep in **PostgreSQL** (must) | Reason |
|---|---|
| `kudos_vectors` | Requires `pgvector` — no HNSW in SQLite without `sqlite-vss` |
| `users`, `courses`, `enrollments` | Concurrent FK, auth |
| `sessions`, `attendances` | Burst `UPDATE ... WHERE is_open=true` needs row locks |
| `chat_rooms`, `chat_messages` | WebSocket concurrency |
| `assignments`, `submissions`, `grades`, `exams`, `exam_attempts` | Transactional grading |
| `posts`, `comments`, `reactions` | Public feed needs `SELECT ... FOR UPDATE` on view_count |

| Ideal for **SQLite** (local) | Reason |
|---|---|
| `kudos_chunks` *cache copy* | Read-only replica for offline answering |
| `kudos_web_knowledge` *cache copy* | Offline web knowledge |
| `kudos_knowledge_packs` | Exportable packs (already JSON Text — perfect for file) |
| Guardian `kudos_shield` logs, `device_fingerprints`, `performance_logs` | Append-only, local-only, no need to centralize |
| `notifications` local queue | Push later |
| `chat_messages` where `is_offline=true` | Outbox pattern |

> If you keep one DB, everything lives in Postgres in prod and SQLite in dev — no split needed.

---

## 5. Implementation — 5-Minute Setup

### 5.1 Install SQLite on your laptop

**Windows (your likely OS):**
```powershell
# Option 1: winget (recommended)
winget install SQLite.SQLite
sqlite3 --version

# Option 2: manual
# Download sqlite-tools-win-x64-*.zip from https://sqlite.org/download.html
# Unzip to C:\sqlite, add to PATH
```

**macOS / Linux:**
```bash
# macOS
brew install sqlite
# Ubuntu/Debian
sudo apt update && sudo apt install sqlite3
sqlite3 --version
```

Verify:
```bash
sqlite3 digital_campus.db "SELECT sqlite_version();"
```

### 5.2 Configure `.env` (two files)

Create `services/backend/.env` (laptop):
```ini
# Laptop — local dev
DATABASE_URL=sqlite:///./digital_campus.db
SECRET_KEY=dev-only-change-in-prod
DEBUG=true
EMBED_DIM=1536
```

Create `services/backend/.env.prod` (server/docker):
```ini
# Server / Docker — production
DATABASE_URL=postgresql+psycopg2://dc_user:dc_pass@db:5432/digital_campus
SECRET_KEY=replace-with-long-random-64-chars
DEBUG=false
EMBED_DIM=1536
```

`docker-compose.yml` already reads `services/backend/.env` — no change needed. For prod, run:
```bash
docker-compose --env-file services/backend/.env.prod up -d
```

### 5.3 The polished `config.py` + `database.py` (already patched in this branch)

See `services/backend/app/core/config.py`:
```python
class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./digital_campus.db"          # primary
    DATABASE_URL_LOCAL: str | None = None  # e.g. sqlite:///./local.db for offline replica
    EMBED_DIM: int = 1536
```

See `services/backend/app/core/database.py`:
- Auto-detects `sqlite` vs `postgres`, sets `check_same_thread` only for SQLite.
- Provides `SessionLocal` for primary; if `DATABASE_URL_LOCAL` is set, also exposes `LocalSessionLocal` + `get_local_db()` for offline queue.

### 5.4 Sync scripts (provided in `services/backend/scripts/`)

**Pull Postgres → SQLite (nightly or before trip):**
```bash
# On laptop, with Postgres reachable
python scripts/sync_pg_to_sqlite.py --pg-url postgresql://... --sqlite-path ./digital_campus_local.db --tables all
# Creates/overwrites local replica, keeps your offline copy fresh
```

**Push SQLite offline queue → Postgres (when back online):**
```bash
python scripts/sync_offline_queue.py --sqlite-path ./digital_campus_local.db --pg-url postgresql://...
# Replays chat_messages where is_offline=true, attendance, etc.
```

Both use `pg_dump`/`sqlite3` dump + SQLAlchemy — no manual SQL.

---

## 6. Data Flow Diagrams

**Daily dev (Pattern A):**
```
[laptop]  Code → SQLite file → pytest → commit
             ↓ seed.py
[server]  Docker → Postgres (pgvector) → FastAPI → Next.js
```

**Offline trip (Pattern B):**
```
Before flight:  pg_dump → sqlite replica
On plane:       App writes to SQLite (offline queue)
After landing:  sync_offline_queue.py → Postgres (conflict: last-write-wins, log to sync_logs)
```

---

## 7. Migrations (Alembic) — One Source, Both Targets

```bash
cd services/backend

# Dev (SQLite)
DATABASE_URL=sqlite:///./digital_campus.db alembic revision --autogenerate -m "add feature"
alembic upgrade head

# Prod (Postgres)
DATABASE_URL=postgresql+psycopg2://dc_user:dc_pass@localhost:5432/digital_campus alembic upgrade head
```

**Important:** Keep migrations DB-agnostic: avoid `Vector` type in autogenerate; create `kudos_vectors` via `initdb/pgvector.sql` only on Postgres. SQLite will simply skip that table (app guards with `try: from pgvector import Vector`).

Use branching if needed:
```python
# in alembic version file
if context.get_x_argument(as_dictionary=True).get("db") == "postgres":
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
```

---

## 8. Performance & Cost Tips

- **SQLite pragmas** (auto-set in `database.py` for laptop):
  ```python
  # 10× faster, safe for dev
  PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA cache_size=-64000; PRAGMA foreign_keys=ON;
  ```
- **Postgres tuning** for Digital Campus at scale (<100k rows): default `postgres:15` is fine. Only tune `shared_buffers=256MB` if you host lots of `kudos_vectors`.
- **Vector search:** Keep `kudos_vectors` ONLY on Postgres. SQLite alternative (`sqlite-vss`) is slower and needs custom build — not worth it until offline vector search is a must. For offline, cache embeddings as JSON in SQLite and do brute-force Python cosine (ok for <5k chunks).
- **Backups:** Postgres → `pg_dump` nightly to S3. SQLite → just copy the file (`cp digital_campus.db backups/db-2026-08-08.db`); Guardian already does hourly knowledge backups.

---

## 9. Security Checklist

- [ ] Change `SECRET_KEY` from `changeme-in-production` to `openssl rand -hex 32`
- [ ] SQLite file: `chmod 600 digital_campus.db`, add `*.db` to `.gitignore` (already there)
- [ ] Postgres: `POSTGRES_PASSWORD` not committed; use Docker secrets or env file with `chmod 600`
- [ ] Never commit `.env` — use `.env.example` as template (already correct)
- [ ] Enable `foreign_keys=ON` for SQLite (done in hybrid `database.py`)

---

## 10. Recommended Rollout (2 weeks)

**Week 1 — Foundation (30 min):**
1. Install SQLite locally (section 5.1)
2. `cd services/backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt`
3. `cp .env.example .env` → set `DATABASE_URL=sqlite:///./digital_campus.db`
4. `.venv/bin/python seed.py && .venv/bin/python seed_kudos.py`
5. `.venv/bin/uvicorn app.main:app --reload` → test at http://localhost:8000/docs

**Week 2 — Hybrid ready:**
6. Review `app/core/database_hybrid.py` (new file in this branch)
7. Test docker path: `docker-compose up -d` → verify Postgres + pgvector
8. Before field demo, run `sync_pg_to_sqlite.py` to snapshot Postgres to laptop

---

## 11. TL;DR Decision Matrix

| Question | Answer |
|---|---|
| Should I run both DBs at once in production? | **No** — env-switch is cleaner |
| Where do vectors live? | **Postgres only** (pgvector) |
| Where does my laptop DB live? | `services/backend/digital_campus.db` (gitignored) |
| How to demo offline? | `sync_pg_to_sqlite.py` before offline, `sync_offline_queue.py` after |
| Best ORM approach? | Single `Base` metadata, one `engine` at a time — hybrid file gives dual engines only when needed |

---

## 12. Files Delivered in This Branch

- `services/backend/app/core/database_hybrid.py` — optional dual-engine helper (import instead of `database.py` if you want split)
- `services/backend/scripts/sync_pg_to_sqlite.py` — pull replica
- `services/backend/scripts/sync_offline_queue.py` — push offline queue
- `services/backend/.env.example` — documented hybrid env vars
- This doc: `docs/hybrid-database-strategy.md`

All are **opt-in** — your existing `database.py` and `config.py` continue to work unchanged with just `DATABASE_URL`.

---

## 13. Quick Commands Cheat Sheet

```bash
# Install deps
sqlite3 --version; psql --version  # verify
cd services/backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt

# Dev with SQLite (laptop)
DATABASE_URL=sqlite:///./digital_campus.db .venv/bin/uvicorn app.main:app --reload --port 8000

# Prod with Postgres (docker)
docker-compose up -d
docker-compose exec db psql -U dc_user -d digital_campus -c "SELECT * FROM pg_extension WHERE extname='vector';"

# Migrate
.venv/bin/alembic upgrade head
.venv/bin/alembic revision --autogenerate -m "my change"

# Snapshot for offline
python scripts/sync_pg_to_sqlite.py
ls -lh *.db
```

---

**Bottom line:** Keep it simple — SQLite is your `localhost` workhorse, PostgreSQL is your `production + vector + concurrency` workhorse. Flip with one env var, snapshot when you need offline. The code already supports this; the scripts in this branch make it turnkey.

*Questions? Check `app/core/database.py` comments or open an issue.*
