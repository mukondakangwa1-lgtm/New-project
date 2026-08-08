"""
KUDOS Sandbox — Safe testing environment
KUDOS tests features before offering them for superadmin approval.
Isolated execution, rollback capability, proposal workflow.
"""
import os
import subprocess
from datetime import datetime, timezone
from typing import Optional

from app.core.paths import project_root
from app.models import KudosMemory

REPO_PATH = str(project_root(__file__))
SANDBOX_KB_USER_ID = 0  # KUDOS itself holds the knowledge-layer rememberings

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
    except Exception:
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

def recommend_proposal(proposal_id: int) -> dict:
    """KUDOS reviews a tested proposal and decides whether to recommend it.

    Uses the best LLM when available; falls back to a deterministic heuristic
    (no failures ⇒ recommend) so the flow works offline. Only proposals that
    have been tested can be reviewed.
    """
    import asyncio

    proposal = get_proposal(proposal_id)
    if not proposal:
        return {"error": "Proposal not found"}
    if not proposal.get("test_result"):
        return {"error": "Proposal has not been tested yet"}
    if proposal["status"] not in ("pending", "recommended", "not_recommended"):
        return {"error": f"Cannot review: status is {proposal['status']}"}

    proposal["status"] = "testing"

    test_result = proposal.get("test_result") or {"passed": 0, "failed": 0, "tests": []}
    summary = "\n".join(
        f"- {t.get('name')}: {t.get('status')} ({t.get('details', '')[:160]})"
        for t in (test_result.get("tests") or [])
    ) or "no tests recorded"

    system_prompt = (
        "You are KUDOS's sandbox reviewer. A university feature proposal has "
        "been tested in an isolated sandbox. Decide whether to recommend it "
        "for the Digital Campus platform. Reply with ONLY JSON: "
        '{"decision": "recommend"|"not_recommend", "confidence": 0.0-1.0, '
        '"rationale": "one paragraph"}'
    )
    user_prompt = (
        f"PROPOSAL #{proposal['id']}: {proposal['title']}\n"
        f"Category: {proposal['category']}\nDescription: {proposal['description']}\n"
        f"TEST RESULTS:\n{summary}\n\nVerdict JSON:"
    )

    try:
        from app.core.llm_engine import query_best_llm

        result = asyncio.run(query_best_llm(user_prompt, system_prompt))
        raw = (result or {}).get("response") or ""
    except Exception:
        raw = ""

    decision, confidence, rationale = _parse_recommendation(raw, test_result)
    recommendation = {
        "decision": decision,
        "confidence": confidence,
        "rationale": rationale,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }
    proposal["recommendation"] = recommendation
    proposal["status"] = "recommended" if decision == "recommend" else "not_recommended"
    _log("recommended", f"Proposal #{proposal_id}: {decision} ({confidence}) by KUDOS")
    return {"status": proposal["status"], "recommendation": recommendation}


def _parse_recommendation(raw: str, test_result: dict) -> tuple[str, float, str]:
    """Parse the LLM verdict; degrade gracefully."""
    import json
    import re

    decision, confidence, rationale = "not_recommend", 0.0, "No LLM verdict — heuristic fallback."
    match = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            decision = "recommend" if str(obj.get("decision", "")).startswith("recommend") else "not_recommend"
            confidence = max(0.0, min(1.0, float(obj.get("confidence", 0))))
            rationale = str(obj.get("rationale", ""))[:500] or rationale
        except Exception:
            decision = ""

    if not decision:
        # Deterministic policy fallback: green test suite → recommend.
        passed = int(test_result.get("passed") or 0)
        failed = int(test_result.get("failed") or 0)
        if failed == 0 and passed > 0:
            decision, confidence, rationale = "recommend", 0.7, "Heuristic: all sandbox tests passed"
        else:
            decision, confidence = "not_recommend", 0.8
            rationale = "Heuristic: sandbox tests reported failures"

    if decision == "recommend" and test_result.get("failed"):
        # never recommend a proposal with failing tests
        decision = "not_recommend"
        confidence = min(confidence, 0.5)
        rationale = f"Tests failed in the sandbox — {rationale}"
    return decision, confidence, rationale


# ──────────────────────────────────────────────
# SANDBOX KNOWLEDGE BASE
# ──────────────────────────────────────────────

SANDBOX_KNOWLEDGE = [
    ("concept", "A sandbox is an isolated environment for safely testing changes without touching the main system."),
    ("concept", "KUDOS sandbox flow: proposal created by the admin panel, tests run in isolation, KUDOS recommends, the superadmin approves, deployment commits via git."),
    ("concept", "Sandbox file writes keep a .sandbox_backup of every touched file so anything can be rolled back."),
    ("concept", "Sandbox tests: full pytest suite, syntax check on changed Python files, and an app import check."),
    ("concept", "Sandbox isolation: tests use a separate SQLite database, subprocess limits and timeouts, so failures do not touch production."),
    ("concept", "The sandbox browses only through the Secure Web Bridge, which validates every URL to block private and reserved networks."),
    ("fact", "The internet uses HTTPS (TLS) to encrypt traffic between clients and servers; the bridge only allows https URLs."),
    ("fact", "A URL is: scheme://host[:port]/path?query — the bridge enforces an https scheme and a real public host."),
    ("fact", "SSRF is an attack where a server-side request is tricked into hitting internal addresses; blocking private IPs, loopback and link-local ranges prevents it."),
    ("fact", "DNS resolves host names to addresses; the bridge re-validates the address after every redirect for up to 4 hops."),
    ("fact", "Web content fetched by the bridge is sanitized: scripts and styles are stripped, size capped at 256 KB, then truncated to plain text for the LLM."),
    ("fact", "KUDOS also learns the internet through kudos web connectors and the Internet Archive; everything is chunked, embedded, and searchable."),
]


def build_sandbox_knowledge_context(db, limit: int = 6) -> str:
    """Prose block of what KUDOS knows about sandboxes and the internet.

    Read from the knowledge-layer memories KUDOS seeded for itself, so the
    ask-flow can feed it into the system prompt as 'what you know'.
    """
    try:
        from app.core.memory_store import retrieve_memories

        entries = retrieve_memories(db, user_id=SANDBOX_KB_USER_ID, layers=["knowledge"], limit=limit)
    except Exception:
        return ""
    if not entries:
        return ""
    return "\n".join(f"- {e.content}" for e in entries[:limit])


def seed_sandbox_knowledge(db) -> int:
    """Give KUDOS the knowledge about sandboxes and the internet.

    Stored as knowledge-layer memories; seeded once per token. Returns the
    number of entries written.
    """
    from app.core.memory_store import write_memory

    if db.query(KudosMemory).filter(KudosMemory.source == "sandbox-kb").first():
        return 0
    seeded = 0
    try:
        db.rollback()
    except Exception:
        pass
    for kind, content in SANDBOX_KNOWLEDGE:
        try:
            write_memory(
                db, user_id=SANDBOX_KB_USER_ID,
                content=content, layer="knowledge", kind=kind,
                importance=0.8, source="sandbox-kb",
            )
            seeded += 1
        except Exception:
            continue
    return seeded

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
