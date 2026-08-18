#!/usr/bin/env python3
"""kudos — persistent, context-aware REPL for the KUDOS Agency.

NEW — "never worry about quota":
  - Detects Gemini quota / rate-limit errors in agent output.
  - Automatically re-runs the SAME request on your local Ollama model.
  - Offline (Ollama) mode can now edit files too — no more "advisory only".

Modes:
  1) One-shot:   kudos "your request" [flags]
  2) Interactive REPL:  kudos        (stays open until you type: stop)

Interactive commands:
    /help                 show help
    /agent <slug>         pin a specialist (default: agents-orchestrator)
    /agent none           go back to auto-routing
    /status /diff         git status / git diff
    /commit <msg>         git add -A && commit
    /push                 git push
    /deploy               run $KUDOS_DEPLOY_CMD
    /auto                 toggle auto-commit after each turn
    /clear                clear the screen
    stop | /stop | exit   end the session

Configuration (env vars, optional):
    KUDOS_LOCAL_MODEL      Ollama model used for offline/fallback
                           (default: whatever opencode.json points at)
    KUDOS_DEPLOY_CMD       command /deploy runs
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

# Patterns that mean "the cloud model is rate-limited / out of quota".
QUOTA_PATTERNS = [
    r"exceeded your current quota",
    r"quota exceeded",
    r"resource_?exhausted",
    r"rate.?limit",
    r"\b429\b",
    r"too many requests",
    r"generate_content_free_tier_requests",
    r"you have been rate limited",
]


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
# Running an agent — with automatic quota fallback
# --------------------------------------------------------------------------

def _looks_like_quota(output: str) -> bool:
    low = output.lower()
    return any(re.search(p, low) for p in QUOTA_PATTERNS)


def run_agent(agent: str, task: str, online: bool = True, allow_fallback: bool = True):
    """Run an agent. Returns (returncode, output_text). If online mode hits a
    Gemini quota/rate-limit error, automatically retry on local Ollama."""
    os.environ["OPENCODE_PERMISSION"] = json.dumps(ALLOW_ALL_PERMISSION)

    runner = "agency-offline" if not online else "agency-online"
    command = [runner]
    if not online and PROJECT.exists():
        command.append("--project")
    command.extend([agent, task])

    mode_label = "online" if online else "offline"
    print(f"\nLaunching {agent} ({mode_label})...")

    result = subprocess.run(
        command,
        cwd=PROJECT,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)

    combined = (result.stdout or "") + "\n" + (result.stderr or "")

    # Automatic fallback: Gemini quota/rate-limit -> local Ollama.
    if online and allow_fallback and _looks_like_quota(combined):
        print("\n⚠️  Gemini quota / rate-limit detected — falling back to local Ollama...")
        return run_agent(agent, task, online=False, allow_fallback=False)

    return result.returncode, (result.stdout or "")


# --------------------------------------------------------------------------
# Speaking (text-to-speech output via `kudos-speak`)
# --------------------------------------------------------------------------

def extract_spoken(text: str) -> str:
    """Pull the spoken summary (or last few clean lines) out of agent output."""
    marker = "SPOKEN SUMMARY:"
    if marker in text:
        spoken = text.rsplit(marker, 1)[1].strip()
    else:
        clean_lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
            and not line.lstrip().startswith((">", "$", "✱", "→", "#"))
        ]
        spoken = " ".join(clean_lines[-6:]).strip()
    spoken = re.sub(r"\x1b\[[0-9;]*m", "", spoken)
    return spoken[:1800].strip()


def speak_text(text: str) -> None:
    spoken = extract_spoken(text)
    if not spoken:
        print("(nothing to speak)")
        return
    print(f"\n🔊 Speaking…")
    subprocess.run(["kudos-speak", spoken], check=False)


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
        print("  export KUDOS_DEPLOY_CMD='docker compose -f docker-compose.prod.yml up -d --build frontend backend'")


# --------------------------------------------------------------------------
# Interactive REPL
# --------------------------------------------------------------------------

def repl(agents: dict[str, str], online: bool = True) -> int:
    transcript: list[tuple[str, str]] = []
    pinned = "agents-orchestrator"
    auto_commit = False
    speak = False

    def show_help():
        print("""\nKUDOS interactive session (stays open until you type: stop)
  normal text          -> sent to kudos; routes to a specialist, remembers context
                          (auto-falls back to local Ollama if Gemini quota is hit)
  /offline             -> switch to local Ollama (no Gemini quota)
  /online              -> switch back to Gemini
  /speak               -> toggle speaking replies aloud (kudos-speak)
  /agent <slug>        -> pin a specialist (or 'none' to auto-route)
  /status /diff        -> git status / git diff
  /commit <msg>        -> git add -A && git commit -m <msg>
  /push                -> git push
  /deploy              -> run $KUDOS_DEPLOY_CMD
  /auto                -> toggle auto-commit after each turn
  /clear               -> clear on-screen transcript (context kept)
  /help  stop  exit    -> help / end session""")

    def banner():
        print(f"Agent: {pinned}   ·   mode: {'online' if online else 'offline (local)'}   ·   speak: {'on' if speak else 'off'}   ·   auto-commit: {'on' if auto_commit else 'off'}")

    print("\nKUDOS is listening. Type normally, or /help. Say 'stop' to end.")
    banner()
    print("Quota fallback: on (Gemini -> local Ollama)\n")

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
            elif verb == "/offline":
                online = False
                print("Switched to offline (local Ollama).")
                banner()
            elif verb == "/online":
                online = True
                print("Switched to online (Gemini).")
                banner()
            elif verb == "/speak":
                speak = not speak
                print(f"Speaking replies: {'on' if speak else 'off'}")
                banner()
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

        target = pinned
        if target is None:
            target = route(line, agents)[0][1]

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
        rc, out = run_agent(target, task, online=online)

        transcript.append(("user", line))
        if rc != 0:
            print("(agent exited with an error)")
            transcript.append(("kudos", "[agent error]"))

        if speak:
            speak_text(out)

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

    if not request:
        return repl(agents, online=online)

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
    rc, out = run_agent(selected, task, online=online)
    if args.speak:
        speak_text(out)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
