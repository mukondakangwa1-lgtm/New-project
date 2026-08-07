# Database Migrations (Alembic)

Versioned schema management for the Digital Campus backend. Migrations are the
production path for schema changes — `AUTO_CREATE_TABLES=true` is only for
local throwaway databases.

## Commands

Run from `services/backend`:

```bash
# Apply all migrations
.venv/bin/python -m alembic upgrade head

# Create a new migration from model changes (review the generated file!)
.venv/bin/python -m alembic revision --autogenerate -m "describe change"

# Roll back one step
.venv/bin/python -m alembic downgrade -1

# Show current revision
.venv/bin/python -m alembic current
```

Inside Docker:

```bash
docker compose exec backend python -m alembic upgrade head
docker compose -f docker-compose.prod.yml run --rm backend python -m alembic upgrade head
```

## CI

The CI pipeline (`.github/workflows/ci.yml`) applies `alembic upgrade head` to a
fresh SQLite database on every push and asserts the expected tables exist, so a
broken migration fails the build before it reaches production.
