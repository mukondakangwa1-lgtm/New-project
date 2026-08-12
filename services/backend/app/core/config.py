"""
Digital Campus — Application settings.

Loads configuration from environment variables (and an optional .env file).
Unknown env vars are tolerated so unrelated keys never crash startup.
"""
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── App ────────────────────────────────────
    APP_NAME: str = "Digital Campus API"
    APP_VERSION: str = "1.0.0"

    # ── Server ─────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # ── Database ───────────────────────────────
    DATABASE_URL: str = "sqlite:///./digital_campus.db"

    # ── Security / JWT ─────────────────────────
    SECRET_KEY: str = "change-me-to-a-random-string-at-least-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # ── LLM provider keys (all optional) ───────
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    # All API keys from the API_KEYS env var (comma- or newline-separated)
    API_KEYS: List[str] = []

    # Allow unknown/extra env vars so Settings() won't raise on unrelated keys
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
        case_sensitive=True,
    )

    @field_validator("API_KEYS", mode="before")
    @classmethod
    def _split_api_keys(cls, v):
        """Accept a comma- or newline-separated string, or a real list."""
        if v is None or v == "":
            return []
        if isinstance(v, str):
            normalized = v.replace("\r\n", "\n").replace("\n", ",")
            return [part.strip() for part in normalized.split(",") if part.strip()]
        return v


# Single shared settings instance used across the app
settings = Settings()
