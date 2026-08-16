#!/usr/bin/env bash
# Production entrypoint for free-tier hosts (Render, Oracle, Hugging Face).
# Does not start Celery, Redis, or the 270-agent KUDOS HQ.
set -euo pipefail

cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
export PYTHONPATH="${PYTHONPATH:-.}"

python seed.py
python seed_kudos.py
python seed_campus_help.py

PORT="${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --workers 1 --proxy-headers
