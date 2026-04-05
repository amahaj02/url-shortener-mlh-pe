import json
import logging

from app.logging_config import JsonFormatter


def test_metrics_endpoint_returns_usage_data(client):
    response = client.get("/metrics")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert "cpu_percent" in payload
    assert "memory" in payload
    assert "process" in payload
    assert "rss_bytes" in payload["memory"]
    assert "pid" in payload["process"]


def test_json_formatter_outputs_structured_json():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="app.http",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request_completed",
        args=(),
        exc_info=None,
    )
    record.component = "http"
    record.method = "GET"
    record.path = "/health"
    record.status_code = 200

    rendered = formatter.format(record)
    payload = json.loads(rendered)

    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.http"
    assert payload["message"] == "request_completed"
    assert payload["component"] == "http"
    assert payload["method"] == "GET"
    assert payload["path"] == "/health"
    assert payload["status_code"] == 200
