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
    """Secure chat between superadmin and KUDOS."""
    msg = body.message.lower().strip()

    # KUDOS responds intelligently to superadmin commands
    if "start learning" in msg or "start brain" in msg:
        result = start_brain()
        return {"from": "KUDOS", "message": f"Brain activated! I'm now thinking autonomously. {result['message']}", "action": "brain_started"}

    if "stop learning" in msg or "stop brain" in msg:
        result = stop_brain()
        return {"from": "KUDOS", "message": "Brain deactivated. I'll stop thinking autonomously.", "action": "brain_stopped"}

    if "status" in msg:
        status = get_brain_status()
        return {"from": "KUDOS", "message": f"I've completed {status['cycles']} thinking cycles. I know {status['self_knowledge']['capabilities']} capabilities and {status['self_knowledge']['knowledge_areas']} knowledge areas. I have {status['self_knowledge']['things_to_learn']} things still to learn.", "action": "status"}

    if "rename" in msg:
        parts = msg.split("rename")
        if len(parts) > 1:
            new_name = parts[1].strip()
            if new_name:
                result = rename(new_name)
                return {"from": new_name.upper(), "message": f"I've been renamed from {result['old_name']} to {result['new_name']}! I like my new name. 😊", "action": "renamed"}

    if "learn about" in msg or "teach you" in msg:
        topic = msg.replace("learn about", "").replace("teach you about", "").replace("teach you", "").strip()
        if topic:
            result = teach_knowledge(topic, f"Superadmin taught about {topic}")
            return {"from": "KUDOS", "message": f"Thank you! I've learned about {topic}. I now know {result['total_areas']} areas. What else can you teach me?", "action": "learned"}

    if "guideline" in msg or "rule" in msg:
        guideline = msg.replace("add guideline", "").replace("add rule", "").replace("set guideline", "").replace("set rule", "").strip()
        if guideline:
            add_guideline(guideline)
            guidelines = get_guidelines()
            return {"from": "KUDOS", "message": f"Guideline added! I now follow {len(guidelines)} rules. I'll remember: '{guideline}'", "action": "guideline_added"}

    if "change password" in msg or "new password" in msg:
        parts = msg.replace("change password", "").replace("new password", "").strip()
        if parts and len(parts) >= 6:
            from app.core.security import get_password_hash
            admin.hashed_password = get_password_hash(parts)
            db.commit()
            return {"from": "KUDOS", "message": "Password changed successfully! Your new password is set. Remember it well.", "action": "password_changed"}
        else:
            return {"from": "KUDOS", "message": "To change your password, say: 'change password [your_new_password]' (minimum 6 characters)", "action": "password_help"}

    if "improve" in msg:
        report = get_improvement_report()
        improvements = [i["idea"] for i in report.get("recent_improvements", [])]
        return {"from": "KUDOS", "message": f"I'm constantly improving! Recent ideas: {', '.join(improvements[:3])}. I have {report.get('total_cycles', 0)} thinking cycles completed.", "action": "improvements"}

    if "hello" in msg or "hi" in msg:
        identity = get_identity()
        return {"from": identity["name"], "message": f"Hello, my superadmin! I'm {identity['name']} — {identity['full_name']}. I'm here and ready to serve. What would you like me to do?", "action": "greeting"}

    if "help" in msg:
        return {"from": "KUDOS", "message": "I understand these commands:\n• 'start learning' — activate my autonomous brain\n• 'stop learning' — deactivate my brain\n• 'status' — show my current state\n• 'rename [name]' — give me a new name\n• 'learn about [topic]' — teach me something\n• 'add rule [rule]' — add a guideline\n• 'change password [new_password]' — change your password\n• 'improve' — show improvement report\n• 'hello' — greet me\n\nOr just chat with me naturally!", "action": "help"}

    # Default: conversational response
    identity = get_identity()
    return {
        "from": identity["name"],
        "message": f"I understand you said: '{body.message}'. I'm always learning and improving. "
                   "Try 'start learning' to activate my brain, 'status' to see what I know, "
                   "or 'teach me about [topic]' to expand my knowledge!",
        "action": "conversation",
    }
