"""
Async, batched writes to the Event table so request handlers stay fast under burst load.

- Production: bounded queue + background thread flushes with insert_many batches.
- TESTING=true: synchronous insert (no thread) so tests see rows immediately.

If the queue is full, events are dropped and counted (protects latency).
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import queue
import threading
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

_queue: queue.Queue[tuple[int | None, int | None, str, dict[str, Any]]] | None = None
_worker: threading.Thread | None = None
_stop = threading.Event()
_dropped = 0
_dropped_lock = threading.Lock()

QUEUE_MAX = int(os.getenv("EVENT_QUEUE_MAX", "5000"))
BATCH_SIZE = max(1, int(os.getenv("EVENT_BATCH_SIZE", "100")))
FLUSH_INTERVAL_SEC = float(os.getenv("EVENT_FLUSH_INTERVAL_SEC", "0.15"))


def _testing() -> bool:
    return os.getenv("TESTING", "").strip().lower() in {"1", "true", "yes", "on"}


def _ensure_queue() -> None:
    global _queue, _worker
    if _testing():
        return
    if _queue is not None:
        return
    _queue = queue.Queue(maxsize=QUEUE_MAX)
    _worker = threading.Thread(target=_worker_loop, name="event-pipeline", daemon=False)
    _worker.start()
    atexit.register(_shutdown)


def _insert_batch_sync(rows: list[dict[str, Any]]) -> None:
    from app.database import db
    from app.models.event import Event

    db.connect(reuse_if_open=True)
    with db.atomic():
        Event.insert_many(rows).execute()


def _insert_one_sync(url_id: int | None, user_id: int | None, event_type: str, details: dict[str, Any]) -> None:
    from app.database import db
    from app.models.event import Event

    db.connect(reuse_if_open=True)
    with db.atomic():
        Event.insert(
            url=url_id,
            user=user_id,
            event_type=event_type,
            details=json.dumps(details),
            timestamp=datetime.utcnow(),
        ).execute()
    try:
        db.commit()
    except Exception:
        pass


def enqueue(url_id: int | None, user_id: int | None, event_type: str, details: dict[str, Any]) -> None:
    if not isinstance(details, dict):
        details = {}
    if _testing():
        _insert_one_sync(url_id, user_id, event_type, details)
        return

    _ensure_queue()
    assert _queue is not None
    try:
        _queue.put_nowait((url_id, user_id, event_type, details))
    except queue.Full:
        global _dropped
        with _dropped_lock:
            _dropped += 1
            d = _dropped
        if d == 1 or d % 100 == 0:
            logger.warning(
                "event_queue_drop",
                extra={
                    "component": "event_pipeline",
                    "dropped_events": d,
                    "queue_max": QUEUE_MAX,
                },
            )


def _worker_loop() -> None:
    while not _stop.is_set():
        try:
            first = _queue.get(timeout=FLUSH_INTERVAL_SEC) if _queue else None
        except queue.Empty:
            continue
        batch_items = [first]
        if _queue:
            while len(batch_items) < BATCH_SIZE:
                try:
                    batch_items.append(_queue.get_nowait())
                except queue.Empty:
                    break
        _flush_items(batch_items)


def _flush_items(items: list[tuple[int | None, int | None, str, dict[str, Any]]]) -> None:
    if not items:
        return
    now = datetime.utcnow()
    rows = []
    started = time.perf_counter()
    for url_id, user_id, event_type, details in items:
        rows.append(
            {
                "url": url_id,
                "user": user_id,
                "event_type": event_type,
                "details": json.dumps(details),
                "timestamp": now,
            }
        )
    try:
        _insert_batch_sync(rows)
        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        if len(rows) > 1 or duration_ms >= 100.0:
            logger.info(
                "event_batch_flushed",
                extra={
                    "component": "event_pipeline",
                    "batch_size": len(rows),
                    "duration_ms": duration_ms,
                },
            )
    except Exception:
        logger.exception(
            "event_batch_flush_failed",
            extra={
                "component": "event_pipeline",
                "batch_size": len(rows),
            },
        )


def _shutdown() -> None:
    _stop.set()
    if _worker is not None and _worker.is_alive():
        _worker.join(timeout=5.0)
    pending: list[tuple[int | None, int | None, str, dict[str, Any]]] = []
    if _queue is not None:
        while True:
            try:
                pending.append(_queue.get_nowait())
            except queue.Empty:
                break
    if pending:
        logger.info(
            "event_shutdown_flush",
            extra={
                "component": "event_pipeline",
                "pending_events": len(pending),
            },
        )
        _flush_items(pending)
