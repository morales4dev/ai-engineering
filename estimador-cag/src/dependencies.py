"""FastAPI / service factories for shared singletons."""

from functools import lru_cache

import redis
import structlog
from openai import OpenAI

from cache.semantic import EstimationSemanticCache
from config import get_settings
from services.cache import EstimationCache
from services.llm_wrapper import LLMWrapper

log = structlog.get_logger()


@lru_cache
def get_cache() -> EstimationCache:
    settings = get_settings()
    return EstimationCache.from_url(settings.REDIS_URL, ttl=settings.CACHE_TTL)


@lru_cache
def get_llm_wrapper() -> LLMWrapper:
    settings = get_settings()
    return LLMWrapper(
        openai_api_key=settings.OPENAI_API_KEY,
        anthropic_api_key=settings.ANTHROPIC_API_KEY,
        primary_model=settings.PRIMARY_MODEL,
        timeout=settings.LLM_TIMEOUT,
    )


@lru_cache
def get_openai_client() -> OpenAI | None:
    """OpenAI client for moderation (step 2) and later embeddings. None without a key."""
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        return None
    return OpenAI(api_key=settings.OPENAI_API_KEY)


@lru_cache
def get_semantic_cache() -> EstimationSemanticCache | None:
    """Build the semantic cache, or None if embeddings / RediSearch are unavailable."""
    settings = get_settings()
    if get_openai_client() is None:
        log.warning("semantic_cache_disabled", reason="no_openai_key")
        return None

    try:
        from redisvl.utils.vectorize import OpenAITextVectorizer

        vectorizer = OpenAITextVectorizer(
            model=settings.EMBEDDING_MODEL,
            api_config={"api_key": settings.OPENAI_API_KEY},
        )
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=False)
        return EstimationSemanticCache(
            redis_client=redis_client,
            vectorizer=vectorizer,
            threshold=settings.SEMANTIC_CACHE_THRESHOLD,
            ttl=settings.SEMANTIC_CACHE_TTL,
            log_only=settings.SEMANTIC_CACHE_LOG_ONLY,
        )
    except Exception as exc:  # noqa: BLE001 — exact-match must keep working
        log.warning(
            "semantic_cache_disabled",
            reason="setup_failed",
            error_type=type(exc).__name__,
            error=str(exc)[:200],
        )
        return None
