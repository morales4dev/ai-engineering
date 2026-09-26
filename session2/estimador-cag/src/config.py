from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from utils import get_absolute_path


ENV_FILE = f"{get_absolute_path()}/../.env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file.

    API keys may be missing. The process must still boot so /health can say so.
    """

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8")

    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    LLM_PROVIDER: Literal["openai", "anthropic"] = "anthropic"
    LLM_MODEL: str = "claude-haiku-4-5"
    LLM_TIMEOUT: int = 30
    LLM_RETRIES: int = 2
    PRIMARY_MODEL: str = "gpt-4o-mini"
    FALLBACK_MODEL: str = "claude-haiku-4-5-20251001"
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL: int = 86400
    ESTIMATOR_API_BASE_URL: str = "http://localhost:8000"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "DEBUG"

    @property
    def llm_configured(self) -> bool:
        return bool(self.OPENAI_API_KEY or self.ANTHROPIC_API_KEY)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings (singleton)."""
    return Settings()