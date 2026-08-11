"""Object storage for Digital Campus — MinIO (S3-compatible) with local-disk fallback.

Storage is split by bucket prefixes so one bucket can hold every object type:

    audio/    — speaking practice recordings
    docs/     — original knowledge documents (PDF, DOCX, ...)
    avatars/  — user profile pictures
    backups/  — pg_dump / SQLite backup archives

Backend selection (``STORAGE_BACKEND``):

* ``auto``  — use MinIO when ``MINIO_ENDPOINT`` is configured, otherwise fall
  back to the local directory (``STORAGE_LOCAL_DIR``). Recommended for dev.
* ``minio`` — require MinIO; operations raise ``StorageUnavailableError`` when
  the endpoint is missing or unreachable.
* ``local`` — always use the local directory (tests, standalone boxes).

When MinIO is absent, object keys map to files under the local directory, so
application code never branches on the backend for basic read/write.
"""

from __future__ import annotations

import contextlib
import io
import os
import time
import uuid
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

from app.core.config import settings
from app.core.paths import project_root

LOCAL_ROOT = Path(project_root(__file__)) / "storage-local"

# Bucket prefixes (single MinIO bucket, sub-folders per object type).
BUCKET_PREFIXES = ("audio/", "docs/", "avatars/", "backups/", "media/", "generated/")


class StorageUnavailableError(RuntimeError):
    """Raised when MinIO is required (``STORAGE_BACKEND=minio``) but unusable."""


def _minio_configured() -> bool:
    return bool(settings.MINIO_ENDPOINT and settings.MINIO_ACCESS_KEY and settings.MINIO_SECRET_KEY)


def backend_name() -> str:
    """Resolve the effective backend: ``minio`` or ``local``."""
    if settings.STORAGE_BACKEND == "local":
        return "local"
    if settings.STORAGE_BACKEND == "minio":
        return "minio"
    return "minio" if _minio_configured() else "local"


def _local_dir() -> Path:
    root = Path(settings.STORAGE_LOCAL_DIR).expanduser()
    if not root.is_absolute():
        root = LOCAL_ROOT / root
    root.mkdir(parents=True, exist_ok=True)
    return root


# ──────────────────────────────────────────────
# MINIO CLIENT
# ──────────────────────────────────────────────

_client = None


def _check_key(key: str) -> None:
    if not key.startswith(BUCKET_PREFIXES):
        raise StorageUnavailableError(f"object key must live under {BUCKET_PREFIXES}: {key}")


def _get_client():
    """Lazily build the MinIO client; raises StorageUnavailableError when the
    backend is minio but credentials/endpoint are missing."""
    global _client
    if backend_name() != "minio":
        raise StorageUnavailableError(
            "MinIO is not configured (set MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY and STORAGE_BACKEND=minio)"
        )
    if not settings.MINIO_ENDPOINT:
        raise StorageUnavailableError("MINIO_ENDPOINT is empty")
    if _client is not None:
        return _client
    try:
        from minio import Minio
    except ImportError as exc:  # pragma: no cover - dependency missing
        raise StorageUnavailableError("minio SDK is not installed (pip install minio)") from exc

    _client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
        region=settings.MINIO_REGION or None,
    )
    return _client


def _local_path(key: str) -> Path:
    key = key.replace("/", os.sep)
    path = os.path.normpath(os.path.join(_local_dir(), key))
    if not path == str(_local_dir()) and not path.startswith(str(_local_dir()) + os.sep):
        raise StorageUnavailableError(f"refusing unsafe storage key: {key}")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


# ──────────────────────────────────────────────
# BUCKETS
# ──────────────────────────────────────────────


def ensure_bucket(prefix: str | None = None) -> str:
    """Ensure the bucket exists (MinIO) or the local prefix directory does.

    Returns the bucket name. No-op for ``local``.
    """
    if backend_name() != "minio":
        if prefix:
            (_local_dir() / prefix).mkdir(parents=True, exist_ok=True)
        return "local"
    client = _get_client()
    bucket = settings.MINIO_BUCKET
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    return bucket


def ensure_buckets() -> bool:
    """Idempotent bootstrap for all object-type prefixes.

    Returns True when MinIO is reachable/ready, False when falling back to
    local disk (so callers can log the mode without failing startup).
    """
    if backend_name() != "minio":
        return False
    try:
        ensure_bucket()
        for prefix in BUCKET_PREFIXES:
            ensure_bucket(prefix)
        return True
    except Exception:
        return False


# ──────────────────────────────────────────────
# OBJECT OPERATIONS
# ──────────────────────────────────────────────


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    """Write an object; ``key`` must live under one of the bucket prefixes."""
    _check_key(key)
    if backend_name() == "minio":
        client = _get_client()
        ensure_bucket(key.split("/", 1)[0] + "/")
        client.put_object(
            settings.MINIO_BUCKET,
            key,
            io.BytesIO(data),
            len(data),
            content_type=content_type,
        )
    else:
        _local_path(key).write_bytes(data)
        os.chmod(_local_path(key), 0o600)


def download(key: str) -> bytes:
    """Fetch an object's bytes (local or MinIO)."""
    if backend_name() == "minio":
        resp = _get_client().get_object(settings.MINIO_BUCKET, key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()
    path = _local_path(key)
    if not path.is_file():
        raise FileNotFoundError(key)
    return path.read_bytes()


def stream(key: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
    """Yield object bytes in chunks; ideal for StreamingResponse bodies."""
    if backend_name() == "minio":
        resp = _get_client().get_object(settings.MINIO_BUCKET, key)
        for chunk in resp.stream(chunk_size):
            yield chunk
        resp.close()
        resp.release_conn()
    else:
        path = _local_path(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        with open(path, "rb") as fh:
            while chunk := fh.read(chunk_size):
                yield chunk


def delete(key: str) -> None:
    """Remove an object; missing objects are treated as success."""
    if backend_name() == "minio":
        with contextlib.suppress(Exception):
            _get_client().remove_object(settings.MINIO_BUCKET, key)
    else:
        path = _local_path(key)
        if path.is_file():
            path.unlink()


def exists(key: str) -> bool:
    if backend_name() == "minio":
        try:
            _get_client().stat_object(settings.MINIO_BUCKET, key)
            return True
        except Exception:
            return False
    return _local_path(key).is_file()


def presigned_url(key: str, expires_seconds: int = 15 * 60) -> str | None:
    """Short-lived GET URL for direct browser download (MinIO only)."""
    if backend_name() != "minio":
        return None
    client = _get_client()
    try:
        return client.presigned_get_object(
            settings.MINIO_BUCKET,
            key,
            expires=timedelta(seconds=expires_seconds),
        )
    except Exception:
        return None


# ──────────────────────────────────────────────
# KEY HELPERS
# ──────────────────────────────────────────────


def new_key(prefix: str, filename: str = "") -> str:
    """Build a collision-safe object key: ``prefix/user-<id>/<uuid><ext>``."""
    ext = os.path.splitext(filename)[1] if filename else ""
    return f"{prefix}{uuid.uuid4().hex}{ext}"


def local_path(key: str) -> Path | None:
    """Expose the on-disk path for the local backend (None on MinIO)."""
    if backend_name() == "minio":
        return None
    return _local_path(key)


def status() -> dict:
    """Health/readiness information about the storage layer."""
    mode = backend_name()
    ok = True
    latency_ms = None
    if mode == "minio":
        try:
            client = _get_client()
            start = time.perf_counter()
            client.bucket_exists(settings.MINIO_BUCKET)
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
        except Exception:
            ok = False
    return {
        "backend": mode,
        "ready": ok,
        "bucket": settings.MINIO_BUCKET if mode == "minio" else "local",
        "latency_ms": latency_ms,
    }


def usage() -> dict:
    """Object counts and bytes per object-type prefix, plus totals.

    Works for both backends (MinIO and local-disk) and never raises —
    callers render whatever is measurable.
    """
    mode = backend_name()
    by_prefix: dict = {}
    total_bytes = 0
    total_objects = 0
    if mode == "minio":
        try:
            client = _get_client()
            bucket = settings.MINIO_BUCKET
            client.bucket_exists(bucket)
            for prefix in BUCKET_PREFIXES:
                objects = 0
                bytes_ = 0
                try:
                    for obj in client.list_objects(bucket, prefix=prefix, recursive=True):
                        objects += 1
                        bytes_ += obj.size or 0
                except Exception:
                    pass
                by_prefix[prefix] = {"objects": objects, "bytes": bytes_}
                total_objects += objects
                total_bytes += bytes_
        except Exception:
            pass
    else:
        root = _local_dir()
        for prefix in BUCKET_PREFIXES:
            pdir = root / prefix
            objects = 0
            bytes_ = 0
            if pdir.is_dir():
                for fp in pdir.rglob("*"):
                    if fp.is_file():
                        objects += 1
                        with contextlib.suppress(OSError):
                            bytes_ += fp.stat().st_size
            by_prefix[prefix] = {"objects": objects, "bytes": bytes_}
            total_objects += objects
            total_bytes += bytes_
    return {
        "backend": mode,
        "total_bytes": total_bytes,
        "total_objects": total_objects,
        "by_prefix": by_prefix,
    }
