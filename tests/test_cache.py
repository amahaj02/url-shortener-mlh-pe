import json
import types
from types import SimpleNamespace

from app import cache as cache_module


class FakeRedisClient:
    def __init__(self):
        self.data = {}
        self.deleted = []
        self.set_calls = []

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value
        self.set_calls.append(("set", key, value))

    def setex(self, key, ttl, value):
        self.data[key] = value
        self.set_calls.append(("setex", key, ttl, value))

    def delete(self, key):
        self.deleted.append(key)
        self.data.pop(key, None)

    def scan_iter(self, match=None):
        return [key for key in list(self.data.keys()) if match is None or key.startswith(cache_module.KEY_PREFIX)]

    def ping(self):
        return True


def test_normalize_cached_is_active_handles_supported_types():
    assert cache_module._normalize_cached_is_active(True) is True
    assert cache_module._normalize_cached_is_active(0) is False
    assert cache_module._normalize_cached_is_active(1) is True
    assert cache_module._normalize_cached_is_active("false") is False
    assert cache_module._normalize_cached_is_active("TRUE") is True


def test_ttl_seconds_defaults_invalid_and_non_positive(monkeypatch):
    monkeypatch.delenv("REDIS_CACHE_TTL_SECONDS", raising=False)
    assert cache_module._ttl_seconds() == 86400

    monkeypatch.setenv("REDIS_CACHE_TTL_SECONDS", "bad")
    assert cache_module._ttl_seconds() == 86400

    monkeypatch.setenv("REDIS_CACHE_TTL_SECONDS", "0")
    assert cache_module._ttl_seconds() is None


def test_get_short_link_handles_disabled_missing_and_invalid_payload(monkeypatch):
    monkeypatch.setattr(cache_module, "_redis", None)
    assert cache_module.get_short_link("abc123") is None

    fake = FakeRedisClient()
    monkeypatch.setattr(cache_module, "_redis", fake)
    assert cache_module.get_short_link("abc123") is None

    fake.data[cache_module._key("abc123")] = "{bad"
    assert cache_module.get_short_link("abc123") is None

    fake.data[cache_module._key("abc123")] = json.dumps({"short_code": "abc123"})
    assert cache_module.get_short_link("abc123") is None


def test_get_short_link_returns_normalized_payload(monkeypatch):
    fake = FakeRedisClient()
    fake.data[cache_module._key("abc123")] = json.dumps(
        {
            "id": 1,
            "short_code": "abc123",
            "original_url": "https://example.com",
            "is_active": "1",
            "user_id": 9,
        }
    )
    monkeypatch.setattr(cache_module, "_redis", fake)

    payload = cache_module.get_short_link("abc123")

    assert payload == {
        "id": 1,
        "short_code": "abc123",
        "original_url": "https://example.com",
        "is_active": True,
        "user_id": 9,
    }


def test_set_short_link_uses_ttl_and_skips_missing_identifiers(monkeypatch):
    fake = FakeRedisClient()
    monkeypatch.setattr(cache_module, "_redis", fake)
    monkeypatch.setenv("REDIS_CACHE_TTL_SECONDS", "60")

    cache_module.set_short_link(SimpleNamespace(id=5, short_code="abc123", original_url="https://example.com", is_active=True, user_id=3))
    cache_module.set_short_link(SimpleNamespace(id=None, short_code="missingid", original_url="https://example.com"))
    cache_module.set_short_link(SimpleNamespace(id=9, short_code=None, original_url="https://example.com"))

    assert fake.set_calls[0][0] == "setex"
    assert fake.set_calls[0][1] == cache_module._key("abc123")
    assert fake.set_calls[0][2] == 60
    assert len(fake.set_calls) == 1


def test_delete_short_link_and_clear_namespace(monkeypatch):
    fake = FakeRedisClient()
    fake.data[cache_module._key("one")] = "1"
    fake.data[cache_module._key("two")] = "2"
    fake.data["other:key"] = "3"
    monkeypatch.setattr(cache_module, "_redis", fake)

    cache_module.delete_short_link("one")
    cache_module.clear_namespace()

    assert cache_module._key("one") in fake.deleted
    assert cache_module._key("two") in fake.deleted
    assert "other:key" not in fake.deleted


def test_init_cache_disables_when_no_redis_config(monkeypatch):
    class App:
        extensions = {}

    monkeypatch.setenv("TESTING", "false")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_HOST", raising=False)

    cache_module.init_cache(App)

    assert App.extensions["redis"] is None
    assert cache_module.enabled() is False


def test_init_cache_uses_redis_url_and_host(monkeypatch):
    class App:
        extensions = {}

    calls = []

    class RedisFactory:
        def from_url(self, url, decode_responses=True):
            calls.append(("from_url", url, decode_responses))
            return FakeRedisClient()

        def Redis(self, **kwargs):
            calls.append(("redis", kwargs))
            return FakeRedisClient()

    fake_module = types.SimpleNamespace(from_url=RedisFactory().from_url, Redis=RedisFactory().Redis)

    monkeypatch.setenv("TESTING", "false")
    monkeypatch.setitem(__import__("sys").modules, "redis", fake_module)

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.delenv("REDIS_HOST", raising=False)
    cache_module.init_cache(App)
    assert calls[0][0] == "from_url"

    App.extensions = {}
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("REDIS_PORT", "6380")
    monkeypatch.setenv("REDIS_DB", "2")
    cache_module.init_cache(App)
    assert calls[1][0] == "redis"
    assert calls[1][1]["host"] == "localhost"
    assert calls[1][1]["port"] == 6380
