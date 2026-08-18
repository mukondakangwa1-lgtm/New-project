from typing import List, Optional

from pydantic import ConfigDict, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Digital Campus"
    APP_VERSION: str = "1.0.0"

    DATABASE_URL: str = "sqlite:///./digital_campus.db"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    SECRET_KEY: str = "change-me-in-production-use-a-long-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # known single-key provider envs (optional)
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    # will contain all API keys from the API_KEYS env var (comma- or newline-separated)
    API_KEYS: List[str] = []

    # comma-separated origins, or * for any (launch default)
    CORS_ORIGINS: str = "*"

    # campus_help = public Digital Campus guide (no 270-agent HQ)
    # hq = local KUDOS on the superadmin PC
    KUDOS_MODE: str = "campus_help"
    QUOTA_SAFE: bool = True

    # allow unknown/extra env vars so Settings() won't raise on unrelated keys
    model_config = ConfigDict(extra="allow", env_file=".env", env_file_encoding="utf-8")

    @field_validator("API_KEYS", mode="before")
    @classmethod
    def _split_api_keys(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            parts = []
            for part in v.replace("\r\n", "\n").replace("\n", ",").split(","):
                s = part.strip()
                if s:
                    parts.append(s)
            return parts
        return v

    def cors_origins_list(self) -> List[str]:
        raw = (self.CORS_ORIGINS or "*").strip()
        if raw == "*":
            return ["*"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]


# single shared settings instance used across the app
settings = Settings()
