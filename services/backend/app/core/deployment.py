"""
KUDOS Deployment Engine — Deploy to Render, Cloudflare, Vercel, Railway, Fly.io
KUDOS can help the superadmin take the app live and generate public links.
"""
import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Optional

from app.core.paths import backend_root, project_root

BACKEND_PATH = str(backend_root(__file__))
REPO_PATH = str(project_root(__file__))


# ──────────────────────────────────────────────
# DEPLOYMENT PLATFORMS
# ──────────────────────────────────────────────

PLATFORMS = {
    "render": {
        "name": "Render",
        "url": "https://render.com",
        "free_tier": "Yes — 750 hours/month, auto-sleep after 15min inactivity",
        "best_for": "Full-stack apps (backend + frontend + database)",
        "setup": [
            "1. Sign up at render.com with GitHub",
            "2. Click 'New' → 'Web Service'",
            "3. Connect your GitHub repo",
            "4. Set build command: cd services/backend && pip install -r requirements.txt",
            "5. Set start command: cd services/backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT",
            "6. Add environment variables (SECRET_KEY, DATABASE_URL)",
            "7. Click 'Create Web Service'",
            "8. For frontend: 'New' → 'Static Site' → build command: cd frontend && npm install && npm run build",
        ],
        "env_template": {
            "SECRET_KEY": "your-random-secret-key",
            "DATABASE_URL": "sqlite:///./digital_campus.db",
            "PYTHON_VERSION": "3.11",
        },
        "public_url_format": "https://your-app-name.onrender.com",
    },
    "vercel": {
        "name": "Vercel",
        "url": "https://vercel.com",
        "free_tier": "Yes — unlimited deployments, 100GB bandwidth/month",
        "best_for": "Frontend (Next.js) — best Next.js hosting",
        "setup": [
            "1. Install Vercel CLI: npm i -g vercel",
            "2. cd frontend",
            "3. Run: vercel",
            "4. Follow prompts (connect GitHub, set project name)",
            "5. Vercel auto-detects Next.js and deploys",
            "6. Custom domain: vercel domains add yourdomain.com",
        ],
        "env_template": {
            "NEXT_PUBLIC_API_URL": "https://your-backend-url.com",
        },
        "public_url_format": "https://your-project.vercel.app",
    },
    "railway": {
        "name": "Railway",
        "url": "https://railway.app",
        "free_tier": "Yes — $5 free credit/month",
        "best_for": "Full-stack with database (PostgreSQL included)",
        "setup": [
            "1. Sign up at railway.app with GitHub",
            "2. Click 'New Project' → 'Deploy from GitHub repo'",
            "3. Select your repo",
            "4. Railway auto-detects and deploys",
            "5. Add PostgreSQL: 'New' → 'Database' → 'PostgreSQL'",
            "6. Set environment variables",
            "7. Custom domain: Settings → Domains",
        ],
        "env_template": {
            "SECRET_KEY": "your-random-secret-key",
            "DATABASE_URL": "${{Postgres.DATABASE_URL}}",
        },
        "public_url_format": "https://your-app.up.railway.app",
    },
    "fly": {
        "name": "Fly.io",
        "url": "https://fly.io",
        "free_tier": "Yes — 3 shared VMs, 160GB bandwidth",
        "best_for": "Global deployment, Docker containers",
        "setup": [
            "1. Install flyctl: curl -L https://fly.io/install.sh | sh",
            "2. Run: fly auth login",
            "3. Run: fly launch",
            "4. Follow prompts",
            "5. Deploy: fly deploy",
            "6. Set secrets: fly secrets set SECRET_KEY=your-key",
        ],
        "env_template": {
            "SECRET_KEY": "your-random-secret-key",
            "DATABASE_URL": "sqlite:///./digital_campus.db",
        },
        "public_url_format": "https://your-app.fly.dev",
    },
    "cloudflare": {
        "name": "Cloudflare Pages",
        "url": "https://pages.cloudflare.com",
        "free_tier": "Yes — unlimited sites, 500 builds/month",
        "best_for": "Frontend static sites, CDN, DDoS protection",
        "setup": [
            "1. Go to Cloudflare Dashboard → Pages",
            "2. Connect GitHub repo",
            "3. Set framework: Next.js",
            "4. Build command: cd frontend && npm install && npm run build",
            "5. Output directory: frontend/.next",
            "6. Add environment variables",
            "7. Custom domain: Custom Domains → Add",
        ],
        "env_template": {
            "NEXT_PUBLIC_API_URL": "https://your-backend-url.com",
        },
        "public_url_format": "https://your-project.pages.dev",
    },
    "digitalocean": {
        "name": "DigitalOcean App Platform",
        "url": "https://www.digitalocean.com/products/app-platform",
        "free_tier": "Yes — 3 static sites, 1 app with basic tier",
        "best_for": "Full-stack with managed database",
        "setup": [
            "1. Sign up at digitalocean.com",
            "2. Create → Apps → Connect GitHub",
            "3. Select repo and branch",
            "4. Configure build and run commands",
            "5. Add managed PostgreSQL database",
            "6. Set environment variables",
            "7. Deploy",
        ],
        "env_template": {
            "SECRET_KEY": "your-random-secret-key",
            "DATABASE_URL": "postgresql://user:pass@host:5432/db",
        },
        "public_url_format": "https://your-app.ondigitalocean.app",
    },
}


# ──────────────────────────────────────────────
# ENV FILE MANAGEMENT
# ──────────────────────────────────────────────

ENV_PATH = os.path.join(BACKEND_PATH, ".env")


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
    """Return the checked-in LAN/VPS production Compose definition."""
    compose_path = os.path.join(REPO_PATH, "docker-compose.prod.yml")
    try:
        with open(compose_path, encoding="utf-8") as compose_file:
            return compose_file.read()
    except OSError as exc:
        return f"# Unable to read docker-compose.prod.yml: {exc}"


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
