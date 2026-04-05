from flask import Flask, Response

from app import prometheus_metrics as metrics


def test_start_finish_request_records_metrics():
    app = Flask(__name__)

    with app.test_request_context("/health", method="GET"):
        metrics.start_request_timer()
        response = metrics.finish_request(Response(status=204))

    assert response.status_code == 204
    rendered, content_type = metrics.render_metrics()
    body = rendered.decode("utf-8")
    assert content_type
    assert 'url_shortener_http_requests_total' in body
    assert 'method="GET",route="/health",status="204"' in body


def test_finish_exception_records_counter():
    app = Flask(__name__)

    with app.test_request_context("/boom", method="POST"):
        metrics.start_request_timer()
        metrics.finish_exception(RuntimeError("boom"))

    rendered, _content_type = metrics.render_metrics()
    body = rendered.decode("utf-8")
    assert 'url_shortener_http_request_exceptions_total' in body
    assert 'exception_type="RuntimeError",method="POST"' in body or 'method="POST",route="/boom",exception_type="RuntimeError"' in body


def test_finish_request_without_start_is_noop():
    app = Flask(__name__)

    with app.test_request_context("/noop", method="GET"):
        response = metrics.finish_request(Response(status=200))

    assert response.status_code == 200
