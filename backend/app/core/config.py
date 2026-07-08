"""
Centralized application configuration.
All secrets and environment-specific values are loaded from environment
variables (see .env.example). Never hardcode secrets here.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "SmileyGPT"
    ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Database
    DATABASE_URL: str = "postgresql+psycopg+asyncio://smiley:smiley@postgres:5432/smileygpt"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # LLM Provider (OpenAI-compatible; works with OpenAI, Groq, Ollama, etc.)
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_DEFAULT_MODEL: str = "gpt-4o-mini"
    LLM_VISION_MODEL: str = "gpt-4o-mini"
    AVAILABLE_MODELS: List[str] = ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"]

    # Vector memory (Chroma, embedded persistent store)
    CHROMA_PERSIST_DIR: str = "/data/chroma"
    MEMORY_TOP_K: int = 5

    # File uploads
    UPLOAD_DIR: str = "/data/uploads"
    MAX_UPLOAD_MB: int = 20

    # Admin
    ADMIN_EMAILS: List[str] = []


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
