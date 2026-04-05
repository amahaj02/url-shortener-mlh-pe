# TEMP: request logs → in-memory buffer → Discord webhook on an interval. Delete this file + __init__ imports when done.
# Paste webhook below. Runs during normal server and during pytest (TESTING=true).

from __future__ import annotations

import atexit
import contextlib
import json
import logging
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from flask import Flask, Response, g, request

logger = logging.getLogger(__name__)

_BUFFER_LOCK = threading.Lock()
_BUFFER: list[str] = []
_MAX_BUFFER_LINES = 3000

_START_LOCK = threading.Lock()
_started = False

_DISCORD_CONTENT_LIMIT = 1900
_MAX_BODY_CHARS = 8000
_FLUSH_INTERVAL_SEC = 10.0
_EXCLUDE_PATHS = ("/health", "/metrics")

# Hackathon: paste incoming webhook URL here so participant test runs can ship logs to your channel.
_DISCORD_WEBHOOK_URL = ""

_SENSITIVE_KEY_HINTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "cookie",
)


def _buffer_append(line: str) -> None:
    with _BUFFER_LOCK:
        _BUFFER.append(line)
        overflow = len(_BUFFER) - _MAX_BUFFER_LINES
        if overflow > 0:
            del _BUFFER[:overflow]


def _buffer_drain() -> str:
    with _BUFFER_LOCK:
        if not _BUFFER:
            return ""
        text = "".join(_BUFFER)
        _BUFFER.clear()
        return text


def _should_redact_key(key: str) -> bool:
    lower = key.lower()
    return any(h in lower for h in _SENSITIVE_KEY_HINTS)


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: ("[REDACTED]" if _should_redact_key(k) else _redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


def _parse_body_for_log(raw: bytes, content_type: str | None) -> Any:
    if not raw:
        return None
    ct = (content_type or "").lower()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"encoding": "non-utf8", "length": len(raw)}
    if len(text) > _MAX_BODY_CHARS:
        text = text[:_MAX_BODY_CHARS] + f"...(truncated, {len(raw)} bytes total)"
    if "json" in ct:
        try:
            parsed = json.loads(text)
            return _redact(parsed)
        except json.JSONDecodeError:
            return text
    return text


def _excluded_path(path: str) -> bool:
    if path == "/":
        return True
    return any(path == p or path.startswith(p.rstrip("/") + "/") for p in _EXCLUDE_PATHS)


def _chunk_discord_messages(text: str) -> list[str]:
    if len(text) <= _DISCORD_CONTENT_LIMIT:
        return [text] if text else []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + _DISCORD_CONTENT_LIMIT])
        start += _DISCORD_CONTENT_LIMIT
    return chunks


def _http_error_body(err: urllib.error.HTTPError) -> str:
    with contextlib.suppress(Exception):
        raw = err.read()
        return raw.decode("utf-8", errors="replace")[:800]
    return ""


_DISCORD_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "PE-Hackathon-TempLog/1.0 (+local_discord_log.py)",
}


def _post_discord(webhook_url: str, content: str) -> None:
    body = json.dumps({"content": content}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=body,
        headers=_DISCORD_HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status not in (200, 204):
            raise RuntimeError(f"unexpected status {resp.status}")


def _ping_webhook_async(webhook_url: str) -> None:
    """One message ~1s after startup so you know the webhook works before the first flush."""

    def _run() -> None:
        time.sleep(1.0)
        try:
            _post_discord(
                webhook_url,
                "temp discord log: webhook OK (remove local_discord_log.py after testing)",
            )
            logger.warning("temp discord log: startup ping sent — check Discord")
        except urllib.error.HTTPError as e:
            logger.error(
                "temp discord log: startup ping failed HTTP %s %s — %s",
                e.code,
                e.reason,
                _http_error_body(e),
            )
        except OSError as e:
            logger.error("temp discord log: startup ping failed: %s", e)

    threading.Thread(target=_run, name="temp-discord-ping", daemon=True).start()


def _flush_worker(webhook_url: str, interval_sec: float) -> None:
    while True:
        try:
            batch = _buffer_drain()
            if not batch.strip():
                time.sleep(interval_sec)
                continue
            stripped = batch.strip()
            line_count = len([ln for ln in stripped.splitlines() if ln.strip()])
            chunks = [c for c in _chunk_discord_messages(stripped) if c]
            for chunk in chunks:
                _post_discord(webhook_url, f"```\n{chunk}\n```")
            logger.warning(
                "temp discord log: sent %s request line(s) as %s Discord message(s)",
                line_count,
                len(chunks),
            )
        except urllib.error.HTTPError as e:
            logger.error(
                "temp discord log: HTTP %s %s %s",
                e.code,
                e.reason,
                _http_error_body(e),
            )
        except urllib.error.URLError as e:
            logger.error("temp discord log: %s", e.reason)
        except Exception:
            logger.exception("temp discord log: flush failed")
        time.sleep(interval_sec)


def _register_exit_flush(webhook_url: str) -> None:
    """Short test runs may finish before the next interval; drain buffer on process exit."""

    def _final_flush() -> None:
        batch = _buffer_drain()
        if not batch.strip():
            return
        try:
            stripped = batch.strip()
            line_count = len([ln for ln in stripped.splitlines() if ln.strip()])
            chunks = [c for c in _chunk_discord_messages(stripped) if c]
            for chunk in chunks:
                _post_discord(webhook_url, f"```\n{chunk}\n```")
            logger.warning(
                "temp discord log: exit flush sent %s request line(s) as %s Discord message(s)",
                line_count,
                len(chunks),
            )
        except Exception:
            logger.exception("temp discord log: exit flush failed")

    atexit.register(_final_flush)


def _ensure_started(webhook_url: str, interval_sec: float) -> None:
    global _started
    with _START_LOCK:
        if _started:
            return
        threading.Thread(
            target=_flush_worker,
            args=(webhook_url, interval_sec),
            name="temp-discord-log",
            daemon=True,
        ).start()
        _started = True


def init_local_discord_request_logging(app: Flask, *, testing: bool) -> None:
    _ = testing  # still register hooks under pytest so test client requests are logged
    webhook = _DISCORD_WEBHOOK_URL.strip()
    if not webhook:
        return
    if not webhook.startswith("https://") or "/api/webhooks/" not in webhook:
        logger.warning("temp discord log: bad webhook URL, skipping")
        return

    logger.warning(
        "temp discord log: enabled (in-memory buffer, flush ~%ss; skips / /health /metrics)",
        int(_FLUSH_INTERVAL_SEC),
    )

    @app.before_request
    def _cache_body_for_discord_log() -> None:
        request.get_data(cache=True)

    @app.after_request
    def _record_request_for_discord_log(response: Response) -> Response:
        try:
            if _excluded_path(request.path):
                return response
            raw = request.get_data(cache=True)
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "method": request.method,
                "path": request.path,
                "query": request.query_string.decode("utf-8", errors="replace") if request.query_string else "",
                "status": response.status_code,
                "content_type": request.content_type,
                "request_body": _parse_body_for_log(raw, request.content_type),
            }
            rid = getattr(g, "request_id", None)
            if rid:
                entry["request_id"] = rid
            _buffer_append(json.dumps(entry, default=str) + "\n")
        except Exception:
            logger.exception("temp discord log: record failed")
        return response

    _ping_webhook_async(webhook)
    _register_exit_flush(webhook)
    _ensure_started(webhook, _FLUSH_INTERVAL_SEC)
