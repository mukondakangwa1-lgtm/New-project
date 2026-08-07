"""Application configuration loaded from environment variables and ``.env``."""

import json
import re
from typing import Annotated, Any, List, Optional

from pydantic import ConfigDict, field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    """Runtime settings for the Digital Campus backend.

    Unknown values in ``.env`` are allowed so that infrastructure-specific
    settings (for example Redis or Celery configuration) can be supplied
    without making the application fail during import.
    """

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

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

    # Database
    DATABASE_URL: str = "sqlite:///./digital_campus.db"

    # Optional LLM providers
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

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


settings = Settings()
