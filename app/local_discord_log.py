# TEMP: one-off request → file → Discord webhook. Delete this file and remove the two lines in app/__init__.py that mention it.
# Paste webhook below, run server, hit a route (not /health or /metrics), wait ~30s, then delete.

from __future__ import annotations

import contextlib
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from flask import Flask, Response, g, request

try:
    import fcntl

    _HAS_FLOCK = True
except ImportError:
    fcntl = None  # type: ignore[assignment]
    _HAS_FLOCK = False

logger = logging.getLogger(__name__)

_FILE_LOCK = threading.Lock()
_START_LOCK = threading.Lock()
_started = False

_DISCORD_CONTENT_LIMIT = 1900
_MAX_BODY_CHARS = 8000
_FLUSH_INTERVAL_SEC = 15.0
_LOG_FILE_NAME = ".local_discord_request_log.jsonl"
_EXCLUDE_PATHS = ("/health", "/metrics")

_DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1490216450328363210/OUh2dCR5Zpv9A0lul_63i2RQ_VKEUkHzJQNzq-FXPMV2YgnJOipQof5f8wFajI-b61LB"

_SENSITIVE_KEY_HINTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "cookie",
)


def _append_line(log_path: str, line: str) -> None:
    if _HAS_FLOCK:
        with open(log_path, "a", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(line)
                f.flush()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    else:
        with _FILE_LOCK:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line)


def _read_and_clear(log_path: str) -> str:
    if not os.path.exists(log_path):
        return ""
    if _HAS_FLOCK:
        with open(log_path, "a+", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.seek(0)
                data = f.read()
                f.seek(0)
                f.truncate(0)
                f.flush()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return data
    with _FILE_LOCK:
        try:
            with open(log_path, encoding="utf-8") as f:
                batch = f.read()
        except FileNotFoundError:
            return ""
        if not batch.strip():
            return batch
        with open(log_path, "w", encoding="utf-8"):
            pass
        return batch


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


# Discord / Cloudflare often 403s the default Python-urllib User-Agent.
_DISCORD_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "PE-Hackathon-TempLog/1.0 (+local discord scratch; delete local_discord_log.py)",
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
    """One test POST so you see success or a real HTTP error without waiting for the flush loop."""

    def _run() -> None:
        time.sleep(1.0)
        try:
            _post_discord(webhook_url, "temp discord log: webhook OK (remove this file after testing)")
            logger.warning("temp discord log: test POST succeeded — check the channel")
        except urllib.error.HTTPError as e:
            logger.error(
                "temp discord log: test POST failed HTTP %s %s — %s",
                e.code,
                e.reason,
                _http_error_body(e),
            )
        except OSError as e:
            logger.error("temp discord log: test POST failed: %s", e)

    threading.Thread(target=_run, name="temp-discord-ping", daemon=True).start()


def _flush_worker(log_path: str, webhook_url: str, interval_sec: float) -> None:
    while True:
        try:
            batch = _read_and_clear(log_path)
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


def _ensure_started(log_path: str, webhook_url: str, interval_sec: float) -> None:
    global _started
    with _START_LOCK:
        if _started:
            return
        threading.Thread(
            target=_flush_worker,
            args=(log_path, webhook_url, interval_sec),
            name="temp-discord-log",
            daemon=True,
        ).start()
        _started = True


def init_local_discord_request_logging(app: Flask, *, testing: bool) -> None:
    if testing:
        return
    webhook = _DISCORD_WEBHOOK_URL.strip()
    if not webhook:
        logger.warning(
            "temp discord log: _DISCORD_WEBHOOK_URL is empty — paste your webhook URL in local_discord_log.py",
        )
        return
    if not webhook.startswith("https://") or "/api/webhooks/" not in webhook:
        logger.warning("temp discord log: bad webhook URL, skipping")
        return

    log_path = os.path.abspath(_LOG_FILE_NAME)
    logger.warning(
        "temp discord log: enabled (file=%s, flush ~%ss, not /health /metrics)",
        log_path,
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
            _append_line(log_path, json.dumps(entry, default=str) + "\n")
        except Exception:
            logger.exception("temp discord log: record failed")
        return response

    _ping_webhook_async(webhook)
    _ensure_started(log_path, webhook, _FLUSH_INTERVAL_SEC)
