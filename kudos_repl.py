#!/usr/bin/env python3
"""kudos — persistent, context-aware REPL for the KUDOS Agency.

Two modes:

1) One-shot (unchanged):   kudos "your request" [flags]
2) Interactive REPL:       kudos
       - stays OPEN until you type:  stop  (or /stop, exit, quit)
       - remembers the whole conversation (context is passed each turn)
       - routes to a specialist, OR pins one so "kudos controls his agents"
       - built-in commands for committing & deploying so you SEE changes

Interactive commands:
    /help                 show help
    /agent <slug>         pin a specialist (default: agents-orchestrator)
    /agent none           go back to auto-routing
    /status               git status
    /diff                 git diff (unstaged)
    /commit <msg>         git add -A && commit
    /push                 git push
    /deploy               run $KUDOS_DEPLOY_CMD (see below)
    /auto                 toggle auto-commit after each turn
    /clear                clear the on-screen transcript
    stop | /stop | exit   end the session
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

AGENTS_DIR = Path.home() / ".config/opencode/agents-all-270"
PROJECT = Path.home() / "New-project"

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by",
    "do", "for", "from", "help", "i", "in", "is", "it",
    "me", "my", "of", "on", "or", "our", "please", "the",
    "this", "to", "we", "with", "you",
}

SYNONYMS = {
    "login": {"authentication", "identity", "security", "access"},
    "password": {"authentication", "identity", "security"},
    "auth": {"authentication", "identity", "security", "access"},
    "database": {"data", "sql", "backend", "architecture"},
    "postgres": {"database", "sql", "data", "backend"},
    "api": {"backend", "platform", "architecture"},
    "frontend": {"react", "nextjs", "ui", "web"},
    "dashboard": {"frontend", "ui", "ux", "design"},
    "page": {"frontend", "ui", "web"},
    "design": {"ui", "ux", "frontend", "visual"},
    "test": {"testing", "quality", "qa", "api"},
    "bug": {"debugging", "testing", "quality"},
    "error": {"debugging", "testing", "backend"},
    "secure": {"security", "application", "audit"},
    "security": {"secure", "application", "audit", "identity"},
    "docker": {"devops", "deployment", "infrastructure"},
    "deploy": {"devops", "deployment", "infrastructure"},
    "performance": {"optimization", "scalability", "backend"},
    "slow": {"performance", "optimization"},
    "mobile": {"android", "ios", "release"},
    "documentation": {"writer", "docs", "technical"},
    "voice": {"audio", "speech", "tts"},
    "ai": {"llm", "machine", "learning", "agent"},
    "agent": {"ai", "automation", "orchestrator"},
}

ALLOW_ALL_PERMISSION = {
    "external_directory": "allow",
    "read": "allow", "edit": "allow", "write": "allow",
    "glob": "allow", "grep": "allow", "list": "allow",
    "bash": "allow", "task": "allow", "lsp": "allow", "skill": "allow",
    "webfetch": "allow", "websearch": "allow",
    "todoread": "allow", "todowrite": "allow",
}


def tokenize(text: str) -> set[str]:
    words = set(re.findall(r"[a-z0-9]+", text.lower())) - STOP_WORDS
    expanded = set(words)
    for word in words:
        expanded.update(SYNONYMS.get(word, set()))
    return expanded


def load_agents() -> dict[str, str]:
    agents = {}
    if not AGENTS_DIR.exists():
        return agents
    for path in AGENTS_DIR.glob("*.md"):
        agents[path.stem] = path.read_text(encoding="utf-8", errors="replace")
    return agents


def score_agent(request_tokens: set[str], slug: str, content: str) -> int:
    slug_tokens = tokenize(slug.replace("-", " "))
    content_tokens = tokenize(content[:5000])
    score = 12 * len(request_tokens & slug_tokens)
    score += 2 * len(request_tokens & content_tokens)
    joined = " ".join(sorted(request_tokens))
    preferred = [
        (r"security|authentication|password|login|identity", "application-security-engineer"),
        (r"backend|database|postgres|architecture", "backend-architect"),
        (r"api.*test|test.*api", "api-tester"),
        (r"frontend|react|nextjs|web page", "frontend-developer"),
        (r"ui|ux|visual|dashboard|design", "ui-designer"),
        (r"accessibility|screen reader|wcag", "accessibility-auditor"),
        (r"agent|orchestrate|multiple specialists", "agents-orchestrator"),
    ]
    for pattern, preferred_slug in preferred:
        if slug == preferred_slug and re.search(pattern, joined):
            score += 50
    return score


def route(request: str, agents: dict[str, str]):
    tokens = tokenize(request)
    ranked = sorted(
        ((score_agent(tokens, slug, content), slug) for slug, content in agents.items()),
        reverse=True,
    )
    ranked = [(s, slug) for s, slug in ranked if s > 0]
    if ranked:
        return ranked
    fallback = "agents-orchestrator"
    if fallback in agents:
        return [(1, fallback)]
    return [(1, sorted(agents)[0])]


def transcribe_voice() -> str:
    # (unchanged from the original script)
    lock_path = Path.home() / ".config/kudos/voice-lock.json"
    if not lock_path.exists():
        raise RuntimeError("KUDOS voice lock is missing.")
    voice_lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if not voice_lock.get("locked"):
        raise RuntimeError("KUDOS signature voice is not locked.")
    service = "kudos-whisper"
    capture = Path("/tmp/kudos-spoken-command.wav")
    try:
        subprocess.run(["systemctl", "--user", "start", service], check=False)
        ready = False
        for _ in range(20):
            try:
                with urllib.request.urlopen("http://127.0.0.1:8083/health", timeout=2) as r:
                    if r.status == 200:
                        ready = True
                        break
            except Exception:
                time.sleep(0.5)
        if not ready:
            raise RuntimeError("Whisper did not become ready.")
        duration = os.getenv("KUDOS_VOICE_SECONDS", "8")
        device = os.getenv("KUDOS_AUDIO_DEVICE", "plughw:0,0")
        print(f"\nSpeak your request now ({duration} seconds)...")
        subprocess.run(["arecord", "-q", "-D", device, "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", duration, str(capture)], check=False)
        result = subprocess.run(
            ["curl", "-fsS", "-F", f"file=@{capture}", "-F", "language=en", "http://127.0.0.1:8083/transcribe"],
            text=True, capture_output=True, check=False,
        )
        if result.returncode != 0:
            raise RuntimeError("Speech transcription failed.")
        data = json.loads(result.stdout)
        raw = data.get("text", "").strip()
        if not raw:
            raise RuntimeError("No speech recognized.")
        normalized = re.sub(r"^\s*(kudos|who does)\b[\s,]*", "", raw, flags=re.IGNORECASE)
        normalized = re.sub(r"\bdigital compass\b", "Digital Campus", normalized, flags=re.IGNORECASE)
        print("\nWhisper heard:", raw)
        print("KUDOS understood:", normalized)
        return normalized.strip()
    finally:
        subprocess.run(["systemctl", "--user", "stop", service], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        capture.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# Running an agent (shared by one-shot and REPL)
# --------------------------------------------------------------------------

def run_agent(agent: str, task: str, online: bool = True) -> int:
    os.environ["OPENCODE_PERMISSION"] = json.dumps(ALLOW_ALL_PERMISSION)
    runner = "agency-offline" if not online else "agency-online"
    command = [runner]
    if not online and PROJECT.exists():
        command.append("--project")
    command.extend([agent, task])
    print(f"\nLaunching {agent}...")
    return subprocess.run(command, cwd=PROJECT, check=False).returncode


# --------------------------------------------------------------------------
# Git helpers (deterministic, not routed through an agent)
# --------------------------------------------------------------------------

def git_status() -> None:
    subprocess.run(["git", "status", "--short"], cwd=PROJECT)


def git_diff() -> None:
    subprocess.run(["git", "diff"], cwd=PROJECT)


def git_commit(message: str) -> None:
    if not message:
        message = input("Commit message: ").strip()
    if not message:
        print("No commit message; skipped.")
        return
    subprocess.run(["git", "add", "-A"], cwd=PROJECT)
    subprocess.run(["git", "commit", "-m", message], cwd=PROJECT)


def git_push() -> None:
    subprocess.run(["git", "push"], cwd=PROJECT)


def deploy() -> None:
    cmd = os.getenv("KUDOS_DEPLOY_CMD")
    if cmd:
        print(f"Running: {cmd}")
        subprocess.run(cmd, shell=True, cwd=PROJECT)
    else:
        print("No KUDOS_DEPLOY_CMD set.")
        print("Set it to however you deploy, e.g.:")
        print("  export KUDOS_DEPLOY_CMD='docker compose up -d --build'")
        print("  export KUDOS_DEPLOY_CMD='cd frontend && npm run dev'")


# --------------------------------------------------------------------------
# Interactive REPL
# --------------------------------------------------------------------------

def repl(agents: dict[str, str], online: bool = True) -> int:
    transcript: list[tuple[str, str]] = []  # (role, text)
    pinned = "agents-orchestrator"          # "kudos controls his agents"
    auto_commit = False

    def show_help():
        print("""\nKUDOS interactive session (stays open until you type: stop)
  normal text          -> sent to kudos; it routes to a specialist and remembers context
  /agent <slug>        -> pin a specialist (or 'none' to auto-route)
  /status /diff        -> git status / git diff
  /commit <msg>        -> git add -A && git commit -m <msg>
  /push                -> git push
  /deploy              -> run $KUDOS_DEPLOY_CMD
  /auto                -> toggle auto-commit after each turn
  /clear               -> clear on-screen transcript (context kept)
  /help  stop  exit    -> help / end session""")

    print("\nKUDOS is listening. Type normally, or /help. Say 'stop' to end.")
    print(f"Agent: {pinned}   ·   auto-commit: {'on' if auto_commit else 'off'}\n")

    while True:
        try:
            line = input("you › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        low = line.lower()
        if low in ("stop", "/stop", "exit", "/exit", "quit", "/quit"):
            print("Ending session. Goodbye.")
            break

        if line.startswith("/"):
            parts = line.split(maxsplit=1)
            verb = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            if verb == "/help":
                show_help()
            elif verb == "/agent":
                if arg in ("none", ""):
                    pinned = None
                    print("Auto-routing restored.")
                elif arg in agents:
                    pinned = arg
                    print(f"Pinned agent: {arg}")
                else:
                    print(f"Unknown agent: {arg}")
            elif verb == "/status":
                git_status()
            elif verb == "/diff":
                git_diff()
            elif verb == "/commit":
                git_commit(arg)
            elif verb == "/push":
                git_push()
            elif verb == "/deploy":
                deploy()
            elif verb == "/auto":
                auto_commit = not auto_commit
                print(f"Auto-commit: {'on' if auto_commit else 'off'}")
            elif verb == "/clear":
                print("\n" * 40)
            else:
                print(f"Unknown command: {verb} (try /help)")
            continue

        # --- route & build context ---------------------------------------
        target = pinned
        if target is None:
            target = route(line, agents)[0][1]

        # carry conversation context (last ~10 turns, ~5000 chars max)
        if transcript:
            recent = transcript[-10:]
            ctx = "\n".join(f"{r}: {t}" for r, t in recent)
            if len(ctx) > 5000:
                ctx = ctx[-5000:]
            task = (
                "This is a continuing conversation with KUDOS. Earlier turns "
                "(context only — do not redo them):\n"
                f"{ctx}\n\n"
                "Latest request (do this now, editing files directly): "
                f"{line}"
            )
        else:
            task = f"You may edit files. {line}"

        print(f"[routing -> {target}]")
        rc = run_agent(target, task, online=online)

        transcript.append(("user", line))
        if rc != 0:
            print("(agent exited with an error)")
            transcript.append(("kudos", "[agent error]"))

        if auto_commit:
            git_commit(f"kudos: {line[:60]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Control KUDOS Agency using normal English")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--online", action="store_true", help="Use Gemini and OpenCode (default)")
    mode.add_argument("--offline", action="store_true", help="Use local Ollama")
    rw = parser.add_mutually_exclusive_group()
    rw.add_argument("--mode", choices=["read", "write"], default=None)
    rw.add_argument("--apply", action="store_true", help="Alias for --mode write")
    parser.add_argument("--yes", action="store_true", help="Skip APPLY confirmation")
    parser.add_argument("--agent", help="Use a specific specialist")
    parser.add_argument("--dry-run", action="store_true", help="Show routing without launching")
    parser.add_argument("--speak", action="store_true")
    parser.add_argument("--voice", action="store_true")
    parser.add_argument("request", nargs="*", help="Plain-English request")

    args = parser.parse_args()
    agents = load_agents()

    if not agents:
        print("No Agency Agents definitions found.", file=sys.stderr)
        return 1

    request = " ".join(args.request).strip()
    online = not args.offline

    # No request at all -> interactive REPL (persistent, context-aware)
    if not request:
        return repl(agents, online=online)

    # --- one-shot mode (original behavior, plus --yes) -------------------
    if args.voice:
        try:
            request = " ".join(p for p in (request, transcribe_voice()) if p).strip()
        except Exception as error:
            print(f"Voice input failed: {error}", file=sys.stderr)
            return 1

    default_mode = os.getenv("KUDOS_DEFAULT_MODE", "read")
    if args.mode == "write":
        can_edit = True
    elif args.mode == "read":
        can_edit = False
    elif args.apply:
        can_edit = True
    else:
        can_edit = default_mode.strip().lower() == "write"

    local_request = request.lower()
    wants_open = "open" in local_request
    wants_github = "github" in local_request or "repository" in local_request or "repo" in local_request
    wants_campus = "digital campus" in local_request or "campus app" in local_request

    # Only trigger the browser shortcut for *pure* open requests,
    # not for meta-commands like "open a new session".
    if wants_open and wants_github and "session" not in local_request:
        subprocess.Popen(["xdg-open", "https://github.com/mukondakangwa1-lgtm/New-project"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("KUDOS opened your GitHub repository.")
        return 0

    if wants_open and wants_campus and "session" not in local_request and "build" not in local_request:
        subprocess.Popen(["xdg-open", "http://127.0.0.1:3000"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("KUDOS opened Digital Campus.")
        return 0

    ranked = route(request, agents)

    if args.agent:
        if args.agent not in agents:
            print(f"Unknown agent: {args.agent}", file=sys.stderr)
            return 2
        selected = args.agent
    else:
        selected = ranked[0][1]

    print()
    print("KUDOS REQUEST")
    print(f"  Request: {request}")
    print(f"  Agent:   {selected}")
    print(f"  Mode:    {'offline' if args.offline else 'online'}")
    print(f"  Action:  {'may edit files' if can_edit else 'read-only'}")
    print("\nOther likely specialists:")
    for score, slug in ranked[:4]:
        marker = "*" if slug == selected else "-"
        print(f"  {marker} {slug} (score {score})")

    if args.dry_run:
        print("\nDry run only; no model was launched.")
        return 0

    if can_edit:
        if not online:
            print("Offline specialists are advisory only; file editing requires online mode.", file=sys.stderr)
            return 2
        if not args.yes:
            confirmation = input("Type APPLY to allow repository edits: ")
            if confirmation != "APPLY":
                print("Cancelled; no files were modified.")
                return 0
        task = (
            "You may edit files for this request. First inspect the repository, "
            "make the smallest safe change, run relevant tests, and do not commit "
            "or push. User request: " + request
        )
    else:
        task = (
            "READ-ONLY REQUEST: Do not edit, create, rename, or delete files. "
            "Do not commit or push. Inspect only what is necessary and provide an "
            "actionable answer. User request: " + request
        )

    if args.speak:
        task += "\n\nEnd your response with the exact heading 'SPOKEN SUMMARY:' followed by a concise plain-English summary of no more than three sentences."

    print()
    return run_agent(selected, task, online=online)


if __name__ == "__main__":
    raise SystemExit(main())
