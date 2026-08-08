"""
Architecture index — a navigable map of the codebase: directory tree,
modules with their public symbols, imports, and summary stats.

Used by the admin endpoint to inspect where things live before approving
agent changes (Req 8: architecture index).
"""
import ast
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".kudos_workspaces", ".next", "dist", "build", "coverage",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
}
SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".cpp", ".c", ".h"}
DOC_EXTS = {".md", ".txt", ".rst", ".toml", ".yaml", ".yml", ".json", ".ini", ".cfg", ".html"}

_cache: dict[str, dict] = {}
_cache_key: str = ""


class ArchIndex:
    """Builds and stores the architecture index for one repo root."""

    def __init__(self, repo_root: str | Path):
        self.root = Path(repo_root).resolve()
        self.modules: list[dict] = []
        self.tree: list[dict] = []
        self.stats: dict = {}
        self.features: list[dict] = []

    # ── scanning ───────────────────────────────────────────

    def build(self) -> "ArchIndex":
        self.modules = list(self._iter_modules())
        self.tree = self._build_tree()
        self.stats = self._compute_stats()
        self.features = self._detect_features()
        return self

    def _iter_modules(self) -> iter:
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or not self._included(path):
                continue
            rel = path.relative_to(self.root).as_posix()
            yield self._module_for(path, rel)

    def _included(self, path: Path) -> bool:
        if path.name.startswith(".") and path.parent == self.root:
            return False  # hidden files at root
        parts = set(path.parts)
        if any(d in SKIP_DIRS for d in parts):
            return False
        if path.suffix not in SOURCE_EXTS | DOC_EXTS:
            return False
        if path.name in {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}:
            return False
        return True

    def _module_for(self, path: Path, rel: str) -> dict:
        if path.suffix == ".py":
            return self._python_module(path, rel)
        return self._text_module(path, rel)

    def _python_module(self, path: Path, rel: str) -> dict:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            return {"path": rel, "kind": "python", "docstring": "", "symbols": [], "imports": [], "error": "parse"}

        classes, functions, imports = [], [], []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names]
                if isinstance(node, ast.ImportFrom) and node.module:
                    names = [f"{node.module}.{a.name}" for a in node.names]
                imports.extend(names)
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                methods = [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
                classes.append({"name": node.name, "methods": methods, "line": node.lineno})
            elif isinstance(node, ast.FunctionDef):
                functions.append({"name": node.name, "line": node.lineno})
        docstring = ast.get_docstring(tree) or ""
        return {
            "path": rel,
            "kind": "python",
            "docstring": docstring.strip().split("\n")[0][:200] if docstring else "",
            "classes": classes,
            "functions": functions,
            "symbols": [c["name"] for c in classes] + [f["name"] for f in functions],
            "imports": sorted(set(imports))[:50],
            "line_count": len(open(path, encoding="utf-8", errors="replace").readlines()),
        }

    def _text_module(self, path: Path, rel: str) -> dict:
        try:
            content = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            return {"path": rel, "kind": "text"}
        first_lines = [l.strip() for l in content.splitlines()[:8] if l.strip()]
        title = next((l for l in first_lines if l.startswith("#") and len(l) > 3), first_lines[0] if first_lines else "")
        return {
            "path": rel,
            "kind": "text",
            "title": title[:150],
            "line_count": len(content.splitlines()),
        }

    def _build_tree(self) -> list[dict]:
        dirs: dict[str, set] = {}
        for mod in self.modules:
            parts = Path(mod["path"]).parts
            for i in range(len(parts)):
                d = "/".join(parts[:i])
                dirs.setdefault(d, set()).add(parts[i] if i == len(parts) - 1 else "/".join(parts[: i + 1]))
        return [
            {
                "path": d,
                "entries": sorted(entries),
                "depth": d.count("/") if d else 0,
            }
            for d, entries in sorted(dirs.items(), key=lambda kv: kv[0])
        ]

    def _compute_stats(self) -> dict:
        by_ext = Counter(m["path"].rsplit(".", 1)[-1] for m in self.modules)
        py = [m for m in self.modules if m["kind"] == "python"]
        return {
            "files": len(self.modules),
            "python_files": len(py),
            "lines_of_code": sum(m.get("line_count", 0) for m in self.modules),
            "classes": sum(len(m.get("classes", [])) for m in py),
            "functions": sum(len(m.get("functions", [])) for m in py),
            "by_extension": dict(by_ext.most_common(10)),
        }

    def _detect_features(self) -> list[dict]:
        patterns = [
            ("api_endpoints", r"(APIRouter|FastAPI|Blueprint|@app\.(get|post|put|delete))"),
            ("models", r"__tablename__|class \w+\(.*Model|@entity"),
            ("tests", r"(^|/)test_|\.test\("),
            ("frontend_pages", r"pages/|src/pages"),
            ("migrations", r"alembic|migration"),
            ("config", r"\.env|settings|config\."),
            ("db", r"sqlalchemy|psycopg|sqlite|create_engine"),
            ("ai_ml", r"llm|openai|embedding|vector|agent|model\."),
        ]
        features = []
        for name, pattern in patterns:
            matches = [m["path"] for m in self.modules if re.search(pattern, m["path"], re.I)
                       or (name in {"tests", "api_endpoints"} and re.search(pattern, " ".join(m.get("imports", [])), re.I))]
            if matches:
                features.append({"name": name, "files": len(matches), "examples": matches[:8]})
        return features

    def to_dict(self) -> dict:
        return {
            "root": str(self.root),
            "generated_at": None,
            "stats": self.stats,
            "features": self.features,
            "modules": self.modules,
            "tree": self.tree,
        }


# ── cached accessor used by the endpoint ───────────────────

def get_architecture_index(repo_root: str | Path, force: bool = False) -> dict:
    """Build (and cache) the architecture index for a repo root."""
    root = str(Path(repo_root).resolve())
    global _cache, _cache_key
    if force or _cache_key != root or not _cache:
        try:
            index = ArchIndex(root).build().to_dict()
            _cache, _cache_key = index, root
        except OSError as exc:
            return {"error": str(exc)}
    return _cache


def summarize(index: dict) -> str:
    """A short human-readable summary of an index."""
    stats = index.get("stats", {})
    features = ", ".join(f["name"] for f in index.get("features", [])[:10])
    return (
        f"{stats.get('files', 0)} files, {stats.get('lines_of_code', 0)} LOC, "
        f"{stats.get('classes', 0)} classes, {stats.get('functions', 0)} functions. "
        f"Features: {features or 'none detected'}."
    )
