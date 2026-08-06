from typing import List, Optional from pydantic_settings import BaseSettings from pydantic import field_validator, ConfigDict

class Settings(BaseSettings): DATABASE_URL: str = "sqlite:///./digital_campus.db" HOST: str = "0.0.0.0" PORT: int = 8000 DEBUG: bool = False

Code
# known single-key provider envs (optional)
OPENAI_API_KEY: Optional[str] = None
GOOGLE_GEMINI_API_KEY: Optional[str] = None
GROQ_API_KEY: Optional[str] = None

# will contain all API keys from the API_KEYS env var (comma- or newline-separated)
API_KEYS: List[str] = []

# allow unknown/extra env vars so Settings() won't raise on unrelated keys
model_config = ConfigDict(extra="allow")

@field_validator("API_KEYS", mode="before")
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
single shared settings instance used across the app
settings = Settings()
