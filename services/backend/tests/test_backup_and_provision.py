"""Backup helpers and the secret provisioner — local, no external services."""

import os
import sqlite3

import pytest

from app.core import backup, storage


def _make_sqlite(path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.execute("INSERT INTO t (v) VALUES ('hello')")
    conn.commit()
    conn.close()


def test_sqlite_dump_produces_readable_snapshot(tmp_path, monkeypatch):
    db_file = tmp_path / "app.db"
    _make_sqlite(db_file)
    monkeypatch.setattr(backup.settings, "DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setattr(storage, "backend_name", lambda: "local")
    monkeypatch.setattr(backup.settings, "BACKUP_DIR", str(tmp_path / "backups"))

    dest = backup.sqlite_dump()
    assert dest.endswith(".sqlite3")
    assert os.path.isfile(dest)

    conn = sqlite3.connect(dest)
    try:
        row = conn.execute("SELECT v FROM t").fetchone()
    finally:
        conn.close()
    assert row == ("hello",)


def test_sqlite_backup_refuses_postgres_url():
    with pytest.raises(ValueError):
        backup.sqlite_dump("postgresql://db:5432/x")


def test_provision_generates_secrets_idempotently(tmp_path, monkeypatch):
    from scripts.provision_env import provision, load_env, PLACEHOLDER_VALUES

    env_file = tmp_path / ".env"
    env_file.write_text(
        "SECRET_KEY=changeme-in-production\nDATABASE_URL=sqlite:///x.db\n"
    )

    env = provision(env_file, replace_placeholders=True)
    assert env["SECRET_KEY"] not in PLACEHOLDER_VALUES
    assert len(env["SECRET_KEY"]) >= 32
    assert env["MINIO_ENDPOINT"] == "minio:9000"
    assert env["STORAGE_BACKEND"] == "minio"
    assert "POSTGRES_PASSWORD" in env
    assert env["POSTGRES_PASSWORD"] not in ("", "replace-with-a-long-random-password")
    assert env["DATABASE_URL"].startswith("postgresql://")

    first = load_env(env_file)
    # second run: values unchanged
    again = provision(env_file, replace_placeholders=True)
    second = load_env(env_file)
    assert first == second
    assert again == first
    assert os.stat(env_file).st_mode & 0o777 == 0o600

    # explicitly set secrets must survive (no overwrite)
    after_user_edit = load_env(env_file)
    user_secret = "my-own-deliberately-placed-secret-1234567890"
    after_user_edit["SECRET_KEY"] = user_secret
    env_file.write_text(
        "\n".join(f"{k}={v}" for k, v in after_user_edit.items()) + "\n"
    )
    provision(env_file, replace_placeholders=False)
    assert load_env(env_file)["SECRET_KEY"] == user_secret
