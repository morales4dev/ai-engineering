"""Runtime-mutable model configuration, backed by Redis.

``Settings`` (.env) stays the immutable layer of *defaults*; this store holds
runtime *overrides* as deltas in a Redis hash, so the instructor can switch
models from the Ajustes tab mid-session without editing .env or recreating
containers. Overrides survive ``--reload`` restarts and are shared across
workers (Redis is the source of truth, read on every call).

Failure semantics:
- Reads degrade gracefully: if Redis is down, ``effective()`` falls back to
  the settings default (the service behaves exactly as configured by .env).
- Writes re-raise (`RuntimeConfigUnavailable`): a failed override must be
  visible to the caller — the API maps it to a 503.
"""

from __future__ import annotations

import math

import redis
import structlog

from config import Settings

log = structlog.get_logger()

# The LLM model knobs that can be overridden at runtime. Each name is also a
# ``Settings`` field (the default). EMBEDDING_MODEL is deliberately absent:
# changing it would invalidate every stored vector, so it stays .env-only.
MODEL_KEYS: tuple[str, ...] = (
    "PRIMARY_MODEL",
    "CRITIC_MODEL",
    "METADATA_EXTRACTOR_MODEL",
    "COMPRESSION_MODEL",
    "PROPOSITIONAL_CHUNKER_MODEL",
    "CONTEXTUAL_CHUNKER_MODEL",
)

HASH_KEY = "estimator:runtime_config"
RETRIEVAL_HASH_KEY = "estimator:runtime_retrieval"

RETRIEVAL_KEYS: tuple[str, ...] = (
    "RETRIEVAL_SEARCH_MODE",
    "RERANKER_ENABLED",
    "RETRIEVAL_ROUTING_ENABLED",
    "QUERY_TRANSFORM_ENABLED",
    "TEMPORAL_DECAY_ENABLED",
    "TASK_HOURS_TOP_K",
    "TASK_HOURS_DISTANCE_THRESHOLD",
)


class RuntimeConfigUnavailable(Exception):
    """Raised when an override WRITE fails (Redis unreachable)."""


class RuntimeModelConfig:
    """Redis-hash-backed override store for the LLM model knobs."""

    def __init__(self, redis_client: redis.Redis, settings: Settings) -> None:
        self._redis = redis_client
        self._settings = settings

    @classmethod
    def from_url(cls, url: str, settings: Settings) -> "RuntimeModelConfig":
        return cls(redis.from_url(url, decode_responses=True), settings)

    def get(self, key: str) -> str | None:
        """Return the override for ``key``, or ``None`` (unset / Redis down)."""
        self._validate_key(key)
        try:
            return self._redis.hget(HASH_KEY, key)
        except redis.RedisError as exc:
            log.warning("runtime_config_read_failed", key=key, error=str(exc)[:200])
            return None

    def set(self, key: str, value: str | None) -> None:
        """Set the override for ``key``; ``None`` clears it (back to default)."""
        self._validate_key(key)
        try:
            if value is None:
                self._redis.hdel(HASH_KEY, key)
            else:
                self._redis.hset(HASH_KEY, key, value)
        except redis.RedisError as exc:
            raise RuntimeConfigUnavailable(str(exc)) from exc

    def effective(self, key: str) -> str:
        """The value the pipeline should use: override if set, else the default."""
        return self.get(key) or self.default(key)

    def default(self, key: str) -> str:
        self._validate_key(key)
        return getattr(self._settings, key)

    def is_overridden(self, key: str) -> bool:
        return self.get(key) is not None

    def snapshot(self) -> dict[str, dict[str, str | bool]]:
        """One entry per model key: ``{effective, default, overridden}``."""
        try:
            overrides = self._redis.hgetall(HASH_KEY)
        except redis.RedisError as exc:
            log.warning("runtime_config_read_failed", key="*", error=str(exc)[:200])
            overrides = {}
        return {
            key: {
                "effective": overrides.get(key) or self.default(key),
                "default": self.default(key),
                "overridden": key in overrides,
            }
            for key in MODEL_KEYS
        }

    def reset_all(self) -> None:
        """Drop every override (back to .env defaults)."""
        try:
            self._redis.delete(HASH_KEY)
        except redis.RedisError as exc:
            raise RuntimeConfigUnavailable(str(exc)) from exc

    @staticmethod
    def _validate_key(key: str) -> None:
        if key not in MODEL_KEYS:
            raise ValueError(f"Unknown model key: {key}")


class RuntimeRetrievalConfig:
    """Redis-hash-backed overrides for retrieval and task-hours controls."""

    def __init__(self, redis_client: redis.Redis, settings: Settings) -> None:
        self._redis = redis_client
        self._settings = settings

    @classmethod
    def from_url(cls, url: str, settings: Settings) -> "RuntimeRetrievalConfig":
        return cls(redis.from_url(url, decode_responses=True), settings)

    def _get(self, key: str) -> str | None:
        self._validate_key(key)
        try:
            return self._redis.hget(RETRIEVAL_HASH_KEY, key)
        except redis.RedisError as exc:
            log.warning("runtime_retrieval_read_failed", key=key, error=str(exc)[:200])
            return None

    def _set(self, key: str, value: str | None) -> None:
        self._validate_key(key)
        try:
            if value is None:
                self._redis.hdel(RETRIEVAL_HASH_KEY, key)
            else:
                self._redis.hset(RETRIEVAL_HASH_KEY, key, value)
        except redis.RedisError as exc:
            raise RuntimeConfigUnavailable(str(exc)) from exc

    def _effective(self, key: str) -> str:
        return self._get(key) or str(getattr(self._settings, key))

    def effective_search_mode(self) -> str:
        value = self._effective("RETRIEVAL_SEARCH_MODE")
        return value if value in ("vector", "hybrid") else self._settings.RETRIEVAL_SEARCH_MODE

    def effective_rerank(self) -> bool:
        return self._effective_bool("RERANKER_ENABLED")

    def effective_routing(self) -> bool:
        return self._effective_bool("RETRIEVAL_ROUTING_ENABLED")

    def effective_query_transform(self) -> bool:
        return self._effective_bool("QUERY_TRANSFORM_ENABLED")

    def effective_temporal_decay(self) -> bool:
        return self._effective_bool("TEMPORAL_DECAY_ENABLED")

    def _effective_bool(self, key: str) -> bool:
        value = self._effective(key).strip().lower()
        if value in ("true", "1", "yes"):
            return True
        if value in ("false", "0", "no"):
            return False
        return bool(getattr(self._settings, key))

    def effective_task_hours_top_k(self) -> int:
        try:
            value = int(self._effective("TASK_HOURS_TOP_K"))
        except (TypeError, ValueError):
            return self._settings.TASK_HOURS_TOP_K
        return value if 1 <= value <= 30 else self._settings.TASK_HOURS_TOP_K

    def effective_task_hours_distance_threshold(self) -> float:
        try:
            value = float(self._effective("TASK_HOURS_DISTANCE_THRESHOLD"))
        except (TypeError, ValueError):
            return self._settings.TASK_HOURS_DISTANCE_THRESHOLD
        return (
            value
            if math.isfinite(value) and 0 <= value <= 2
            else self._settings.TASK_HOURS_DISTANCE_THRESHOLD
        )

    def set_search_mode(self, value: str | None) -> None:
        if value is not None and value not in ("vector", "hybrid"):
            raise ValueError("RETRIEVAL_SEARCH_MODE must be 'vector' or 'hybrid'")
        self._set("RETRIEVAL_SEARCH_MODE", value)

    def set_rerank(self, value: bool | None) -> None:
        self._set("RERANKER_ENABLED", None if value is None else str(value).lower())

    def set_routing(self, value: bool | None) -> None:
        self._set("RETRIEVAL_ROUTING_ENABLED", None if value is None else str(value).lower())

    def set_query_transform(self, value: bool | None) -> None:
        self._set("QUERY_TRANSFORM_ENABLED", None if value is None else str(value).lower())

    def set_temporal_decay(self, value: bool | None) -> None:
        self._set("TEMPORAL_DECAY_ENABLED", None if value is None else str(value).lower())

    def set_task_hours_top_k(self, value: int | None) -> None:
        if value is not None and not 1 <= value <= 30:
            raise ValueError("TASK_HOURS_TOP_K must be between 1 and 30")
        self._set("TASK_HOURS_TOP_K", None if value is None else str(value))

    def set_task_hours_distance_threshold(self, value: float | None) -> None:
        if value is not None and (not math.isfinite(value) or not 0 <= value <= 2):
            raise ValueError("TASK_HOURS_DISTANCE_THRESHOLD must be between 0 and 2")
        self._set(
            "TASK_HOURS_DISTANCE_THRESHOLD",
            None if value is None else str(value),
        )

    def snapshot(self) -> dict[str, dict[str, str | bool]]:
        try:
            overrides = self._redis.hgetall(RETRIEVAL_HASH_KEY)
        except redis.RedisError as exc:
            log.warning("runtime_retrieval_read_failed", key="*", error=str(exc)[:200])
            overrides = {}
        return {
            key: {
                "effective": self._effective_snapshot_value(key, overrides.get(key)),
                "default": str(getattr(self._settings, key)),
                "overridden": key in overrides,
            }
            for key in RETRIEVAL_KEYS
        }

    def _effective_snapshot_value(self, key: str, value: str | None) -> str:
        if value is None:
            return str(getattr(self._settings, key))
        if key == "RETRIEVAL_SEARCH_MODE" and value not in ("vector", "hybrid"):
            return str(getattr(self._settings, key))
        if key.endswith("_ENABLED"):
            normalized = value.strip().lower()
            if normalized in ("true", "1", "yes"):
                return "true"
            if normalized in ("false", "0", "no"):
                return "false"
            return str(getattr(self._settings, key)).lower()
        try:
            if key == "TASK_HOURS_TOP_K":
                return str(int(value)) if 1 <= int(value) <= 30 else str(
                    getattr(self._settings, key)
                )
            if key == "TASK_HOURS_DISTANCE_THRESHOLD":
                parsed = float(value)
                return (
                    str(parsed)
                    if math.isfinite(parsed) and 0 <= parsed <= 2
                    else str(getattr(self._settings, key))
                )
        except (TypeError, ValueError):
            return str(getattr(self._settings, key))
        return value

    def reset_all(self) -> None:
        try:
            self._redis.delete(RETRIEVAL_HASH_KEY)
        except redis.RedisError as exc:
            raise RuntimeConfigUnavailable(str(exc)) from exc

    @staticmethod
    def _validate_key(key: str) -> None:
        if key not in RETRIEVAL_KEYS:
            raise ValueError(f"Unknown retrieval key: {key}")
