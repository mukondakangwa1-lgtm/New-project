"""Application configuration loaded from environment variables and ``.env``.

The env file is resolved relative to this file (``services/backend/.env``)
rather than the current working directory, so the SECRET_KEY and other
secrets load no matter where the process is launched from. Override with the
``KUDOS_ENV_FILE`` environment variable when needed.
"""

import json
import os
import re
from typing import Annotated, Any

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

    # When True, new registrations are marked pending and can only log in
    # after a superadmin approves them (admin accounts and existing users
    # are unaffected).
    REQUIRE_APPROVAL: bool = False

    # Redis (broker / cache); only used when configured.
    REDIS_URL: str = "redis://redis:6379/0"

    # Database
    DATABASE_URL: str = "sqlite:///./digital_campus.db"
    AUTO_CREATE_TABLES: bool = False

    # Backups (PostgreSQL)
    BACKUP_DIR: str = "backups"
    BACKUP_KEEP: int = 14

    # Object storage (MinIO with local-disk fallback)
    # STORAGE_BACKEND: auto -> MinIO when configured, else local disk;
    #                  minio -> require MinIO; local -> always local disk.
    STORAGE_BACKEND: str = "auto"
    STORAGE_LOCAL_DIR: str = "uploads"  # relative to storage-local/ when not absolute
    MINIO_ENDPOINT: str = ""  # host:port, e.g. minio:9000
    MINIO_ACCESS_KEY: str | None = None  # scoped app user (not root)
    MINIO_SECRET_KEY: str | None = None
    MINIO_BUCKET: str = "kudos"
    MINIO_SECURE: bool = False  # True for TLS against MinIO
    MINIO_REGION: str = "us-east-1"

    # LLM runtime configuration. Set LLM_PROVIDER to a provider ID or
    # ``auto`` to use the first configured provider.
    LLM_PROVIDER: str = "auto"
    GEMINI_MODEL: str = "gemini-2.0-flash"
    OPENAI_MODEL: str = "gpt-4o-mini"
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    OLLAMA_ENABLED: bool = False
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_API_KEY: str | None = None
    OLLAMA_MODEL: str = "llama3.2"
    LLM_TIMEOUT_SECONDS: float = 30.0
    LLM_COOLDOWN_SECONDS: float = 60.0

    # Vision + media generation (auto-detected by provider key availability).
    GEMINI_IMAGE_MODEL: str = "gemini-2.5-flash-image"
    OPENAI_IMAGE_MODEL: str = "gpt-image-1"
    # Video generation (up to MAX_VIDEO_SECONDS; clips are stitched together).
    GEMINI_VIDEO_MODEL: str = "veo-3.0-generation-001"
    OPENAI_VIDEO_MODEL: str = "sora-2"
    VIDEO_CLIP_MAX_SECONDS: int = 8
    MAX_VIDEO_SECONDS: int = 300  # 5 minutes
    # Chat/agent videos are short clips only, served as single-use downloads
    # and never persisted to object storage.
    MAX_CHAT_VIDEO_SECONDS: int = 10

    # KUDOS Voice — speech-to-text & text-to-speech.
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_TTS_MODEL: str = "eleven_multilingual_v2"
    ELEVENLABS_S2S_MODEL: str = "eleven_multilingual_sts_v2"  # voice changer (speech-to-speech)
    OPENAI_TTS_MODEL: str = "gpt-4o-mini-tts"
    OPENAI_TTS_VOICE: str = "nova"  # fallback voice until the signature voice is cloned
    # Signature voice: minimum clear speech captured before auto-clone on first feed.
    KUDOS_SIGNATURE_MIN_SAMPLE_SECONDS: int = 30

    # Registered external tool execution
    TOOL_CALL_TIMEOUT_SECONDS: float = 30.0
    TOOL_CALL_MAX_RESPONSE_CHARS: int = 8000

    # networkops sidecar (KUDOS network doctor). Empty = feature disabled.
    NETWORKOPS_URL: str = ""

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
    MCP_AUTH_TOKEN: str | None = None
    MCP_REQUIRE_AUTH: bool = True
    MCP_ALLOW_MUTATIONS: bool = False

    # Optional LLM providers
    OPENAI_API_KEY: str | None = None
    GOOGLE_GEMINI_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None

    # KUDOS Terminal: auto-open a session during ask when the question looks
    # like code KUDOS should test. Agent shell commands always require
    # superadmin approval regardless of this flag.
    KUDOS_TERMINAL_AUTO_OPEN: bool = True
    KUDOS_TERMINAL_WORKSPACE_ROOT: str = ""

    # KUDOS continuous learning: the first site visit starts the never-ending
    # learning loop (persisted on disk, resumes after restarts). Admins can
    # still stop it; the next visit re-arms it.
    KUDOS_LEARN_ON_VISIT: bool = True
    KUDOS_LEARN_INTERVAL_MINUTES: int = 120

    # KUDOS Offline Brain — persistent self-contained knowledge + reasoning.
    # When OFFLINE_FIRST, KUDOS answers from its own brain before asking any
    # LLM. When GROUNDED_ONLY, LLM answers are verified against real sources
    # and replaced by a grounded (or honestly-refusing) answer when unsupported.
    KUDOS_OFFLINE_FIRST: bool = False
    KUDOS_GROUNDED_ONLY: bool = True
    KUDOS_BRAIN_MIN_SCORE: float = 0.6  # minimum confidence for a grounded reply
    KUDOS_BRAIN_CONSOLIDATE_LIMIT: int = 300

    # KUDOS Governance & Continuity — rotating superadmin identity and the
    # transparent succession policy. uid rotates on login every
    # UID_ROTATE_DAYS; if the superadmin is inactive for SUCCESSOR_DAYS the
    # dashboard shows KUDOS as self-managed; REVIVAL_YEARS later it considers
    # itself fully self-sustaining. All state is visible in the root panel.
    KUDOS_UID_ROTATE_DAYS: int = 5
    KUDOS_SUCCESSOR_INACTIVE_DAYS: int = 1095  # 3 years
    KUDOS_REVIVAL_YEARS: int = 5

    # Additional application API keys. Both comma- and newline-separated
    # values are accepted in environment variables and .env files.
    API_KEYS: Annotated[list[str], NoDecode] = []

    @field_validator("API_KEYS", mode="before")
    @classmethod
    def parse_api_keys(cls, value: Any) -> list[str]:
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

            return [key.strip() for key in re.split(r"[,\r\n]+", raw_value) if key.strip()]

        if isinstance(value, (list, tuple, set)):
            return [str(key).strip() for key in value if str(key).strip()]

        return value

    @model_validator(mode="after")
    def _harden(self) -> "Settings":
        """Fail fast on insecure defaults when running in production; in
        development, replace the known default secret with a random key."""
        if self.APP_ENV == "production":
            if not self.SECRET_KEY or self.SECRET_KEY == "changeme-in-production":
                raise ValueError("SECRET_KEY must be a strong random value when APP_ENV=production")
            if len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY must be at least 32 characters when APP_ENV=production")
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
