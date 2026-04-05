import logging
import queue

from app import event_pipeline


def test_enqueue_uses_sync_insert_in_testing(monkeypatch):
    captured = []
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setattr(event_pipeline, "_insert_one_sync", lambda *args: captured.append(args))

    event_pipeline.enqueue(1, 2, "click", {"ok": True})

    assert captured == [(1, 2, "click", {"ok": True})]


def test_enqueue_drops_when_queue_full(monkeypatch, caplog):
    monkeypatch.setenv("TESTING", "false")
    monkeypatch.setattr(event_pipeline, "_ensure_queue", lambda: None)
    monkeypatch.setattr(event_pipeline, "_queue", queue.Queue(maxsize=1))
    event_pipeline._queue.put((1, 2, "created", {}))
    monkeypatch.setattr(event_pipeline, "_dropped", 0)

    with caplog.at_level(logging.WARNING):
        event_pipeline.enqueue(3, 4, "click", {"x": 1})

    assert event_pipeline._dropped == 1
    assert "event_queue_drop" in caplog.text


def test_flush_items_inserts_batch_and_logs(monkeypatch, caplog):
    inserted = []
    monkeypatch.setattr(event_pipeline, "_insert_batch_sync", lambda rows: inserted.extend(rows))

    with caplog.at_level(logging.INFO):
        event_pipeline._flush_items(
            [
                (1, 2, "created", {"a": 1}),
                (3, None, "click", {"b": 2}),
            ]
        )

    assert len(inserted) == 2
    assert inserted[0]["url"] == 1
    assert inserted[1]["user"] is None
    assert "event_batch_flushed" in caplog.text


def test_flush_items_logs_failures(monkeypatch, caplog):
    def blow_up(_rows):
        raise RuntimeError("boom")

    monkeypatch.setattr(event_pipeline, "_insert_batch_sync", blow_up)

    with caplog.at_level(logging.ERROR):
        event_pipeline._flush_items([(1, 2, "created", {})])

    assert "event_batch_flush_failed" in caplog.text


def test_shutdown_flushes_pending_items(monkeypatch):
    flushed = []
    worker = type("Worker", (), {"is_alive": lambda self: True, "join": lambda self, timeout=0: None})()
    monkeypatch.setattr(event_pipeline, "_queue", queue.Queue())
    monkeypatch.setattr(event_pipeline, "_worker", worker)
    monkeypatch.setattr(event_pipeline, "_flush_items", lambda items: flushed.extend(items))
    event_pipeline._stop.clear()
    event_pipeline._queue.put((1, 2, "created", {}))

    event_pipeline._shutdown()

    assert flushed == [(1, 2, "created", {})]
    event_pipeline._stop.clear()
    monkeypatch.setattr(event_pipeline, "_queue", None)
    monkeypatch.setattr(event_pipeline, "_worker", None)
