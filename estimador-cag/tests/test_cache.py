import fakeredis
import pytest

from services.cache import EstimationCache


@pytest.fixture
def cache() -> EstimationCache:
    return EstimationCache(fakeredis.FakeRedis(decode_responses=True), ttl=60)


def test_set_then_get_roundtrips_payload(cache: EstimationCache) -> None:
    payload = {"summary": "ok", "total_cost_eur": 1000}
    cache.set("estimation:v2:abc", payload)
    assert cache.get("estimation:v2:abc") == payload


def test_get_returns_none_on_miss(cache: EstimationCache) -> None:
    assert cache.get("estimation:v2:missing") is None


def test_set_applies_ttl(cache: EstimationCache) -> None:
    cache.set("estimation:v2:ttl", {"x": 1})
    ttl = cache.redis.ttl("estimation:v2:ttl")
    assert 0 < ttl <= 60
