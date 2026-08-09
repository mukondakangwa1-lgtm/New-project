"""Object storage tests — local-disk backend (MinIO integration runs in Compose).

Each test pins STORAGE_BACKEND=local and an isolated temp directory so the
suite never touches the developer's real uploads or requires a MinIO server.
"""

import os

import pytest

from app.core import storage
from app.core.config import settings


@pytest.fixture(autouse=True)
def _local_backend(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "STORAGE_LOCAL_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "MINIO_ENDPOINT", "")
    monkeypatch.setattr(settings, "MINIO_ACCESS_KEY", None)
    monkeypatch.setattr(settings, "MINIO_SECRET_KEY", None)
    monkeypatch.setattr(settings, "MINIO_BUCKET", "kudos-test")
    yield


def test_backend_resolves_to_local_when_minio_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "auto")
    assert storage.backend_name() == "local"


def test_backend_requires_minio_when_requested(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "minio")
    with pytest.raises(storage.StorageUnavailableError):
        storage._get_client()


def test_upload_download_roundtrip():
    key = "audio/test_roundtrip.webm"
    storage.upload_bytes(key, b"\x00\x01recording-bytes", content_type="audio/webm")
    assert storage.exists(key)
    assert storage.download(key) == b"\x00\x01recording-bytes"
    assert storage.local_path(key).is_file()
    assert os.stat(storage.local_path(key)).st_mode & 0o777 == 0o600


def test_stream_yields_chunks():
    key = "docs/streamed.txt"
    payload = b"x" * (1024 * 1024 + 17)
    storage.upload_bytes(key, payload, content_type="text/plain")
    chunks = list(storage.stream(key, chunk_size=1024 * 1024))
    assert sum(len(c) for c in chunks) == len(payload)
    assert b"".join(chunks) == payload


def test_delete_removes_object():
    key = "avatars/u1.png"
    storage.upload_bytes(key, b"png-data", content_type="image/png")
    assert storage.exists(key)
    storage.delete(key)
    assert not storage.exists(key)


def test_delete_missing_is_success():
    storage.delete("avatars/nope.png")  # must not raise


def test_download_missing_raises():
    with pytest.raises(FileNotFoundError):
        storage.download("audio/missing.webm")


def test_presigned_url_is_none_on_local_backend():
    storage.upload_bytes("audio/x.webm", b"data")
    assert storage.presigned_url("audio/x.webm") is None


def test_key_must_have_allowed_prefix():
    with pytest.raises(storage.StorageUnavailableError):
        storage.upload_bytes("etc/passwd", b"nope")
    with pytest.raises(storage.StorageUnavailableError):
        storage.upload_bytes("../escape.txt", b"nope")


def test_new_key_has_prefix_and_extension():
    key = storage.new_key("audio/", "myrec.wav")
    assert key.startswith("audio/")
    assert key.endswith(".wav")
    assert len(key) > len("audio/")


def test_local_path_key_traversal_refused():
    with pytest.raises(storage.StorageUnavailableError):
        storage._local_path("../../etc/passwd")


def test_ensure_buckets_returns_false_when_local():
    assert storage.ensure_buckets() is False
    storage.ensure_bucket()
    storage.ensure_bucket("audio/")
    assert storage.backend_name() == "local"


def test_status_reports_local_backend():
    status = storage.status()
    assert status["backend"] == "local"
    assert status["ready"] is True


def test_bucketless_read_fallback(tmp_path):
    """Reading a key that only exists as a pre-seeded file must work."""
    pre = tmp_path / "audio" / "seeded.webm"
    pre.parent.mkdir(parents=True)
    pre.write_bytes(b"seeded!")
    assert storage.exists("audio/seeded.webm")
    assert storage.download("audio/seeded.webm") == b"seeded!"
