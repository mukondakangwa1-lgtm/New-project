"""
KUDOS Deployment Engine — Deploy to Render, Cloudflare, Vercel, Railway, Fly.io
KUDOS can help the superadmin take the app live and generate public links.
"""
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_PATH = str(Path(__file__).parent.parent.parent.parent)


# ──────────────────────────────────────────────
# DEPLOYMENT PLATFORMS
# ──────────────────────────────────────────────

PLATFORMS = {
    "render": {
        "name": "Render",
        "url": "https://render.com",
        "free_tier": "Yes — free web service, 512MB RAM, sleeps after 15 min idle",
        "best_for": "Public FastAPI backend (campus app only, no 270-agent HQ)",
        "setup": [
            "1. Sign up at render.com with GitHub",
            "2. New → Blueprint and select this repo (render.yaml) OR New → Web Service",
            "3. Build: pip install -r services/backend/requirements.txt",
            "4. Start: bash services/backend/start.sh",
            "5. Env: SECRET_KEY (generate), KUDOS_MODE=campus_help, QUOTA_SAFE=true",
            "6. DATABASE_URL from a free Neon Postgres project (do not use ephemeral SQLite)",
            "7. Health check: /api/v1/health",
            "8. Keep LLM keys OFF this service so campus help uses zero quota",
        ],
        "env_template": {
            "SECRET_KEY": "your-random-secret-key",
            "DATABASE_URL": "postgresql://user:pass@host/neondb?sslmode=require",
            "KUDOS_MODE": "campus_help",
            "QUOTA_SAFE": "true",
            "PYTHON_VERSION": "3.11",
        },
        "public_url_format": "https://digital-campus-api.onrender.com",
    },
    "vercel": {
        "name": "Vercel",
        "url": "https://vercel.com",
        "free_tier": "Yes — Hobby, 100GB bandwidth/month, best Next.js host",
        "best_for": "Public Next.js frontend for the whole world",
        "setup": [
            "1. Sign up at vercel.com with GitHub",
            "2. Import the repo, set Root Directory to frontend",
            "3. Env BACKEND_URL = https://your-backend.onrender.com",
            "4. Env NEXT_PUBLIC_WS_URL = wss://your-backend.onrender.com",
            "5. Deploy — public URL is https://your-project.vercel.app",
        ],
        "env_template": {
            "BACKEND_URL": "https://your-backend.onrender.com",
            "NEXT_PUBLIC_API_URL": "https://your-backend.onrender.com",
            "NEXT_PUBLIC_WS_URL": "wss://your-backend.onrender.com",
        },
        "public_url_format": "https://your-project.vercel.app",
    },
    "neon": {
        "name": "Neon Postgres",
        "url": "https://neon.tech",
        "free_tier": "Yes — serverless Postgres, scales to zero, ~0.5GB",
        "best_for": "Persistent public database (Render disks are ephemeral on free)",
        "setup": [
            "1. Sign up at neon.tech",
            "2. Create project digital-campus",
            "3. Copy the pooled connection string",
            "4. Paste it as DATABASE_URL on Render",
            "5. First boot runs seed.py + seed_kudos.py + seed_campus_help.py",
        ],
        "env_template": {
            "DATABASE_URL": "postgresql://user:pass@host/neondb?sslmode=require",
        },
        "public_url_format": "managed — no public app URL",
    },
    "cloudflare": {
        "name": "Cloudflare Pages",
        "url": "https://pages.cloudflare.com",
        "free_tier": "Yes — unlimited bandwidth, 500 builds/month",
        "best_for": "Frontend CDN alternative to Vercel",
        "setup": [
            "1. Cloudflare Dashboard → Pages → Connect GitHub",
            "2. Root directory: frontend",
            "3. Framework: Next.js",
            "4. Env BACKEND_URL = your Render API URL",
            "5. Custom domain optional",
        ],
        "env_template": {
            "BACKEND_URL": "https://your-backend.onrender.com",
            "NEXT_PUBLIC_WS_URL": "wss://your-backend.onrender.com",
        },
        "public_url_format": "https://your-project.pages.dev",
    },
    "oracle": {
        "name": "Oracle Cloud Always Free",
        "url": "https://www.oracle.com/cloud/free/",
        "free_tier": "Yes — ARM VM ~2 OCPU / 12GB RAM, always on, no sleep",
        "best_for": "Always-on public stack when Render cold starts are not acceptable",
        "setup": [
            "1. Create an Always Free ARM VM (Ampere A1)",
            "2. Open ports 22, 80, 443, 3000, 8000 in the VCN security list",
            "3. Install Docker and Docker Compose",
            "4. git clone the repo and copy a strong SECRET_KEY",
            "5. docker compose -f docker-compose.launch.yml up -d --build",
            "6. Do NOT run the 270-agent HQ on this VM — campus only",
        ],
        "env_template": {
            "SECRET_KEY": "your-random-secret-key",
            "KUDOS_MODE": "campus_help",
            "QUOTA_SAFE": "true",
        },
        "public_url_format": "http://YOUR_PUBLIC_IP:3000",
    },
    "huggingface": {
        "name": "Hugging Face Spaces",
        "url": "https://huggingface.co/spaces",
        "free_tier": "Yes — free CPU Space with a public URL",
        "best_for": "Fast public demo of the API",
        "setup": [
            "1. Create a Docker Space",
            "2. Point it at services/backend/Dockerfile",
            "3. Set KUDOS_MODE=campus_help and QUOTA_SAFE=true",
            "4. Share the *.hf.space URL",
        ],
        "env_template": {
            "KUDOS_MODE": "campus_help",
            "QUOTA_SAFE": "true",
        },
        "public_url_format": "https://your-name-digital-campus.hf.space",
    },
    "tunnel": {
        "name": "Cloudflare Tunnel (local HQ only)",
        "url": "https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/",
        "free_tier": "Yes — cloudflared is free",
        "best_for": "Private superadmin access to the 270-agent HQ on your 4GB PC — NOT the public world",
        "setup": [
            "1. Keep the 270 agents on the PC only",
            "2. cloudflared tunnel login && cloudflared tunnel create kudos-hq",
            "3. Route a hostname to http://localhost:8000",
            "4. Do not advertise this URL — 4GB RAM plus agents cannot serve the world",
            "5. Public users go to the Vercel + Render campus app instead",
        ],
        "env_template": {
            "KUDOS_MODE": "hq",
            "QUOTA_SAFE": "true",
        },
        "public_url_format": "https://hq.yourdomain.com (private)",
    },
}


# ──────────────────────────────────────────────
# ENV FILE MANAGEMENT
# ──────────────────────────────────────────────

ENV_PATH = os.path.join(REPO_PATH, "services", "backend", ".env")


def get_env_content() -> dict:
    """Read current .env file."""
    if not os.path.exists(ENV_PATH):
        return {"exists": False, "content": "", "vars": {}}

    with open(ENV_PATH) as f:
        content = f.read()

    vars_dict = {}
    for line in content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            vars_dict[key.strip()] = value.strip()

    return {"exists": True, "content": content, "vars": vars_dict}


def set_env_var(key: str, value: str) -> dict:
    """Set a single environment variable in .env."""
    current = get_env_content()
    lines = current["content"].split("\n") if current["content"] else []

    found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"{key}={value}")

    content = "\n".join(new_lines) + "\n"
    with open(ENV_PATH, "w") as f:
        f.write(content)

    return {"status": "set", "key": key, "value": value}


def create_env_file(vars_dict: dict) -> dict:
    """Create a new .env file with given variables."""
    lines = ["# Digital Campus Environment Variables", "# Generated by KUDOS", ""]
    for key, value in vars_dict.items():
        lines.append(f"{key}={value}")
    lines.append("")

    with open(ENV_PATH, "w") as f:
        f.write("\n".join(lines))

    return {"status": "created", "vars": len(vars_dict), "path": ENV_PATH}


# ──────────────────────────────────────────────
# GIT OPERATIONS
# ──────────────────────────────────────────────

def _run_git(args: list[str]) -> tuple[int, str]:
    """Run a git command."""
    try:
        result = subprocess.run(
            ["git"] + args, cwd=REPO_PATH,
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return 1, str(e)


def git_status() -> dict:
    """Get git status."""
    _, branch = _run_git(["branch", "--show-current"])
    _, status = _run_git(["status", "--short"])
    _, log = _run_git(["log", "--oneline", "-5"])
    _, diff = _run_git(["diff", "--stat"])
    return {
        "branch": branch.strip(),
        "status": status.strip(),
        "recent_commits": log.strip().split("\n") if log.strip() else [],
        "diff_stat": diff.strip(),
    }


def git_add_all() -> dict:
    """Stage all changes."""
    rc, output = _run_git(["add", "-A"])
    return {"status": "success" if rc == 0 else "error", "output": output.strip()}


def git_commit(message: str) -> dict:
    """Commit staged changes."""
    rc, output = _run_git(["commit", "-m", message])
    if rc == 0:
        _, hash_out = _run_git(["rev-parse", "HEAD"])
        return {"status": "committed", "hash": hash_out.strip()[:8], "message": message}
    return {"status": "error", "output": output.strip()}


def git_push(branch: str = "", force: bool = False) -> dict:
    """Push to remote."""
    if not branch:
        _, branch = _run_git(["branch", "--show-current"])
        branch = branch.strip()

    args = ["push", "origin", branch]
    if force:
        args.append("--force")

    rc, output = _run_git(args)
    return {"status": "pushed" if rc == 0 else "error", "branch": branch, "output": output.strip()}


def git_pull(branch: str = "") -> dict:
    """Pull from remote."""
    if not branch:
        _, branch = _run_git(["branch", "--show-current"])
        branch = branch.strip()

    rc, output = _run_git(["pull", "origin", branch])
    return {"status": "pulled" if rc == 0 else "error", "branch": branch, "output": output.strip()}


# ──────────────────────────────────────────────
# DEPLOYMENT GENERATION
# ──────────────────────────────────────────────

def generate_render_yaml() -> str:
    """Generate render.yaml for Render deployment."""
    return """services:
  - type: web
    name: digital-campus-backend
    runtime: python
    buildCommand: cd services/backend && pip install -r requirements.txt
    startCommand: cd services/backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: SECRET_KEY
        generateValue: true
      - key: DATABASE_URL
        value: sqlite:///./digital_campus.db

  - type: web
    name: digital-campus-frontend
    runtime: node
    buildCommand: cd frontend && npm install && npm run build
    startCommand: cd frontend && npm start
    envVars:
      - key: NEXT_PUBLIC_API_URL
        value: https://digital-campus-backend.onrender.com
"""


def generate_docker_compose_prod() -> str:
    """Generate production docker-compose.yml."""
    return """version: "3.9"

services:
  backend:
    build: ./services/backend
    ports:
      - "8000:8000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=sqlite:///./digital_campus.db
    volumes:
      - db-data:/app
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  db-data:
"""


def get_deployment_guide(platform: str) -> dict:
    """Get deployment guide for a specific platform."""
    p = PLATFORMS.get(platform.lower())
    if not p:
        return {"error": f"Unknown platform: {platform}. Available: {', '.join(PLATFORMS.keys())}"}
    return p


def list_platforms() -> list[dict]:
    """List all supported deployment platforms."""
    return [
        {"id": k, "name": v["name"], "free_tier": v["free_tier"], "best_for": v["best_for"]}
        for k, v in PLATFORMS.items()
    ]
