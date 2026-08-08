"""
Architecture index tests — scanning, module extraction, tree, stats, cache,
and the admin endpoint.
"""
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core import archindex
from app.core.archindex import ArchIndex, get_architecture_index, summarize
from app.main import app

client = TestClient(app)


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Path:
    root = tmp_path / "sample"
    (root / "src").mkdir(parents=True)
    (root / "src" / "main.py").write_text(
        '"""Entry point."""\n'
        "import os\n"
        "from fastapi import FastAPI\n\n"
        "app = FastAPI()\n\n"
        "def run():\n"
        "    return 1\n\n"
        "class Service:\n"
        "    def start(self):\n"
        "        pass\n"
    )
    (root / "src" / "models.py").write_text(
        "class User:\n    pass\n\nclass Post:\n    pass\n"
    )
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_main.py").write_text("def test_run():\n    pass\n")
    (root / "README.md").write_text("# Sample\n\nDocs.\n")
    (root / "package.json").write_text('{"name": "x", "scripts": {"test": "vitest"}}\n')
    (root / "alembic").mkdir(parents=True)
    (root / "alembic" / "env.py").write_text("migration stuff\n")
    return root


def test_index_stats(sample_repo: Path):
    index = ArchIndex(sample_repo).build().to_dict()
    assert index["stats"]["files"] == 6
    assert index["stats"]["python_files"] == 4
    assert index["stats"]["classes"] == 3  # Service, User, Post
    assert index["stats"]["functions"] == 2  # run, test_run


def test_module_symbols(sample_repo: Path):
    index = ArchIndex(sample_repo).build().to_dict()
    main_mod = next(m for m in index["modules"] if m["path"] == "src/main.py")
    assert [c["name"] for c in main_mod["classes"]] == ["Service"]
    assert "run" in main_mod["functions"][0]["name"]
    assert "fastapi" in " ".join(main_mod["imports"]).lower()


def test_skips_venv_and_git(tmp_path: Path):
    root = tmp_path / "r"
    (root / ".venv").mkdir(parents=True)
    (root / ".venv" / "lib.py").write_text("class X: pass\n")
    (root / ".git").mkdir()
    (root / "ok.py").write_text("x = 1\n")
    index = ArchIndex(root).build().to_dict()
    assert index["stats"]["files"] == 1


def test_features_detected(sample_repo: Path):
    index = ArchIndex(sample_repo).build().to_dict()
    names = {f["name"] for f in index["features"]}
    assert "tests" in names
    assert "api_endpoints" in names
    assert "migrations" in names


def test_cache_and_force(sample_repo: Path):
    get_architecture_index(sample_repo)
    assert archindex._cache_key == str(sample_repo.resolve())
    (sample_repo / "new.py").write_text("x=1\n")
    cached = get_architecture_index(sample_repo)
    assert cached["stats"]["files"] == 6  # stale by design
    fresh = get_architecture_index(sample_repo, force=True)
    assert fresh["stats"]["files"] == 7


def test_summarize_string(sample_repo: Path):
    index = ArchIndex(sample_repo).build().to_dict()
    s = summarize(index)
    assert "files" in s and "classes" in s


def test_endpoint_requires_admin(sample_repo: Path):
    from tests.conftest import login, promote_to_admin, register_user

    email = "arch_admin@example.com"
    register_user(client, email)
    promote_to_admin(email)
    headers = login(client, email)

    from app.core.code_agent import set_repo_path

    set_repo_path(str(sample_repo))
    r = client.get("/api/v1/kudos/agent/architecture", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["stats"]["classes"] == 3
    assert "summary" in data

    r2 = client.get("/api/v1/kudos/agent/architecture?force=true", headers=headers)
    assert r2.status_code == 200


def test_endpoint_rejects_non_admin(sample_repo: Path):
    from tests.conftest import login, register_user

    email = "arch_user@example.com"
    register_user(client, email)
    headers = login(client, email)
    r = client.get("/api/v1/kudos/agent/architecture", headers=headers)
    assert r.status_code == 403
