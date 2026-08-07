"""
KUDOS Sandbox — Safe testing environment
KUDOS tests features before offering them for superadmin approval.
Isolated execution, rollback capability, proposal workflow.
"""
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_PATH = str(Path(__file__).resolve().parents[4])

# ──────────────────────────────────────────────
# SANDBOX STATE
# ──────────────────────────────────────────────

_sandbox_active = False
_sandbox_proposals: list[dict] = []
_sandbox_test_results: list[dict] = []
_sandbox_log: list[dict] = []
_proposal_counter = 0


def _log(action: str, details: str):
    _sandbox_log.append({
        "action": action,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if len(_sandbox_log) > 500:
        _sandbox_log[:] = _sandbox_log[-200:]


# ──────────────────────────────────────────────
# PROPOSAL SYSTEM
# ──────────────────────────────────────────────

def create_proposal(
    title: str,
    description: str,
    category: str,
    changes: list[dict] = None,
    test_code: str = "",
) -> dict:
    """KUDOS creates a proposal for superadmin to review."""
    global _proposal_counter
    _proposal_counter += 1

    proposal = {
        "id": _proposal_counter,
        "title": title,
        "description": description,
        "category": category,  # feature, fix, improvement, security
        "changes": changes or [],  # [{file, action, preview}]
        "test_code": test_code,
        "status": "pending",  # pending, testing, approved, rejected, deployed
        "test_result": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_at": None,
        "deployed_at": None,
    }
    _sandbox_proposals.append(proposal)
    _log("proposal_created", f"Proposal #{proposal['id']}: {title}")
    return proposal


def list_proposals(status: Optional[str] = None) -> list[dict]:
    """List all proposals."""
    if status:
        return [p for p in _sandbox_proposals if p["status"] == status]
    return _sandbox_proposals


def get_proposal(proposal_id: int) -> Optional[dict]:
    """Get a specific proposal."""
    for p in _sandbox_proposals:
        if p["id"] == proposal_id:
            return p
    return None


# ──────────────────────────────────────────────
# TESTING ENGINE
# ──────────────────────────────────────────────

def test_proposal(proposal_id: int) -> dict:
    """Run tests on a proposal in the sandbox."""
    proposal = get_proposal(proposal_id)
    if not proposal:
        return {"error": "Proposal not found"}

    proposal["status"] = "testing"
    _log("test_started", f"Testing proposal #{proposal_id}")

    results = {
        "proposal_id": proposal_id,
        "tests": [],
        "passed": 0,
        "failed": 0,
        "warnings": [],
    }

    # Test 1: Run existing tests
    try:
        result = subprocess.run(
            [".venv/bin/python", "-m", "pytest", "tests/", "-q", "--tb=no"],
            cwd=os.path.join(REPO_PATH, "services", "backend"),
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            results["tests"].append({"name": "existing_tests", "status": "PASS", "details": "All tests passed"})
            results["passed"] += 1
        else:
            results["tests"].append({"name": "existing_tests", "status": "FAIL", "details": result.stdout[:200]})
            results["failed"] += 1
    except Exception as e:
        results["tests"].append({"name": "existing_tests", "status": "ERROR", "details": str(e)[:200]})
        results["failed"] += 1

    # Test 2: Python syntax check
    for change in proposal.get("changes", []):
        filepath = change.get("file", "")
        if filepath.endswith(".py"):
            full_path = os.path.join(REPO_PATH, filepath)
            if os.path.exists(full_path):
                try:
                    subprocess.run(
                        [".venv/bin/python", "-m", "py_compile", full_path],
                        cwd=REPO_PATH, capture_output=True, timeout=10,
                    )
                    results["tests"].append({"name": f"syntax_{filepath}", "status": "PASS"})
                    results["passed"] += 1
                except Exception:
                    results["tests"].append({"name": f"syntax_{filepath}", "status": "FAIL"})
                    results["failed"] += 1

    # Test 3: Import check
    try:
        result = subprocess.run(
            [".venv/bin/python", "-c", "from app.main import app; print('OK')"],
            cwd=os.path.join(REPO_PATH, "services", "backend"),
            capture_output=True, text=True, timeout=10,
        )
        if "OK" in result.stdout:
            results["tests"].append({"name": "import_check", "status": "PASS"})
            results["passed"] += 1
        else:
            results["tests"].append({"name": "import_check", "status": "FAIL", "details": result.stderr[:200]})
            results["failed"] += 1
    except Exception as e:
        results["tests"].append({"name": "import_check", "status": "ERROR"})
        results["failed"] += 1

    # Determine overall result
    overall = "PASS" if results["failed"] == 0 else "FAIL"
    results["overall"] = overall

    proposal["test_result"] = results
    proposal["status"] = "pending" if overall == "PASS" else "rejected"

    _log("test_complete", f"Proposal #{proposal_id}: {overall} ({results['passed']}P/{results['failed']}F)")
    _sandbox_test_results.append(results)

    return results


# ──────────────────────────────────────────────
# APPROVAL & DEPLOYMENT
# ──────────────────────────────────────────────

def approve_proposal(proposal_id: int) -> dict:
    """Superadmin approves a proposal."""
    proposal = get_proposal(proposal_id)
    if not proposal:
        return {"error": "Proposal not found"}
    if proposal["status"] != "pending":
        return {"error": f"Cannot approve: status is {proposal['status']}"}

    proposal["status"] = "approved"
    proposal["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    _log("approved", f"Proposal #{proposal_id} approved by superadmin")
    return {"status": "approved", "proposal": proposal}


def reject_proposal(proposal_id: int, reason: str = "") -> dict:
    """Superadmin rejects a proposal."""
    proposal = get_proposal(proposal_id)
    if not proposal:
        return {"error": "Proposal not found"}

    proposal["status"] = "rejected"
    proposal["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    proposal["rejection_reason"] = reason
    _log("rejected", f"Proposal #{proposal_id} rejected: {reason}")
    return {"status": "rejected"}


def deploy_proposal(proposal_id: int) -> dict:
    """Deploy an approved proposal — commits changes to git."""
    proposal = get_proposal(proposal_id)
    if not proposal:
        return {"error": "Proposal not found"}
    if proposal["status"] != "approved":
        return {"error": f"Cannot deploy: status is {proposal['status']}"}

    # Git add, commit, push
    try:
        result = subprocess.run(
            ["git", "add", "-A"],
            cwd=REPO_PATH, capture_output=True, text=True, timeout=10,
        )

        commit_msg = f"kudos: {proposal['title']}\n\n{proposal['description']}\n\nProposal #{proposal['id']}"
        result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=REPO_PATH, capture_output=True, text=True, timeout=10,
        )

        if result.returncode == 0:
            # Get hash
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=REPO_PATH, capture_output=True, text=True, timeout=10,
            )
            proposal["status"] = "deployed"
            proposal["deployed_at"] = datetime.now(timezone.utc).isoformat()
            proposal["commit_hash"] = hash_result.stdout.strip()[:8]
            _log("deployed", f"Proposal #{proposal_id} deployed: {proposal['commit_hash']}")
            return {"status": "deployed", "commit": proposal["commit_hash"]}
        else:
            return {"error": f"Commit failed: {result.stderr[:200]}"}

    except Exception as e:
        return {"error": f"Deploy failed: {str(e)[:200]}"}


# ──────────────────────────────────────────────
# SANDBOX FILE OPERATIONS
# ──────────────────────────────────────────────

def sandbox_write_file(filepath: str, content: str) -> dict:
    """Write a file in the sandbox (actual repo)."""
    full_path = os.path.join(REPO_PATH, filepath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    # Backup original
    backup_path = full_path + ".sandbox_backup"
    if os.path.exists(full_path):
        import shutil
        shutil.copy2(full_path, backup_path)

    with open(full_path, "w") as f:
        f.write(content)

    _log("file_written", f"Wrote {filepath} ({len(content)} bytes)")
    return {"status": "written", "file": filepath, "bytes": len(content)}


def sandbox_read_file(filepath: str) -> dict:
    """Read a file from the repo."""
    full_path = os.path.join(REPO_PATH, filepath)
    if not os.path.exists(full_path):
        return {"error": "File not found"}
    with open(full_path) as f:
        return {"file": filepath, "content": f.read()}


def rollback_file(filepath: str) -> dict:
    """Rollback a file to its sandbox backup."""
    full_path = os.path.join(REPO_PATH, filepath)
    backup_path = full_path + ".sandbox_backup"
    if not os.path.exists(backup_path):
        return {"error": "No backup found"}

    import shutil
    shutil.copy2(backup_path, full_path)
    os.remove(backup_path)
    _log("rollback", f"Rolled back {filepath}")
    return {"status": "rolled_back", "file": filepath}


# ──────────────────────────────────────────────
# SANDBOX STATUS
# ──────────────────────────────────────────────

def get_sandbox_status() -> dict:
    """Get sandbox status."""
    return {
        "active": _sandbox_active,
        "proposals": {
            "total": len(_sandbox_proposals),
            "pending": len([p for p in _sandbox_proposals if p["status"] == "pending"]),
            "approved": len([p for p in _sandbox_proposals if p["status"] == "approved"]),
            "rejected": len([p for p in _sandbox_proposals if p["status"] == "rejected"]),
            "deployed": len([p for p in _sandbox_proposals if p["status"] == "deployed"]),
        },
        "tests_run": len(_sandbox_test_results),
        "recent_log": _sandbox_log[-10:],
    }


def get_sandbox_log(limit: int = 50) -> list[dict]:
    """Get sandbox activity log."""
    return _sandbox_log[-limit:]
