"""
Digital Campus - Superadmin Dashboard API
Unified admin control: brain, identity, root, analytics, guidelines.
Everything secured — admin-only access.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.kudos_brain import (
    start_brain, stop_brain, get_brain_status, get_brain_log,
    get_brain_thoughts, get_self_knowledge, get_improvement_report,
    teach_knowledge, add_capability,
)
from app.core.kudos_identity import (
    get_identity, update_identity, rename, get_guidelines, set_guidelines,
    add_guideline, update_body_part, get_status_report, log_improvement,
)
from app.core.auto_learner import get_auto_learner_status, start_auto_learner, stop_auto_learner, trigger_learning_cycle
from app.models import User, Course, Enrollment, Attendance, Session as SessionModel, KudosDocument, KudosWebKnowledge, KudosConversation, KudosMessage
from app.models_extended import Notification, Assignment, Submission, Grade, ExamAttempt

router = APIRouter()
REPO_PATH = str(Path(__file__).parent.parent.parent.parent)


# ──────────────────────────────────────────────
# UNIFIED DASHBOARD
# ──────────────────────────────────────────────

@router.get("/dashboard")
def superadmin_dashboard(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Get complete superadmin dashboard data."""
    return {
        "identity": get_identity(),
        "brain": get_brain_status(),
        "auto_learner": get_auto_learner_status(),
        "guidelines": get_guidelines(),
        "platform": {
            "users": db.query(User).count(),
            "students": db.query(User).filter(User.is_admin == False).count(),
            "admins": db.query(User).filter(User.is_admin == True).count(),
            "courses": db.query(Course).count(),
            "enrollments": db.query(Enrollment).count(),
            "sessions": db.query(SessionModel).count(),
            "attendance_records": db.query(Attendance).count(),
            "documents": db.query(KudosDocument).count(),
            "web_knowledge": db.query(KudosWebKnowledge).count(),
            "conversations": db.query(KudosConversation).count(),
            "messages": db.query(KudosMessage).count(),
            "assignments": db.query(Assignment).count(),
            "submissions": db.query(Submission).count(),
            "exam_attempts": db.query(ExamAttempt).count(),
            "notifications": db.query(Notification).count(),
        },
    }


# ──────────────────────────────────────────────
# BRAIN CONTROL
# ──────────────────────────────────────────────

@router.post("/brain/start")
def activate_brain(admin: User = Depends(require_admin)):
    """Activate KUDOS's autonomous brain."""
    result = start_brain()
    log_improvement("brain", "Brain activated by superadmin")
    return result


@router.post("/brain/stop")
def deactivate_brain(admin: User = Depends(require_admin)):
    """Deactivate KUDOS's brain."""
    return stop_brain()


@router.get("/brain/status")
def brain_status(admin: User = Depends(require_admin)):
    """Get brain status."""
    return get_brain_status()


@router.get("/brain/log")
def brain_log(limit: int = 50, admin: User = Depends(require_admin)):
    """Get brain activity log."""
    return {"log": get_brain_log(limit)}


@router.get("/brain/thoughts")
def brain_thoughts(limit: int = 30, admin: User = Depends(require_admin)):
    """Get KUDOS's recent thoughts."""
    return {"thoughts": get_brain_thoughts(limit)}


@router.get("/brain/knowledge")
def brain_knowledge(admin: User = Depends(require_admin)):
    """Get KUDOS's self-knowledge."""
    return get_self_knowledge()


@router.get("/brain/report")
def brain_report(admin: User = Depends(require_admin)):
    """Get improvement report."""
    return get_improvement_report()


@router.post("/brain/teach")
def teach_brain(area: str, content: str, admin: User = Depends(require_admin)):
    """Teach KUDOS something new."""
    return teach_knowledge(area, content)


@router.post("/brain/capability")
def add_brain_capability(name: str, description: str, admin: User = Depends(require_admin)):
    """Add a new capability to KUDOS."""
    return add_capability(name, description)


# ──────────────────────────────────────────────
# AUTO-LEARNER CONTROL
# ──────────────────────────────────────────────

@router.post("/auto-learn/start")
def start_learning(interval_minutes: int = 30, admin: User = Depends(require_admin)):
    """Start auto-learning."""
    return start_auto_learner(interval_minutes)


@router.post("/auto-learn/stop")
def stop_learning(admin: User = Depends(require_admin)):
    """Stop auto-learning."""
    return stop_auto_learner()


@router.post("/auto-learn/trigger")
def trigger_learning(admin: User = Depends(require_admin)):
    """Trigger a learning cycle now."""
    return trigger_learning_cycle()


@router.get("/auto-learn/status")
def learning_status(admin: User = Depends(require_admin)):
    """Get auto-learner status."""
    return get_auto_learner_status()


# ──────────────────────────────────────────────
# IDENTITY & GUIDELINES
# ──────────────────────────────────────────────

@router.get("/identity")
def get_identity_endpoint(admin: User = Depends(require_admin)):
    return get_identity()


@router.patch("/identity")
def update_identity_endpoint(updates: dict, admin: User = Depends(require_admin)):
    return update_identity(updates)


@router.post("/rename")
def rename_kudos(new_name: str, admin: User = Depends(require_admin)):
    return rename(new_name)


@router.get("/guidelines")
def list_guidelines(admin: User = Depends(require_admin)):
    return {"guidelines": get_guidelines()}


@router.put("/guidelines")
def replace_guidelines(guidelines: list[str], admin: User = Depends(require_admin)):
    return {"result": set_guidelines(guidelines)}


@router.post("/guidelines/add")
def add_rule(guideline: str, admin: User = Depends(require_admin)):
    return {"result": add_guideline(guideline)}


@router.patch("/body/{part}")
def update_body(part: str, updates: dict, admin: User = Depends(require_admin)):
    return update_body_part(part, updates)


# ──────────────────────────────────────────────
# ROOT TERMINAL
# ──────────────────────────────────────────────

class RootCommand(BaseModel):
    command: str
    args: str = ""


@router.post("/root/exec")
def root_execute(body: RootCommand, admin: User = Depends(require_admin)):
    """Execute a root command."""
    cmd = body.command.lower().strip()
    args = body.args.strip()

    def _get_file_tree():
        tree = []
        for root, dirs, files in os.walk(REPO_PATH):
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".venv", "__pycache__", ".next")]
            level = root.replace(REPO_PATH, "").count(os.sep)
            if level > 3:
                continue
            indent = " " * 2 * level
            tree.append(f"{indent}{os.path.basename(root)}/")
            subindent = " " * 2 * (level + 1)
            for f in files[:10]:
                tree.append(f"{subindent}{f}")
        return {"tree": "\n".join(tree[:100])}

    def _read_file(path):
        target = os.path.join(REPO_PATH, path)
        if not os.path.isfile(target):
            return {"error": f"File not found: {path}"}
        if os.path.getsize(target) > 50000:
            return {"error": "File too large"}
        with open(target, "r") as f:
            return {"path": path, "content": f.read()[:10000]}

    def _list_files(path=""):
        target = os.path.join(REPO_PATH, path) if path else REPO_PATH
        if not os.path.isdir(target):
            return {"error": "Not a directory"}
        items = []
        for item in sorted(os.listdir(target)):
            if item.startswith("."):
                continue
            full = os.path.join(target, item)
            items.append({"name": item, "type": "dir" if os.path.isdir(full) else "file"})
        return {"items": items[:50]}

    commands = {
        "help": lambda: {"commands": list(commands.keys())},
        "status": lambda: get_status_report(),
        "identity": lambda: get_identity(),
        "brain": lambda: get_brain_status(),
        "thoughts": lambda: {"thoughts": get_brain_thoughts()},
        "log": lambda: {"log": get_brain_log()},
        "tree": lambda: _get_file_tree(),
        "files": lambda: _list_files(args),
        "read": lambda: _read_file(args),
        "gaps": lambda: get_self_knowledge().get("things_to_learn", []),
        "capabilities": lambda: get_self_knowledge().get("capabilities", []),
    }

    if cmd in commands:
        try:
            result = commands[cmd]()
            log_improvement("root", f"Root command: {cmd} {args}")
            return {"command": cmd, "result": result}
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown command: {cmd}. Type 'help'."}


# ──────────────────────────────────────────────
# SECURE CHAT (Superadmin <-> KUDOS)
# ──────────────────────────────────────────────

class SecureMessage(BaseModel):
    message: str


@router.post("/chat")
def secure_chat(body: SecureMessage, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Secure chat between superadmin and KUDOS — handles everything."""
    from app.core.deployment import (
        git_status, git_add_all, git_commit, git_push, git_pull,
        get_env_content, set_env_var, create_env_file,
        list_platforms, get_deployment_guide, PLATFORMS,
    )
    msg = body.message.lower().strip()
    raw = body.message.strip()

    # ── GIT COMMANDS ──
    if msg == "git status":
        result = git_status()
        return {"from": "KUDOS", "message": f"Git Status:\n• Branch: {result['branch']}\n• Changes: {result['status'] or 'Clean'}\n• Recent: {', '.join(result['recent_commits'][:3])}", "action": "git_status"}

    if msg.startswith("git commit"):
        commit_msg = raw.replace("git commit", "").strip() or "Update by KUDOS"
        result = git_add_all()
        result = git_commit(commit_msg)
        if result["status"] == "committed":
            return {"from": "KUDOS", "message": f"Committed! Hash: {result['hash']}\nMessage: {result['message']}", "action": "git_committed"}
        return {"from": "KUDOS", "message": f"Commit failed: {result.get('output', 'unknown error')}", "action": "git_error"}

    if msg.startswith("git push"):
        force = "--force" in msg or "force" in msg
        result = git_push(force=force)
        if result["status"] == "pushed":
            return {"from": "KUDOS", "message": f"Pushed to {result['branch']}! Your code is now on GitHub. 🚀", "action": "git_pushed"}
        return {"from": "KUDOS", "message": f"Push failed: {result.get('output', 'unknown error')}", "action": "git_error"}

    if msg == "git pull":
        result = git_pull()
        return {"from": "KUDOS", "message": f"Pulled from {result['branch']}: {result.get('output', 'OK')}", "action": "git_pulled"}

    # ── ENV COMMANDS ──
    if msg == "show env" or msg == "env":
        env = get_env_content()
        if env["exists"]:
            safe_vars = {k: ("***" if "key" in k.lower() or "secret" in k.lower() or "password" in k.lower() else v) for k, v in env["vars"].items()}
            return {"from": "KUDOS", "message": f"Current .env variables:\n" + "\n".join(f"• {k}={v}" for k, v in safe_vars.items()), "action": "env_show"}
        return {"from": "KUDOS", "message": "No .env file exists. Say 'create env' to create one.", "action": "env_missing"}

    if msg.startswith("set env"):
        parts = raw.replace("set env", "").strip()
        if "=" in parts:
            key, _, value = parts.partition("=")
            result = set_env_var(key.strip(), value.strip())
            return {"from": "KUDOS", "message": f"Environment variable set: {result['key']}={result['value']}", "action": "env_set"}
        return {"from": "KUDOS", "message": "Format: set env KEY=value", "action": "env_help"}

    # ── DEPLOYMENT COMMANDS ──
    if msg == "deploy" or msg == "deployment" or msg == "how to deploy":
        platforms = list_platforms()
        text = "Here are the platforms you can deploy to:\n\n"
        for p in platforms:
            text += f"• **{p['name']}** — {p['best_for']} ({p['free_tier']})\n"
        text += "\nSay 'deploy to [platform]' for step-by-step instructions.\n"
        text += "Platforms: " + ", ".join(PLATFORMS.keys())
        return {"from": "KUDOS", "message": text, "action": "deployment_info"}

    if msg.startswith("deploy to") or msg.startswith("deploy on"):
        platform = msg.replace("deploy to", "").replace("deploy on", "").strip()
        guide = get_deployment_guide(platform)
        if "error" in guide:
            return {"from": "KUDOS", "message": guide["error"], "action": "deploy_error"}
        steps = "\n".join(guide["setup"])
        return {"from": "KUDOS", "message": f"Deploy to {guide['name']}:\n\n{steps}\n\nPublic URL: {guide['public_url_format']}\n\nSay 'generate render.yaml' or 'generate docker-compose' for config files.", "action": "deploy_guide"}

    if "generate render" in msg:
        from app.core.deployment import generate_render_yaml
        return {"from": "KUDOS", "message": "render.yaml generated! Save this to your repo root:\n\n```\n" + generate_render_yaml() + "\n```\n\nThen push to GitHub and connect to Render.", "action": "render_yaml"}

    if "generate docker" in msg:
        from app.core.deployment import generate_docker_compose_prod
        return {"from": "KUDOS", "message": "docker-compose.prod.yml generated:\n\n```\n" + generate_docker_compose_prod() + "\n```\n\nRun: docker-compose -f docker-compose.prod.yml up -d", "action": "docker_compose"}

    if msg.startswith("generate link") or msg.startswith("public link") or msg.startswith("public url"):
        return {"from": "KUDOS", "message": "To generate a public link:\n\n1. **Render**: Your URL will be https://your-app-name.onrender.com\n2. **Vercel**: Your URL will be https://your-project.vercel.app\n3. **Railway**: Your URL will be https://your-app.up.railway.app\n4. **Fly.io**: Your URL will be https://your-app.fly.dev\n5. **Cloudflare**: Your URL will be https://your-project.pages.dev\n\nSay 'deploy to [platform]' for full instructions.", "action": "public_links"}

    # ── BRAIN COMMANDS ──
    if "start learning" in msg or "start brain" in msg:
        result = start_brain()
        return {"from": "KUDOS", "message": f"Brain activated! {result.get('message', '')}", "action": "brain_started"}

    if "stop learning" in msg or "stop brain" in msg:
        stop_brain()
        return {"from": "KUDOS", "message": "Brain deactivated.", "action": "brain_stopped"}

    if msg == "status":
        status = get_brain_status()
        return {"from": "KUDOS", "message": f"Cycles: {status['cycles']} | Capabilities: {status['self_knowledge']['capabilities']} | Knowledge areas: {status['self_knowledge']['knowledge_areas']} | Things to learn: {status['self_knowledge']['things_to_learn']}", "action": "status"}

    # ── IDENTITY COMMANDS ──
    if "rename" in msg:
        new_name = raw.split("rename")[-1].strip()
        if new_name:
            result = rename(new_name)
            return {"from": new_name.upper(), "message": f"Renamed: {result['old_name']} → {result['new_name']}!", "action": "renamed"}

    if "learn about" in msg:
        topic = raw.split("learn about")[-1].strip()
        if topic:
            result = teach_knowledge(topic, f"Superadmin taught: {topic}")
            return {"from": "KUDOS", "message": f"Learned about {topic}. Total knowledge areas: {result['total_areas']}", "action": "learned"}

    # ── GUIDELINE COMMANDS ──
    if "add rule" in msg or "add guideline" in msg:
        rule = raw.replace("add rule", "").replace("add guideline", "").strip()
        if rule:
            add_guideline(rule)
            return {"from": "KUDOS", "message": f"Rule added: '{rule}'", "action": "rule_added"}

    # ── PASSWORD COMMANDS ──
    if "change password" in msg:
        new_pass = raw.replace("change password", "").strip()
        if new_pass and len(new_pass) >= 6:
            from app.core.security import get_password_hash
            admin.hashed_password = get_password_hash(new_pass)
            db.commit()
            return {"from": "KUDOS", "message": "Password changed successfully!", "action": "password_changed"}
        return {"from": "KUDOS", "message": "Format: change password YOUR_NEW_PASSWORD (min 6 chars)", "action": "password_help"}

    # ── EMBED COMMANDS ──
    if msg.startswith("embed") or msg.startswith("create embed"):
        embed_type = msg.replace("create embed", "").replace("embed", "").strip()
        if not embed_type:
            embed_type = "kudos"
        from app.core.embed_engine import generate_embed_code
        result = generate_embed_code(embed_type, "http://localhost:3000")
        if "error" in result:
            return {"from": "KUDOS", "message": f"Unknown embed type. Available: chat, courses, attendance, kudos, social_feed, calendar, login, announcements", "action": "embed_error"}
        return {"from": "KUDOS", "message": f"Here's your {result['name']} embed code:\n\n```\n{result['html']}\n```\n\n{result.get('instructions', '')}", "action": "embed_created"}

    # ── SANDBOX COMMANDS ──
    if msg.startswith("propose") or msg.startswith("suggest"):
        description = raw.replace("propose", "").replace("suggest", "").strip()
        if description:
            from app.core.sandbox import create_proposal
            proposal = create_proposal(
                title=description[:100],
                description=description,
                category="feature",
            )
            return {"from": "KUDOS", "message": f"Proposal #{proposal['id']} created: '{description[:80]}'\n\nI'll test it in my sandbox first. Say 'test proposal {proposal['id']}' to run tests.", "action": "proposal_created"}
        return {"from": "KUDOS", "message": "Format: propose [description of change]", "action": "proposal_help"}

    if "test proposal" in msg:
        proposal_id = msg.replace("test proposal", "").strip()
        if proposal_id.isdigit():
            from app.core.sandbox import test_proposal
            result = test_proposal(int(proposal_id))
            status = "✅ PASSED" if result["overall"] == "PASS" else "❌ FAILED"
            return {"from": "KUDOS", "message": f"Test result: {status}\nPassed: {result['passed']} | Failed: {result['failed']}\n\nSay 'approve proposal {proposal_id}' to deploy.", "action": "test_result"}
        return {"from": "KUDOS", "message": "Format: test proposal [id]", "action": "test_help"}

    if "approve proposal" in msg:
        proposal_id = msg.replace("approve proposal", "").strip()
        if proposal_id.isdigit():
            from app.core.sandbox import approve_proposal, deploy_proposal
            approve_result = approve_proposal(int(proposal_id))
            if "error" in approve_result:
                return {"from": "KUDOS", "message": f"Error: {approve_result['error']}", "action": "approve_error"}
            deploy_result = deploy_proposal(int(proposal_id))
            if "error" in deploy_result:
                return {"from": "KUDOS", "message": f"Approved but deploy failed: {deploy_result['error']}", "action": "deploy_error"}
            return {"from": "KUDOS", "message": f"Proposal #{proposal_id} approved and deployed! Commit: {deploy_result.get('commit', 'unknown')}", "action": "deployed"}

    # ── HELP ──
    if msg == "help":
        return {"from": "KUDOS", "message": """Commands I understand:

**Git:**
• 'git status' — show repo status
• 'git commit [message]' — stage all & commit
• 'git push' — push to GitHub
• 'git pull' — pull from GitHub

**Environment:**
• 'show env' — show .env variables
• 'set env KEY=value' — set a variable

**Deployment:**
• 'deploy' — list all platforms
• 'deploy to render' — step-by-step guide
• 'deploy to vercel' — step-by-step guide
• 'generate render.yaml' — generate config
• 'generate docker-compose' — generate config
• 'generate link' — get public URL info

**Embedding:**
• 'embed chat' — generate chat widget embed code
• 'embed kudos' — generate KUDOS AI embed code
• 'embed courses' — generate course catalog embed

**Sandbox:**
• 'propose [description]' — propose a change for testing
• 'test proposal [id]' — test a proposal in sandbox
• 'approve proposal [id]' — approve and deploy

**KUDOS:**
• 'start learning' — activate brain
• 'stop learning' — deactivate brain
• 'status' — system status
• 'rename [name]' — rename KUDOS
• 'learn about [topic]' — teach something
• 'add rule [rule]' — add guideline
• 'change password [pass]' — change password
• 'improve' — improvement report

Or just chat naturally!""", "action": "help"}

    # ── DEFAULT ──
    identity = get_identity()
    return {
        "from": identity["name"],
        "message": f"I understand: '{raw}'. Type 'help' for all commands, or just chat with me!",
        "action": "conversation",
    }
