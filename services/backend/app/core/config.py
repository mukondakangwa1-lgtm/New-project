"""Application configuration loaded from environment variables and ``.env``.

The env file is resolved relative to this file (``services/backend/.env``)
rather than the current working directory, so the SECRET_KEY and other
secrets load no matter where the process is launched from. Override with the
``KUDOS_ENV_FILE`` environment variable when needed.
"""

import json
import os
import re
from typing import Annotated, Any, List, Optional

from pydantic import ConfigDict, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode

_ENV_FILE = os.environ.get("KUDOS_ENV_FILE") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"
)
_ENV_FILE = os.path.normpath(_ENV_FILE)


class Settings(BaseSettings):
    """Runtime settings for the Digital Campus backend.

    Unknown values in ``.env`` are allowed so that infrastructure-specific
    settings (for example Redis or Celery configuration) can be supplied
    without making the application fail during import.
    """

    model_config = ConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="allow",
    )

    # Application
    APP_NAME: str = "Digital Campus API"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    # Explicit origins only — the wildcard is no longer a default. Add your
    # frontend origin(s), comma-separated, via CORS_ORIGINS.
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Security
    # In production SECRET_KEY MUST be set to a strong random value
    # (enforced below). In development the default is replaced with a
    # random per-process key so nothing runs on a known secret.
    SECRET_KEY: str = "changeme-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Redis (broker / cache); only used when configured.
    REDIS_URL: str = "redis://redis:6379/0"

    # Database
    DATABASE_URL: str = "sqlite:///./digital_campus.db"
    AUTO_CREATE_TABLES: bool = False

    # Backups (PostgreSQL)
    BACKUP_DIR: str = "backups"
    BACKUP_KEEP: int = 14

    # LLM runtime configuration. Set LLM_PROVIDER to a provider ID or
    # ``auto`` to use the first configured provider.
    LLM_PROVIDER: str = "auto"
    GEMINI_MODEL: str = "gemini-2.0-flash"
    OPENAI_MODEL: str = "gpt-4o-mini"
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    OLLAMA_ENABLED: bool = False
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_API_KEY: Optional[str] = None
    OLLAMA_MODEL: str = "llama3.2"
    LLM_TIMEOUT_SECONDS: float = 30.0
    LLM_COOLDOWN_SECONDS: float = 60.0

    # Optional semantic retrieval. Keyword search remains the safe fallback.
    SEMANTIC_SEARCH_ENABLED: bool = False
    EMBED_PROVIDER: str = "openai"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBED_DIM: int = 1536

    # Model Context Protocol tool gateway
    MCP_ENABLED: bool = False
    MCP_URL: str = "http://mcp:8765/mcp"
    MCP_HOST: str = "0.0.0.0"
    MCP_PORT: int = 8765
    MCP_AUTH_TOKEN: Optional[str] = None
    MCP_REQUIRE_AUTH: bool = True
    MCP_ALLOW_MUTATIONS: bool = False

    # Optional LLM providers
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    # KUDOS Terminal: auto-open a session during ask when the question looks
    # like code KUDOS should test. Agent shell commands always require
    # superadmin approval regardless of this flag.
    KUDOS_TERMINAL_AUTO_OPEN: bool = True
    KUDOS_TERMINAL_WORKSPACE_ROOT: str = ""

    # Additional application API keys. Both comma- and newline-separated
    # values are accepted in environment variables and .env files.
    API_KEYS: Annotated[List[str], NoDecode] = []

    @field_validator("API_KEYS", mode="before")
    @classmethod
    def parse_api_keys(cls, value: Any) -> List[str]:
        """Normalize API_KEYS from either a list or a delimited string."""
        if value is None:
            return []

        if isinstance(value, str):
            raw_value = value.strip()
            if not raw_value:
                return []

            # Pydantic Settings may leave a JSON list as a string on some
            # versions. Support it in addition to the documented delimiters.
            if raw_value.startswith("["):
                try:
                    value = json.loads(raw_value)
                except json.JSONDecodeError:
                    pass
                else:
                    if isinstance(value, list):
                        return [str(key).strip() for key in value if str(key).strip()]

            return [
                key.strip()
                for key in re.split(r"[,\r\n]+", raw_value)
                if key.strip()
            ]

        if isinstance(value, (list, tuple, set)):
            return [str(key).strip() for key in value if str(key).strip()]

        return value

    @model_validator(mode="after")
    def _harden(self) -> "Settings":
        """Fail fast on insecure defaults when running in production; in
        development, replace the known default secret with a random key."""
        if self.APP_ENV == "production":
            if not self.SECRET_KEY or self.SECRET_KEY == "changeme-in-production":
                raise ValueError(
                    "SECRET_KEY must be a strong random value when APP_ENV=production"
                )
            if len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "SECRET_KEY must be at least 32 characters when APP_ENV=production"
                )
            if self.DEBUG:
                raise ValueError("DEBUG must be false when APP_ENV=production")
        else:
            if not self.SECRET_KEY or self.SECRET_KEY == "changeme-in-production":
                import logging
                import secrets

                logging.getLogger("config").warning(
                    "SECRET_KEY is not set (development) — generating a random "
                    "per-process key. Set SECRET_KEY in production."
                )
                object.__setattr__(self, "SECRET_KEY", secrets.token_urlsafe(32))
        return self


settings = Settings()
