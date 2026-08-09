"""
KUDOS EditOps — structured code editing operations.

Operations are performed inside an isolated Workspace (never the main tree)
and every path goes through :mod:`app.core.pathguard`. Supported operations:

- apply_patch        — apply a unified diff (validated paths, ``git apply``)
- replace_symbol     — replace the body of a named function/class (AST for
                       Python, definition-anchored regex otherwise)
- rename_symbol      — rename a symbol across one file (word-boundary)
- search_references  — find every reference to a symbol (ripgrep)
- create_file        — create a file inside the workspace
- delete_file        — delete a file (requires explicit approval)
- move_file          — move/rename a file
- verify_changed     — confirm exactly the intended files changed
"""
import ast
import re
import shutil
from typing import Iterable, Optional

from app.core.pathguard import PathError, resolve_inside
from app.core.workspace import Workspace


class EditError(RuntimeError):
    """Raised when a structured edit fails."""


# ──────────────────────────────────────────────
# PATCHES
# ──────────────────────────────────────────────

_PATCH_PATH_RE = re.compile(r"^[+-]{3}\s+(?:[ab]/)?(\S+)", re.MULTILINE)


def _paths_in_patch(patch_text: str) -> list[str]:
    """Extract file paths from a unified diff (respects rename headers)."""
    paths: list[str] = []
    for m in _PATCH_PATH_RE.finditer(patch_text):
        path = m.group(1)
        if path == "/dev/null" or path.endswith("/dev/null"):
            continue
        if path not in paths:
            paths.append(path)
    return paths


def apply_patch(ws: Workspace, patch_text: str) -> dict:
    """Validate and apply a unified diff inside the workspace.

    Every path in the diff is validated with :func:`resolve_inside` before
    anything is applied. The patch is then checked with ``git apply --check``
    and applied with ``git apply`` (which reports conflicts cleanly).
    """
    if not patch_text.strip():
        raise EditError("Empty patch")
    for path in _paths_in_patch(patch_text):
        try:
            resolve_inside(ws.path, path, allow_missing=True)
        except PathError as exc:
            raise EditError(f"Patch touches a disallowed path: {exc}")

    check = _run_stdin(ws, ["git", "apply", "--check", "--whitespace=nowarn", "-"], patch_text)
    if check.returncode != 0:
        raise EditError(f"Patch does not apply cleanly:\n{check.stderr[:500]}")

    result = _run_stdin(ws, ["git", "apply", "--whitespace=nowarn", "-"], patch_text)
    if result.returncode != 0:
        raise EditError(f"Patch apply failed:\n{result.stderr[:500]}")
    return {"applied": True, "files": _paths_in_patch(patch_text)}


def _run_stdin(ws: Workspace, args: list[str], stdin_text: str):
    import subprocess

    from app.core.workspace import _limit_resources

    return subprocess.run(
        args,
        cwd=str(ws.path),
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=60,
        preexec_fn=_limit_resources,
    )


# ──────────────────────────────────────────────
# SYMBOL EDITS
# ──────────────────────────────────────────────

def _read(ws: Workspace, relpath: str) -> str:
    path = resolve_inside(ws.path, relpath)
    if not path.exists():
        raise EditError(f"File not found: {relpath}")
    return path.read_text(encoding="utf-8")


def _write(ws: Workspace, relpath: str, content: str) -> None:
    path = resolve_inside(ws.path, relpath)
    path.write_text(content, encoding="utf-8")


def _python_symbol_segment(content: str, symbol: str) -> Optional[tuple[int, int, str]]:
    """Return (start, end, text) of a top-level def/class, or None."""
    tree = ast.parse(content)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol:
            lines = content.splitlines(keepends=True)
            start = node.lineno - 1
            end = node.end_lineno
            return start, end, "".join(lines[start:end])
    return None


def replace_symbol(ws: Workspace, relpath: str, symbol: str, new_definition: str) -> dict:
    """Replace the whole definition of ``symbol`` with ``new_definition``.

    Python files use AST location info; other files use a definition-anchored
    regex (``function name`` / ``class Name`` / ``const name``) up to the end
    of the enclosing block (balanced braces/parens).
    """
    content = _read(ws, relpath)
    segment = None
    if relpath.endswith(".py"):
        try:
            segment = _python_symbol_segment(content, symbol)
        except SyntaxError as exc:
            raise EditError(f"Cannot parse {relpath}: {exc}")
    else:
        segment = _ts_symbol_segment(content, symbol)

    if segment is None:
        raise EditError(f"Symbol '{symbol}' not found in {relpath}")

    start, end, _old = segment
    lines = content.splitlines(keepends=True)
    lines[start:end] = [new_definition if new_definition.endswith("\n") else new_definition + "\n"]
    _write(ws, relpath, "".join(lines))
    return {"replaced": symbol, "file": relpath}


def _ts_symbol_segment(content: str, symbol: str) -> Optional[tuple[int, int, str]]:
    """Find a top-level TS/JS definition block by name."""
    patterns = [
        rf"^(export\s+)?(?:async\s+)?function\s+{re.escape(symbol)}\s*\(",  # function foo(
        rf"^(export\s+)?class\s+{re.escape(symbol)}\b",  # class Foo
        rf"^(export\s+)?(?:const|let|var)\s+{re.escape(symbol)}\s*=",  # const foo =
    ]
    lines = content.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if not re.match(r"^(export|function|class|const|let|var|async)\s", line):
            continue
        if any(re.match(p, line) for p in patterns):
            end = _block_end(lines, i)
            return i, end, "".join(lines[i:end])
    return None


def _block_end(lines: list[str], start: int) -> int:
    """End index of the block starting at ``start`` (brace/bracket aware)."""
    depth = 0
    in_string: Optional[str] = None
    for i in range(start, len(lines)):
        line = lines[i]
        for ch in line:
            if in_string:
                if ch == in_string and not line[: line.index(ch)].count("\\") % 2:
                    in_string = None
                continue
            if ch in ("'", '"', "`"):
                in_string = ch
            elif ch in "({[":
                depth += 1
            elif ch in ")}]":
                depth -= 1
                if depth <= 0 and i > start:
                    return i + 1
    return len(lines)


# ──────────────────────────────────────────────
# RENAME
# ──────────────────────────────────────────────

def rename_symbol(ws: Workspace, relpath: str, old_name: str, new_name: str) -> dict:
    """Rename ``old_name`` to ``new_name`` in one file (word boundaries).

    Intended for identifiers with conventional names. Call
    :func:`search_references` first to review every usage; for cross-file
    renames apply the same call to each file.
    """
    if not old_name.isidentifier() or not new_name.isidentifier():
        raise EditError("Symbol names must be valid identifiers")
    content = _read(ws, relpath)
    if old_name not in content:
        raise EditError(f"'{old_name}' not found in {relpath}")
    updated = re.sub(rf"\b{re.escape(old_name)}\b", new_name, content)
    _write(ws, relpath, updated)
    return {"renamed": old_name, "to": new_name, "file": relpath}


def search_references(ws: Workspace, symbol: str, relpath: Optional[str] = None) -> list[dict]:
    """Find every reference to ``symbol`` (ripgrep, grep fallback)."""
    target = resolve_inside(ws.path, relpath) if relpath else ws.path
    pattern = r"\b" + re.escape(symbol) + r"\b"
    if _have_rg():
        result = ws.run(["rg", "-n", "--no-heading", pattern, str(target)], timeout=60)
    else:
        result = ws.run(["grep", "-rn", "-E", pattern, str(target)], timeout=60)
    matches = []
    for line in result.stdout.splitlines():
        # output: <path>:<line>:<text>
        parts = line.split(":", 2)
        if len(parts) >= 3:
            matches.append({"file": parts[0], "line": int(parts[1]), "text": parts[2].strip()})
    return matches


_RG_AVAILABLE = None


def _have_rg() -> bool:
    global _RG_AVAILABLE
    if _RG_AVAILABLE is None:
        import shutil

        _RG_AVAILABLE = shutil.which("rg") is not None
    return _RG_AVAILABLE


# ──────────────────────────────────────────────
# FILE OPERATIONS
# ──────────────────────────────────────────────

def create_file(ws: Workspace, relpath: str, content: str) -> dict:
    """Create a file inside the workspace (parent dirs created)."""
    try:
        path = resolve_inside(ws.path, relpath, allow_missing=True)
    except PathError as exc:
        raise EditError(str(exc))
    if path.exists():
        raise EditError(f"File already exists: {relpath}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"created": relpath, "bytes": len(content)}


def delete_file(ws: Workspace, relpath: str, *, approved: bool = False) -> dict:
    """Delete a file. Requires explicit approval; refuses by default."""
    if not approved:
        raise EditError(f"Deletion of {relpath} requires explicit approval")
    path = resolve_inside(ws.path, relpath)
    if not path.exists():
        raise EditError(f"File not found: {relpath}")
    if path.is_dir():
        raise EditError(f"Use move/cleanup for directories: {relpath}")
    path.unlink()
    return {"deleted": relpath}


def move_file(ws: Workspace, src: str, dst: str) -> dict:
    """Move a file inside the workspace."""
    src_path = resolve_inside(ws.path, src)
    dst_path = resolve_inside(ws.path, dst, allow_missing=True)
    if not src_path.exists():
        raise EditError(f"File not found: {src}")
    if dst_path.exists():
        raise EditError(f"Destination already exists: {dst}")
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src_path), str(dst_path))
    return {"moved": src, "to": dst}


def verify_changed(ws: Workspace, expected: Iterable[str]) -> dict:
    """Confirm exactly the intended files changed in the workspace.

    Raises EditError if the workspace contains changes to files not in
    ``expected`` (protects against accidental edits to unrelated code).
    """
    expected = set(expected)
    changed = set(ws.files_changed())
    unexpected = changed - expected
    if unexpected:
        raise EditError(f"Unexpected files changed: {sorted(unexpected)}")
    missing = expected - changed
    if missing:
        raise EditError(f"Expected changes not present: {sorted(missing)}")
    return {"verified": True, "changed": sorted(changed)}
