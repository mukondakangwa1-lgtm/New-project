"""
Digital Campus - Backend Configuration
Hybrid PostgreSQL + SQLite support.
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
    # Database — Hybrid Support
    # ──────────────────────────────────────────
    # Primary DB: flip between SQLite (laptop) and Postgres (prod) via one var.
    # Examples:
    #   SQLite laptop: sqlite:///./digital_campus.db
    #   Postgres prod: postgresql+psycopg2://dc_user:dc_pass@db:5432/digital_campus
    DATABASE_URL: str = "sqlite:///./digital_campus.db"

    # Optional local replica for offline-first (Pattern B).
    # When set, app can use this SQLite file as fallback/cache.
    # Example: sqlite:///./digital_campus_local.db
    DATABASE_URL_LOCAL: Optional[str] = None

    # Optional Redis / Celery (docker-compose)
    REDIS_URL: str = "redis://redis:6379/0"

    # Embeddings
    EMBED_DIM: int = 1536

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        return self.DATABASE_URL.startswith(("postgresql", "postgres"))

    @property
    def has_local_replica(self) -> bool:
        return bool(self.DATABASE_URL_LOCAL and self.DATABASE_URL_LOCAL.startswith("sqlite"))


settings = Settings()
