"""
Redis cache for short-code redirect resolution.

- TESTING=true: in-memory FakeRedis (no server).
- Otherwise: set REDIS_URL, or REDIS_HOST (and optional REDIS_PORT, REDIS_PASSWORD, REDIS_DB).
- If Redis is not configured, caching is disabled (always DB lookup).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

KEY_PREFIX = "urlshort:sc:"

_redis: Any | None = None


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _testing() -> bool:
    return os.getenv("TESTING", "").strip().lower() in {"1", "true", "yes", "on"}


def _key(short_code: str) -> str:
    return f"{KEY_PREFIX}{short_code}"


def _ttl_seconds() -> int | None:
    raw = os.getenv("REDIS_CACHE_TTL_SECONDS")
    if raw is None or not str(raw).strip():
        return 86400
    try:
        v = int(str(raw).strip())
    except ValueError:
        return 86400
    if v <= 0:
        return None
    return v


def _log_redis_connected(client: Any, label: str) -> None:
    try:
        client.ping()
    except Exception as exc:
        logger.warning("redis cache: client created but ping failed (%s): %s", label, exc)
        return
    logger.info("redis cache: connected (%s)", label)


def init_cache(app) -> None:
    """Attach a Redis client to app.extensions['redis'], or None if caching is off."""
    global _redis
    client: Any | None = None

    if _testing():
        from fakeredis import FakeRedis

        client = FakeRedis(decode_responses=True)
        logger.info("redis cache: fakeredis (TESTING)")
    else:
        url = os.getenv("REDIS_URL", "").strip()
        host = os.getenv("REDIS_HOST", "").strip()
        if url:
            import redis

            client = redis.from_url(url, decode_responses=True)
            _log_redis_connected(client, "REDIS_URL")
        elif host:
            import redis

            port = _env_int("REDIS_PORT", 6379)
            password = os.getenv("REDIS_PASSWORD") or None
            db = _env_int("REDIS_DB", 0)
            client = redis.Redis(
                host=host,
                port=port,
                password=password,
                db=db,
                decode_responses=True,
            )
            _log_redis_connected(client, f"{host}:{port} db={db}")
        else:
            logger.info("redis cache: disabled (set REDIS_URL or REDIS_HOST to enable)")

    _redis = client
    app.extensions["redis"] = client


def enabled() -> bool:
    return _redis is not None


def get_short_link(short_code: str) -> dict[str, Any] | None:
    """Return cached payload for redirect, or None if miss / disabled."""
    if _redis is None or not short_code:
        return None
    try:
        raw = _redis.get(_key(short_code))
    except Exception:
        logger.exception("redis get failed for short_code")
        return None
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    for field in ("id", "short_code", "original_url", "is_active", "user_id"):
        if field not in data:
            return None
    return data


def set_short_link(url_entry) -> None:
    """Cache fields needed for redirect and event logging."""
    if _redis is None:
        return
    sc = getattr(url_entry, "short_code", None)
    if not sc:
        return
    row_id = getattr(url_entry, "id", None)
    if row_id is None:
        return
    is_active = bool(getattr(url_entry, "is_active", True))
    payload = {
        "id": row_id,
        "short_code": sc,
        "original_url": url_entry.original_url,
        "is_active": is_active,
        "user_id": getattr(url_entry, "user_id", None),
    }
    try:
        ttl = _ttl_seconds()
        raw = json.dumps(payload, separators=(",", ":"))
        k = _key(sc)
        if ttl:
            _redis.setex(k, ttl, raw)
        else:
            _redis.set(k, raw)
    except Exception:
        logger.exception("redis set failed for short_code=%s", sc)


def delete_short_link(short_code: str | None) -> None:
    if _redis is None or not short_code:
        return
    try:
        _redis.delete(_key(short_code))
    except Exception:
        logger.exception("redis delete failed for short_code=%s", short_code)


def clear_namespace() -> None:
    """Remove all app cache keys (e.g. after admin DB wipe)."""
    if _redis is None:
        return
    try:
        for key in _redis.scan_iter(match=f"{KEY_PREFIX}*"):
            _redis.delete(key)
    except Exception:
        logger.exception("redis clear_namespace failed")
