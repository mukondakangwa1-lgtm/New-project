"""
KUDOS Shield — Self-protection, self-healing, intrusion detection, backup
Makes KUDOS truly capable of protecting itself and any device it runs on.
"""
import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ──────────────────────────────────────────────
# SHIELD STATE
# ──────────────────────────────────────────────

_shield_active = False
_shield_thread: Optional[threading.Thread] = None
_shield_log: list[dict] = []
_threat_log: list[dict] = []
_backup_log: list[dict] = []
_healing_log: list[dict] = []

# Intrusion detection
_request_tracker: dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
_blocked_ips: set = set()
_RATE_LIMIT = 100  # requests per minute per IP
_RATE_WINDOW = 60  # seconds

# File integrity baseline
_file_hashes: dict[str, str] = {}
_critical_files = [
    "services/backend/app/main.py",
    "services/backend/app/core/database.py",
    "services/backend/app/core/security.py",
    "services/backend/app/core/deps.py",
    "services/backend/app/models.py",
    "services/backend/app/core/kudos_shield.py",
    "services/backend/app/core/kudos_identity.py",
    "services/backend/app/core/kudos_brain.py",
]

# Backup config
BACKUP_DIR = "backups"
MAX_BACKUPS = 10
BACKUP_INTERVAL = 3600  # 1 hour


def _get_repo_path():
    return str(Path(__file__).parent.parent.parent.parent)


def _log_shield(category: str, message: str, severity: str = "info", details: dict = None):
    """Log a shield event."""
    entry = {
        "category": category,
        "message": message,
        "severity": severity,
        "details": details or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _shield_log.append(entry)
    if len(_shield_log) > 1000:
        _shield_log[:] = _shield_log[-500:]

    if severity in ("warning", "critical"):
        _threat_log.append(entry)
        if len(_threat_log) > 200:
            _threat_log[:] = _threat_log[-100:]


# ──────────────────────────────────────────────
# FILE INTEGRITY MONITORING
# ──────────────────────────────────────────────

def _compute_hash(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    try:
        with open(filepath, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except FileNotFoundError:
        return "MISSING"


def _baseline_files():
    """Create baseline hashes of critical files."""
    global _file_hashes
    repo = _get_repo_path()
    for rel_path in _critical_files:
        full_path = os.path.join(repo, rel_path)
        _file_hashes[rel_path] = _compute_hash(full_path)
    _log_shield("integrity", f"Baseline established for {len(_file_hashes)} critical files")


def _check_integrity() -> list[dict]:
    """Check if critical files have been tampered with."""
    violations = []
    repo = _get_repo_path()
    for rel_path, expected_hash in _file_hashes.items():
        full_path = os.path.join(repo, rel_path)
        actual_hash = _compute_hash(full_path)
        if actual_hash != expected_hash:
            violations.append({
                "file": rel_path,
                "expected": expected_hash[:16],
                "actual": actual_hash[:16],
                "status": "TAMPERED" if actual_hash != "MISSING" else "DELETED",
            })
            _log_shield("integrity", f"File tampered: {rel_path}", "critical", {
                "expected": expected_hash[:16], "actual": actual_hash[:16]
            })
    return violations


def update_baseline():
    """Update baseline after authorized changes."""
    _baseline_files()
    return {"status": "updated", "files": len(_file_hashes)}


# ──────────────────────────────────────────────
# INTRUSION DETECTION
# ──────────────────────────────────────────────

def track_request(ip: str, path: str, method: str, status_code: int):
    """Track a request for intrusion detection."""
    now = time.time()
    _request_tracker[ip].append({
        "path": path,
        "method": method,
        "status": status_code,
        "time": now,
    })

    # Clean old entries
    while _request_tracker[ip] and _request_tracker[ip][0]["time"] < now - _RATE_WINDOW:
        _request_tracker[ip].popleft()

    # Rate limit check
    if len(_request_tracker[ip]) > _RATE_LIMIT:
        if ip not in _blocked_ips:
            _blocked_ips.add(ip)
            _log_shield("intrusion", f"IP {ip} rate limited ({len(_request_tracker[ip])} requests/min)", "warning")

    # Detect suspicious patterns
    recent = list(_request_tracker[ip])
    failed_logins = sum(1 for r in recent if r["path"] == "/api/v1/auth/login" and r["status"] == 401)
    if failed_logins > 5:
        _log_shield("intrusion", f"Brute force attempt from {ip}: {failed_logins} failed logins", "critical", {"ip": ip})

    # Detect path scanning
    unique_paths = set(r["path"] for r in recent)
    if len(unique_paths) > 30:
        _log_shield("intrusion", f"Path scanning from {ip}: {len(unique_paths)} unique paths", "warning", {"ip": ip})


def is_blocked(ip: str) -> bool:
    """Check if an IP is blocked."""
    return ip in _blocked_ips


def unblock_ip(ip: str):
    """Unblock an IP."""
    _blocked_ips.discard(ip)
    _log_shield("intrusion", f"IP {ip} unblocked", "info")


def get_blocked_ips() -> list[str]:
    """Get list of blocked IPs."""
    return list(_blocked_ips)


def get_threat_log(limit: int = 50) -> list[dict]:
    """Get threat log."""
    return _threat_log[-limit:]


# ──────────────────────────────────────────────
# SELF-HEALING
# ──────────────────────────────────────────────

def _check_and_heal():
    """Self-diagnosis and healing cycle."""
    repo = _get_repo_path()

    # 1. Check database integrity
    try:
        from app.core.database import SessionLocal
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        _log_shield("health", "Database: OK", "info")
    except Exception as e:
        _log_shield("health", f"Database: ERROR - {str(e)[:100]}", "critical")
        _heal_database()

    # 2. Check disk space
    try:
        stat = shutil.disk_usage(repo)
        free_gb = stat.free / (1024 ** 3)
        if free_gb < 1:
            _log_shield("health", f"Low disk space: {free_gb:.1f}GB free", "warning")
            _cleanup_disk(repo)
        else:
            _log_shield("health", f"Disk space: {free_gb:.1f}GB free", "info")
    except Exception:
        pass

    # 3. Check memory usage
    try:
        import psutil
        mem = psutil.virtual_memory()
        if mem.percent > 90:
            _log_shield("health", f"High memory usage: {mem.percent}%", "warning")
        else:
            _log_shield("health", f"Memory: {mem.percent}% used", "info")
    except ImportError:
        # psutil not installed, use /proc
        try:
            with open("/proc/meminfo") as f:
                lines = f.readlines()
                total = int(lines[0].split()[1])
                available = int(lines[2].split()[1])
                used_pct = round((1 - available / total) * 100, 1)
                _log_shield("health", f"Memory: {used_pct}% used", "info" if used_pct < 90 else "warning")
        except Exception:
            pass

    # 4. Check if critical services are running
    _log_shield("health", "Self-healing cycle complete", "info")


def _heal_database():
    """Attempt to heal database issues."""
    try:
        from app.core.database import engine, Base
        Base.metadata.create_all(bind=engine)
        _log_shield("healing", "Database tables recreated", "info")
    except Exception as e:
        _log_shield("healing", f"Database healing failed: {str(e)[:100]}", "critical")


def _cleanup_disk(repo: str):
    """Clean up disk space."""
    cleaned = 0
    # Remove __pycache__
    for root, dirs, files in os.walk(repo):
        if "__pycache__" in dirs:
            pycache = os.path.join(root, "__pycache__")
            try:
                shutil.rmtree(pycache)
                cleaned += 1
            except Exception:
                pass
    # Remove old backups
    backup_path = os.path.join(repo, BACKUP_DIR)
    if os.path.exists(backup_path):
        backups = sorted(os.listdir(backup_path))
        while len(backups) > MAX_BACKUPS:
            old = backups.pop(0)
            try:
                os.remove(os.path.join(backup_path, old))
                cleaned += 1
            except Exception:
                pass

    _log_shield("healing", f"Cleaned up {cleaned} items", "info")


# ──────────────────────────────────────────────
# BACKUP SYSTEM
# ──────────────────────────────────────────────

def _create_backup():
    """Create a backup of the knowledge base and critical data."""
    repo = _get_repo_path()
    backup_dir = os.path.join(repo, BACKUP_DIR)
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"kudos_backup_{timestamp}.json")

    try:
        from app.core.database import SessionLocal
        from app.models import KudosDocument, KudosChunk, KudosWebKnowledge, KudosConversation, KudosMessage

        db = SessionLocal()

        backup_data = {
            "timestamp": timestamp,
            "documents": [],
            "web_knowledge": [],
            "conversations": [],
            "file_hashes": _file_hashes,
        }

        # Backup documents
        for doc in db.query(KudosDocument).all():
            backup_data["documents"].append({
                "title": doc.title,
                "filename": doc.filename,
                "file_type": doc.file_type,
                "content": doc.content[:10000],  # Limit size
                "summary": doc.summary,
                "tags": doc.tags,
            })

        # Backup web knowledge
        for wk in db.query(KudosWebKnowledge).filter(KudosWebKnowledge.is_approved == True).all():
            backup_data["web_knowledge"].append({
                "url": wk.url,
                "title": wk.title,
                "summary": wk.summary,
                "content": wk.content[:5000],
            })

        db.close()

        with open(backup_file, "w") as f:
            json.dump(backup_data, f, indent=2, default=str)

        size_mb = os.path.getsize(backup_file) / (1024 * 1024)
        _log_shield("backup", f"Backup created: {backup_file} ({size_mb:.1f}MB)", "info")
        _backup_log.append({"file": backup_file, "timestamp": timestamp, "size_mb": round(size_mb, 1)})

        # Cleanup old backups
        backups = sorted(os.listdir(backup_dir))
        while len(backups) > MAX_BACKUPS:
            old = backups.pop(0)
            os.remove(os.path.join(backup_dir, old))

        return {"status": "created", "file": backup_file, "size_mb": round(size_mb, 1)}

    except Exception as e:
        _log_shield("backup", f"Backup failed: {str(e)[:100]}", "critical")
        return {"status": "failed", "error": str(e)[:200]}


def restore_backup(backup_file: str) -> dict:
    """Restore from a backup."""
    repo = _get_repo_path()
    full_path = os.path.join(repo, BACKUP_DIR, backup_file)

    if not os.path.exists(full_path):
        return {"error": "Backup file not found"}

    try:
        with open(full_path) as f:
            data = json.load(f)

        from app.core.database import SessionLocal
        from app.models import KudosDocument, KudosWebKnowledge

        db = SessionLocal()

        restored = 0
        for doc_data in data.get("documents", []):
            existing = db.query(KudosDocument).filter(KudosDocument.title == doc_data["title"]).first()
            if not existing:
                db.add(KudosDocument(
                    uploaded_by=1,  # admin
                    title=doc_data["title"],
                    filename=doc_data.get("filename", ""),
                    file_type=doc_data.get("file_type", ""),
                    content=doc_data.get("content", ""),
                    summary=doc_data.get("summary", ""),
                    tags=doc_data.get("tags", ""),
                    is_approved=True,
                ))
                restored += 1

        for wk_data in data.get("web_knowledge", []):
            existing = db.query(KudosWebKnowledge).filter(KudosWebKnowledge.url == wk_data["url"]).first()
            if not existing:
                db.add(KudosWebKnowledge(
                    url=wk_data["url"],
                    title=wk_data["title"],
                    summary=wk_data.get("summary", ""),
                    content=wk_data.get("content", ""),
                    is_approved=True,
                    learned_by=1,
                ))
                restored += 1

        db.commit()
        db.close()

        _log_shield("backup", f"Restored {restored} items from {backup_file}", "info")
        return {"status": "restored", "items": restored}

    except Exception as e:
        return {"error": f"Restore failed: {str(e)[:200]}"}


def list_backups() -> list[dict]:
    """List available backups."""
    repo = _get_repo_path()
    backup_dir = os.path.join(repo, BACKUP_DIR)
    if not os.path.exists(backup_dir):
        return []

    backups = []
    for f in sorted(os.listdir(backup_dir)):
        if f.endswith(".json"):
            full = os.path.join(backup_dir, f)
            backups.append({
                "filename": f,
                "size_mb": round(os.path.getsize(full) / (1024 * 1024), 1),
                "created": datetime.fromtimestamp(os.path.getctime(full)).isoformat(),
            })
    return backups


# ──────────────────────────────────────────────
# PERFORMANCE MONITORING
# ──────────────────────────────────────────────

_performance_stats = {
    "total_requests": 0,
    "total_errors": 0,
    "avg_response_time_ms": 0,
    "response_times": deque(maxlen=100),
}


def track_performance(response_time_ms: float, is_error: bool = False):
    """Track request performance."""
    _performance_stats["total_requests"] += 1
    if is_error:
        _performance_stats["total_errors"] += 1
    _performance_stats["response_times"].append(response_time_ms)
    times = list(_performance_stats["response_times"])
    _performance_stats["avg_response_time_ms"] = round(sum(times) / len(times), 1) if times else 0


def get_performance_stats() -> dict:
    """Get performance statistics."""
    times = list(_performance_stats["response_times"])
    return {
        "total_requests": _performance_stats["total_requests"],
        "total_errors": _performance_stats["total_errors"],
        "error_rate": round(_performance_stats["total_errors"] / max(_performance_stats["total_requests"], 1) * 100, 1),
        "avg_response_time_ms": _performance_stats["avg_response_time_ms"],
        "p95_response_time_ms": round(sorted(times)[int(len(times) * 0.95)] if len(times) > 10 else 0, 1),
        "active_connections": len(_request_tracker),
        "blocked_ips": len(_blocked_ips),
    }


# ──────────────────────────────────────────────
# SHIELD CONTROL
# ──────────────────────────────────────────────

def _shield_cycle():
    """Main shield monitoring cycle."""
    while _shield_active:
        try:
            _check_and_heal()
            violations = _check_integrity()
            if violations:
                _log_shield("integrity", f"Found {len(violations)} integrity violations", "critical")

            # Auto-backup every hour
            if len(_backup_log) == 0 or _backup_log[-1]["timestamp"] < (datetime.now(timezone.utc) - timedelta(seconds=BACKUP_INTERVAL)).strftime("%Y%m%d_%H%M%S"):
                _create_backup()

        except Exception as e:
            _log_shield("shield", f"Shield cycle error: {str(e)[:100]}", "warning")

        time.sleep(300)  # Check every 5 minutes


from datetime import timedelta


def start_shield():
    """Start the shield protection system."""
    global _shield_active, _shield_thread
    if _shield_active:
        return {"status": "already_active"}

    _shield_active = True
    _baseline_files()

    _shield_thread = threading.Thread(target=_shield_cycle, daemon=True)
    _shield_thread.start()

    _log_shield("shield", "KUDOS Shield activated — protecting the system", "info")
    return {"status": "activated", "message": "Shield is now active"}


def stop_shield():
    """Stop the shield."""
    global _shield_active
    _shield_active = False
    _log_shield("shield", "Shield deactivated", "info")
    return {"status": "deactivated"}


def get_shield_status() -> dict:
    """Get shield status."""
    return {
        "active": _shield_active,
        "protected_files": len(_file_hashes),
        "blocked_ips": len(_blocked_ips),
        "threat_count": len(_threat_log),
        "backup_count": len(_backup_log),
        "last_backup": _backup_log[-1] if _backup_log else None,
        "performance": get_performance_stats(),
        "recent_threats": _threat_log[-5:],
        "recent_healing": _healing_log[-5:],
    }


def get_shield_log(limit: int = 50) -> list[dict]:
    """Get shield activity log."""
    return _shield_log[-limit:]
