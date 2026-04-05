import json
import logging

from app.logging_config import JsonFormatter, RequestContextFilter, clear_log_context, set_log_context


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


def test_prometheus_metrics_endpoint_returns_prometheus_text(client):
    response = client.get("/metrics/prometheus")

    assert response.status_code == 200
    assert "text/plain" in response.content_type
    body = response.get_data(as_text=True)
    assert "http_requests_total" in body or "url_shortener_http_requests_total" in body


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


def test_request_context_filter_injects_request_metadata_and_omits_nulls():
    clear_log_context()
    set_log_context(request_id="req-123", method="POST", path="/users")

    try:
        record = logging.LogRecord(
            name="app.sql",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="sql_query_completed",
            args=(),
            exc_info=None,
        )
        record.component = "db"
        record.duration_ms = 12.5
        record.slow_query = None

        RequestContextFilter().filter(record)
        payload = json.loads(JsonFormatter().format(record))

        assert payload["request_id"] == "req-123"
        assert payload["method"] == "POST"
        assert payload["path"] == "/users"
        assert payload["component"] == "db"
        assert "slow_query" not in payload
    finally:
        clear_log_context()
