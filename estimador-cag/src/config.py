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
    LLM_TIMEOUT: int = 30
    PRIMARY_MODEL: str = "gpt-4o-mini"
    FALLBACK_MODEL: str = "claude-haiku-4-5-20251001"
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL: int = 86400
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    SEMANTIC_CACHE_THRESHOLD: float = 0.85
    SEMANTIC_CACHE_TTL: int = 86400
    SEMANTIC_CACHE_LOG_ONLY: bool = False
    DATABASE_URL: str | None = None
    ESTIMATOR_API_BASE_URL: str = "http://localhost:8000"
    MAX_CONVERSATION_TURNS: int = 6
    MAX_ATTACHMENT_CHARS: int = 60000
    METADATA_EXTRACTOR_MODEL: str = "gpt-4o-mini"
    ANCHOR_DETECTION_MODE: Literal["heuristic", "llm"] = "heuristic"
    COMPRESSION_MODEL: str = "gpt-4o-mini"
    CONVERSATIONAL_PROMPT_VERSION: str = "v3"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "DEBUG"

    @property
    def llm_configured(self) -> bool:
        return bool(self.OPENAI_API_KEY or self.ANTHROPIC_API_KEY)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings (singleton)."""
    return Settings()