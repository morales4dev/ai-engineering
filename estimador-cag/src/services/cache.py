"""Exact-match Redis get/set. Keys are built in ``estimate_oneshot()`` (``estimation:v2:…``)."""

from __future__ import annotations

import json
from typing import Any

import redis
import structlog

log = structlog.get_logger()


class EstimationCache:
    """Thin wrapper around redis-py with TTL. Fail-open on Redis errors."""

    def __init__(self, redis_client: redis.Redis, ttl: int = 86400):
        self.redis = redis_client
        self.ttl = ttl

    @classmethod
    def from_url(cls, url: str, ttl: int = 86400) -> "EstimationCache":
        return cls(redis.from_url(url, decode_responses=True), ttl=ttl)

    def get(self, key: str) -> dict[str, Any] | None:
        try:
            cached = self.redis.get(key)
        except redis.RedisError as exc:
            log.warning("cache_get_failed", error=str(exc))
            return None
        if cached:
            log.info("cache_hit", key_prefix=key[:24])
            return json.loads(cached)
        log.info("cache_miss", key_prefix=key[:24])
        return None

    def set(self, key: str, response: dict[str, Any]) -> None:
        try:
            self.redis.setex(key, self.ttl, json.dumps(response))
            log.info("cache_stored", key_prefix=key[:24], ttl=self.ttl)
        except redis.RedisError as exc:
            log.warning("cache_set_failed", error=str(exc))
