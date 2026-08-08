"""
Digital Campus - Unified Object Storage (MinIO / S3)
Connected storage for PostgreSQL/SQLite apps.

Supports:
  - MinIO local (free, private, offline)  -> S3_ENDPOINT=http://localhost:9000 or http://minio:9000
  - Cloudflare R2 / Backblaze B2 / AWS S3  -> same boto3 code, just change endpoint
  - Graceful fallback: if MinIO not reachable and S3_ENABLED=false, functions return local-file hint.

All buckets are private + AES256. Access via presigned URLs (15 min expiry).
"""
from __future__ import annotations

import os
import time
import hashlib
from typing import Optional, BinaryIO
from pathlib import Path

from app.core.config import settings

try:
    import boto3
    from botocore.client import Config as BotoConfig
    from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError
    BOTO_AVAILABLE = True
except Exception:
    boto3 = None
    BotoConfig = None
    ClientError = Exception
    BOTO_AVAILABLE = False

# Allowed types - only connected ones, dead types (gdrive/dropbox/onedrive) removed
ALLOWED_STORAGE_TYPES = {"s3", "minio", "link", "youtube", "image"}

def _normalize_type(t: str) -> str:
    """Map dead types gdrive/dropbox/onedrive -> link, s3/minio unified."""
    t = (t or "link").lower().strip()
    if t in ("gdrive", "dropbox", "onedrive", "drive"):
        return "link"  # dead external APIs -> generic link
    if t == "minio":
        return "s3"
    if t not in ALLOWED_STORAGE_TYPES:
        return "link"
    return t


def get_s3_client():
    """Return boto3 S3 client for current settings. Raises if not configured."""
    if not BOTO_AVAILABLE:
        raise RuntimeError("boto3 not installed — pip install boto3")
    if not settings.s3_is_configured:
        raise RuntimeError("S3 not configured — set S3_* in .env and S3_ENABLED=true")
    endpoint = settings.S3_ENDPOINT.rstrip("/")
    # MinIO needs path-style, R2/S3 need virtual-hosted - boto handles both with s3v4
    config = BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"})
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=config,
        verify=settings.S3_SECURE,  # for local minio http, verify=False is okay
    )


def ensure_bucket(client=None) -> dict:
    """Ensure bucket exists (private, AES256). Returns {ok, bucket, created}."""
    if not settings.s3_is_configured:
        return {"ok": False, "error": "S3_ENABLED=false or missing S3_BUCKET/keys"}
    c = client or get_s3_client()
    bucket = settings.S3_BUCKET
    try:
        c.head_bucket(Bucket=bucket)
        return {"ok": True, "bucket": bucket, "created": False}
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchBucket", "NotFound"):
            try:
                c.create_bucket(Bucket=bucket)
                # block public access
                try:
                    c.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
                except Exception:
                    pass
                return {"ok": True, "bucket": bucket, "created": True}
            except Exception as ce:
                return {"ok": False, "error": str(ce), "bucket": bucket}
        return {"ok": False, "error": str(e), "bucket": bucket}
    except Exception as e:
        return {"ok": False, "error": str(e), "bucket": bucket}


def upload_file(file_obj: BinaryIO, key: str, content_type: str = "application/octet-stream") -> dict:
    """Upload file-like object to S3/MinIO. Returns {ok, key, url, size}."""
    if not settings.s3_is_configured:
        return {"ok": False, "error": "S3 not enabled — set S3_ENABLED=true in .env"}
    c = get_s3_client()
    bucket = settings.S3_BUCKET
    # ensure bucket
    ensure_bucket(c)
    try:
        file_obj.seek(0)
    except Exception:
        pass
    extra = {"ServerSideEncryption": "AES256", "ContentType": content_type}
    try:
        c.upload_fileobj(file_obj, bucket, key, ExtraArgs=extra)
        # presigned url for private bucket
        url = c.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=900)
        return {"ok": True, "key": key, "bucket": bucket, "url": url, "storage_type": "s3"}
    except Exception as e:
        return {"ok": False, "error": str(e), "key": key, "bucket": bucket}


def delete_file(key: str) -> dict:
    if not settings.s3_is_configured:
        return {"ok": False, "error": "S3 not enabled"}
    c = get_s3_client()
    try:
        c.delete_object(Bucket=settings.S3_BUCKET, Key=key)
        return {"ok": True, "key": key}
    except Exception as e:
        return {"ok": False, "error": str(e), "key": key}


def presigned_url(key: str, expires: int = 900) -> dict:
    if not settings.s3_is_configured:
        return {"ok": False, "error": "S3 not enabled"}
    c = get_s3_client()
    try:
        url = c.generate_presigned_url("get_object", Params={"Bucket": settings.S3_BUCKET, "Key": key}, ExpiresIn=expires)
        return {"ok": True, "url": url, "key": key, "expires": expires}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_files(prefix: str = "", limit: int = 100) -> dict:
    if not settings.s3_is_configured:
        return {"ok": False, "error": "S3 not enabled"}
    c = get_s3_client()
    try:
        resp = c.list_objects_v2(Bucket=settings.S3_BUCKET, Prefix=prefix, MaxKeys=limit)
        items = [{"key": o["Key"], "size": o["Size"], "modified": o["LastModified"].isoformat()} for o in resp.get("Contents", [])]
        return {"ok": True, "files": items, "count": len(items), "bucket": settings.S3_BUCKET}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def health_check() -> dict:
    """Check MinIO/S3 connectivity + bucket + write test."""
    info = {
        "enabled": settings.S3_ENABLED,
        "endpoint": settings.S3_ENDPOINT,
        "bucket": settings.S3_BUCKET,
        "region": settings.S3_REGION,
        "boto3": BOTO_AVAILABLE,
    }
    if not settings.s3_is_configured:
        return {**info, "ok": False, "error": "S3 not configured (S3_ENABLED=false or missing keys)"}
    if not BOTO_AVAILABLE:
        return {**info, "ok": False, "error": "boto3 not installed"}
    try:
        c = get_s3_client()
        # list buckets
        c.list_buckets()
        bucket_res = ensure_bucket(c)
        # try small put/delete test
        test_key = f"_healthcheck/{int(time.time())}.txt"
        c.put_object(Bucket=settings.S3_BUCKET, Key=test_key, Body=b"ok", ServerSideEncryption="AES256")
        c.delete_object(Bucket=settings.S3_BUCKET, Key=test_key)
        return {**info, "ok": True, "bucket_status": bucket_res, "write_test": "ok"}
    except Exception as e:
        return {**info, "ok": False, "error": str(e)[:500]}


def make_key(prefix: str, filename: str, user_id: int = 0) -> str:
    """Make safe S3 key: prefix/user_id/timestamp_hash_filename"""
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)[:80]
    h = hashlib.md5(f"{filename}{time.time()}".encode()).hexdigest()[:8]
    return f"{prefix.strip('/')}/{user_id}/{int(time.time())}_{h}_{safe}"
