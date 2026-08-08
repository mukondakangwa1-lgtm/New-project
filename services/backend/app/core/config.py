"""
Digital Campus - Backend Configuration
Hybrid PostgreSQL + SQLite + MinIO (S3) support.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # Application
    APP_NAME: str = "Digital Campus API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Security
    SECRET_KEY: str = "changeme-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ──────────────────────────────────────────
    # Database — Hybrid Support (PostgreSQL + SQLite)
    # ──────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./digital_campus.db"
    DATABASE_URL_LOCAL: Optional[str] = None
    REDIS_URL: str = "redis://redis:6379/0"
    EMBED_DIM: int = 1536

    # ──────────────────────────────────────────
    # Object Storage — MinIO / S3 (connected)
    # ──────────────────────────────────────────
    # Primary storage for files: MinIO local or Cloudflare R2 / AWS S3
    # If not set, uploads fall back to DB text (graceful), but MinIO is preferred.
    S3_ENDPOINT: str = "http://localhost:9000"  # Docker: http://minio:9000
    S3_BUCKET: str = "campus-media"
    S3_ACCESS_KEY: str = "dc_minio"
    S3_SECRET_KEY: str = "dc_minio_pass_32chars_change_me"
    S3_REGION: str = "us-east-1"
    S3_SECURE: bool = False  # true for R2/ prod
    S3_ENABLED: bool = True  # set false to disable S3 and use DB-only (no MinIO)

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        return self.DATABASE_URL.startswith(("postgresql", "postgres"))

    @property
    def has_local_replica(self) -> bool:
        return bool(self.DATABASE_URL_LOCAL and self.DATABASE_URL_LOCAL.startswith("sqlite"))

    @property
    def s3_is_configured(self) -> bool:
        return bool(self.S3_ENABLED and self.S3_BUCKET and self.S3_ACCESS_KEY and self.S3_SECRET_KEY)


settings = Settings()
