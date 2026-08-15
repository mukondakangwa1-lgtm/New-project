#!/usr/bin/env python3
"""Natural-language controller for the KUDOS Agency.

READ/WRITE MODE (added):
  kudos --mode write "..."   -> agent may edit files
  kudos --mode read  "..."   -> read-only (default)
  kudos --apply "..."        -> alias for --mode write
  kudos --apply --yes "..."  -> write, skip the APPLY confirmation

Persistent default (optional): export KUDOS_DEFAULT_MODE=write
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

AGENTS_DIR = (
    Path.home()
    / ".config/opencode/agents-all-270"
)
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


def tokenize(text: str) -> set[str]:
    words = set(
        re.findall(r"[a-z0-9]+", text.lower())
    )
    words -= STOP_WORDS

    expanded = set(words)

    for word in words:
        expanded.update(SYNONYMS.get(word, set()))

    return expanded


def load_agents() -> dict[str, str]:
    agents = {}

    if not AGENTS_DIR.exists():
        return agents

    for path in AGENTS_DIR.glob("*.md"):
        agents[path.stem] = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

    return agents


def score_agent(
    request_tokens: set[str],
    slug: str,
    content: str,
) -> int:
    slug_tokens = tokenize(slug.replace("-", " "))
    content_tokens = tokenize(content[:5000])

    score = 0
    score += 12 * len(request_tokens & slug_tokens)
    score += 2 * len(request_tokens & content_tokens)

    joined = " ".join(sorted(request_tokens))

    preferred = [
        (
            r"security|authentication|password|login|identity",
            "application-security-engineer",
        ),
        (
            r"backend|database|postgres|architecture",
            "backend-architect",
        ),
        (
            r"api.*test|test.*api",
            "api-tester",
        ),
        (
            r"frontend|react|nextjs|web page",
            "frontend-developer",
        ),
        (
            r"ui|ux|visual|dashboard|design",
            "ui-designer",
        ),
        (
            r"accessibility|screen reader|wcag",
            "accessibility-auditor",
        ),
        (
            r"agent|orchestrate|multiple specialists",
            "agents-orchestrator",
        ),
    ]

    for pattern, preferred_slug in preferred:
        if (
            slug == preferred_slug
            and re.search(pattern, joined)
        ):
            score += 50

    return score


def route(request: str, agents: dict[str, str]):
    tokens = tokenize(request)

    ranked = sorted(
        (
            (
                score_agent(
                    tokens,
                    slug,
                    content,
                ),
                slug,
            )
            for slug, content in agents.items()
        ),
        reverse=True,
    )

    ranked = [
        (score, slug)
        for score, slug in ranked
        if score > 0
    ]

    if ranked:
        return ranked

    fallback = "agents-orchestrator"

    if fallback in agents:
        return [(1, fallback)]

    return [(1, sorted(agents)[0])]


def transcribe_voice() -> str:
    """Record English speech and transcribe it locally."""
    lock_path = (
        Path.home()
        / ".config/kudos/voice-lock.json"
    )

    if not lock_path.exists():
        raise RuntimeError(
            "KUDOS voice lock is missing."
        )

    voice_lock = json.loads(
        lock_path.read_text(encoding="utf-8")
    )

    if not voice_lock.get("locked"):
        raise RuntimeError(
            "KUDOS signature voice is not locked."
        )

    if voice_lock.get("provider") != "fish":
        raise RuntimeError(
            "Protected Fish signature is unavailable."
        )

    print(
        "Protected output voice:",
        voice_lock["provider_voice_id"],
    )
    print(
        "Whisper is input-only and cannot change "
        "the protected voice."
    )

    service = "kudos-whisper"
    capture = Path("/tmp/kudos-spoken-command.wav")
    transcription = Path(
        "/tmp/kudos-spoken-command.json"
    )

    try:
        started = subprocess.run(
            [
                "systemctl",
                "--user",
                "start",
                service,
            ],
            check=False,
        )

        if started.returncode != 0:
            raise RuntimeError(
                "Could not start local Whisper."
            )

        health_url = (
            "http:"
            + "//127.0.0.1:8083/health"
        )

        ready = False

        for _ in range(20):
            try:
                with urllib.request.urlopen(
                    health_url,
                    timeout=2,
                ) as response:
                    ready = response.status == 200
                    if ready:
                        break
            except Exception:
                time.sleep(0.5)

        if not ready:
            raise RuntimeError(
                "Whisper did not become ready."
            )

        duration = os.getenv(
            "KUDOS_VOICE_SECONDS",
            "8",
        )
        device = os.getenv(
            "KUDOS_AUDIO_DEVICE",
            "plughw:0,0",
        )

        print()
        print(
            f"Speak your request now "
            f"({duration} seconds)..."
        )

        recorded = subprocess.run(
            [
                "arecord",
                "-q",
                "-D",
                device,
                "-f",
                "S16_LE",
                "-r",
                "16000",
                "-c",
                "1",
                "-d",
                duration,
                str(capture),
            ],
            check=False,
        )

        if recorded.returncode != 0:
            raise RuntimeError(
                "Microphone recording failed."
            )

        transcribe_url = (
            "http:"
            + "//127.0.0.1:8083/transcribe"
        )

        result = subprocess.run(
            [
                "curl",
                "-fsS",
                "-F",
                f"file=@{capture}",
                "-F",
                "language=en",
                transcribe_url,
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(
                "Speech transcription failed: "
                + result.stderr.strip()
            )

        transcription.write_text(
            result.stdout,
            encoding="utf-8",
        )

        data = json.loads(result.stdout)
        raw_text = data.get("text", "").strip()

        if not raw_text:
            raise RuntimeError(
                "No speech was recognized."
            )

        normalized = raw_text

        normalized = re.sub(
            r"^\s*(kudos|who does)\b[\s,]*",
            "",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(
            r"\bdigital compass\b",
            "Digital Campus",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(
            r"\bback in\b",
            "backend",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(
            r"\bfront end\b",
            "frontend",
            normalized,
            flags=re.IGNORECASE,
        )

        print()
        print("Whisper heard:", raw_text)
        print("KUDOS understood:", normalized)

        return normalized.strip()

    finally:
        subprocess.run(
            [
                "systemctl",
                "--user",
                "stop",
                service,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

        capture.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Control KUDOS Agency using normal English"
        )
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--online",
        action="store_true",
        help="Use Gemini and OpenCode (default)",
    )
    mode.add_argument(
        "--offline",
        action="store_true",
        help="Use local Ollama",
    )

    parser.add_argument(
        "--agent",
        help="Use a specific specialist",
    )

    # --- READ/WRITE SWITCH ------------------------------------------------
    rw = parser.add_mutually_exclusive_group()
    rw.add_argument(
        "--mode",
        choices=["read", "write"],
        default=None,
        help="read-only or read-write (overrides KUDOS_DEFAULT_MODE)",
    )
    rw.add_argument(
        "--apply",
        action="store_true",
        help="Alias for --mode write: allow the selected online agent to edit files",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the APPLY confirmation prompt (write mode only)",
    )
    # ----------------------------------------------------------------------

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show routing without launching a model",
    )
    parser.add_argument(
        "--speak",
        action="store_true",
        help="Speak the final answer with KUDOS's protected voice",
    )
    parser.add_argument(
        "--voice",
        action="store_true",
        help="Speak the request using local Whisper",
    )
    parser.add_argument(
        "request",
        nargs="*",
        help="Plain-English request",
    )

    args = parser.parse_args()
    agents = load_agents()

    if not agents:
        print(
            "No Agency Agents definitions were found.",
            file=sys.stderr,
        )
        return 1

    request = " ".join(args.request).strip()

    if args.voice:
        try:
            spoken_request = transcribe_voice()
        except Exception as error:
            print(
                f"Voice input failed: {error}",
                file=sys.stderr,
            )
            return 1

        request = " ".join(
            part
            for part in (
                request,
                spoken_request,
            )
            if part
        ).strip()

    if not request:
        request = input("What should KUDOS do? ").strip()

    if not request:
        print("No request was provided.", file=sys.stderr)
        return 2

    # --- Resolve read/write mode ------------------------------------------
    default_mode = os.getenv("KUDOS_DEFAULT_MODE", "read")

    if args.mode == "write":
        can_edit = True
    elif args.mode == "read":
        can_edit = False
    elif args.apply:
        can_edit = True
    else:
        can_edit = default_mode.strip().lower() == "write"
    # ----------------------------------------------------------------------

    local_request = request.lower()

    wants_open = "open" in local_request
    wants_github = (
        "github" in local_request
        or "repository" in local_request
        or "repo" in local_request
    )
    wants_campus = (
        "digital campus" in local_request
        or "kudos app" in local_request
        or "campus app" in local_request
    )

    if wants_open and wants_github:
        github_url = (
            "https:"
            + "//github.com/"
            + "mukondakangwa1-lgtm/New-project"
        )

        if args.dry_run:
            print(
                "KUDOS would open the GitHub repository:",
                github_url,
            )
        else:
            subprocess.Popen(
                ["xdg-open", github_url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print("KUDOS opened your GitHub repository.")

        return 0

    if wants_open and wants_campus:
        campus_url = "http:" + "//127.0.0.1:3000"

        if args.dry_run:
            print(
                "KUDOS would open Digital Campus:",
                campus_url,
            )
        else:
            subprocess.Popen(
                ["xdg-open", campus_url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print("KUDOS opened Digital Campus.")

        return 0

    ranked = route(request, agents)

    if args.agent:
        if args.agent not in agents:
            print(
                f"Unknown agent: {args.agent}",
                file=sys.stderr,
            )
            return 2

        selected = args.agent
    else:
        selected = ranked[0][1]

    selected_mode = (
        "offline"
        if args.offline
        else "online"
    )

    print()
    print("KUDOS REQUEST")
    print(f"  Request: {request}")
    print(f"  Agent:   {selected}")
    print(f"  Mode:    {selected_mode}")
    print(
        f"  Action:  "
        f"{'may edit files' if can_edit else 'read-only'}"
    )

    print()
    print("Other likely specialists:")

    for score, slug in ranked[:4]:
        marker = "*" if slug == selected else "-"
        print(f"  {marker} {slug} (score {score})")

    if args.dry_run:
        print()
        print("Dry run only; no model was launched.")
        return 0

    if can_edit:
        if selected_mode == "offline":
            print(
                "Offline specialists are advisory only; "
                "file editing requires online mode.",
                file=sys.stderr,
            )
            return 2

        if not args.yes:
            print()
            confirmation = input(
                "Type APPLY to allow repository edits: "
            )

            if confirmation != "APPLY":
                print("Cancelled; no files were modified.")
                return 0

        task = (
            "You may edit files for this request. "
            "First inspect the repository, make the smallest "
            "safe change, run relevant tests, and do not commit "
            "or push. "
            f"User request: {request}"
        )
    else:
        task = (
            "READ-ONLY REQUEST: Do not edit, create, rename, "
            "or delete files. Do not commit or push. "
            "Inspect only what is necessary and provide an "
            f"actionable answer. User request: {request}"
        )

    if args.speak:
        task += (
            "\n\nEnd your response with the exact heading "
            "'SPOKEN SUMMARY:' followed by a concise plain-English "
            "summary of no more than three sentences. Do not put "
            "anything after the spoken summary."
        )

    runner = (
        "agency-offline"
        if selected_mode == "offline"
        else "agency-online"
    )

    command = [runner]

    if selected_mode == "offline" and PROJECT.exists():
        command.append("--project")

    command.extend([selected, task])

    # --- Grant ALL opencode tools for this run ----------------------------
    # opencode merges OPENCODE_PERMISSION over its config (even managed
    # denies), so this guarantees read/edit/bash/external_directory access
    # regardless of ~/.config/opencode/opencode.json.
    os.environ["OPENCODE_PERMISSION"] = json.dumps(
        {
            "external_directory": "allow",
            "read": "allow",
            "edit": "allow",
            "write": "allow",
            "glob": "allow",
            "grep": "allow",
            "list": "allow",
            "bash": "allow",
            "task": "allow",
            "lsp": "allow",
            "skill": "allow",
            "webfetch": "allow",
            "websearch": "allow",
            "todoread": "allow",
            "todowrite": "allow",
        }
    )
    # ----------------------------------------------------------------------

    print()
    print(f"Launching {selected}...")

    if not args.speak:
        result = subprocess.run(
            command,
            cwd=PROJECT,
            check=False,
        )
        return result.returncode

    result = subprocess.run(
        command,
        cwd=PROJECT,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.stderr:
        print(
            result.stderr,
            end="" if result.stderr.endswith("\n") else "\n",
            file=sys.stderr,
        )

    if result.stdout:
        print(
            result.stdout,
            end="" if result.stdout.endswith("\n") else "\n",
        )

    if result.returncode != 0:
        print(
            "Agent failed; KUDOS will not speak an incomplete answer.",
            file=sys.stderr,
        )
        return result.returncode

    output = result.stdout or ""
    marker = "SPOKEN SUMMARY:"

    if marker in output:
        spoken = output.rsplit(marker, 1)[1].strip()
    else:
        clean_lines = [
            line.strip()
            for line in output.splitlines()
            if line.strip()
            and not line.lstrip().startswith(
                (">", "$", "✱", "→", "#")
            )
        ]
        spoken = " ".join(clean_lines[-6:]).strip()

    spoken = re.sub(
        r"\x1b\[[0-9;]*m",
        "",
        spoken,
    )
    spoken = spoken[:1800].strip()

    if not spoken:
        print(
            "No final text was available to speak.",
            file=sys.stderr,
        )
        return 1

    speech = subprocess.run(
        ["kudos-speak", spoken],
        check=False,
    )

    return speech.returncode


if __name__ == "__main__":
    raise SystemExit(main())
