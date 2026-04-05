import os
import time

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    ProcessCollector,
    PlatformCollector,
    generate_latest,
)


METRICS_NAMESPACE = os.getenv("PROMETHEUS_NAMESPACE", "url_shortener")

registry = CollectorRegistry(auto_describe=True)
ProcessCollector(registry=registry)
PlatformCollector(registry=registry)

http_requests_total = Counter(
    f"{METRICS_NAMESPACE}_http_requests_total",
    "Total HTTP requests handled by the application.",
    labelnames=("method", "route", "status"),
    registry=registry,
)

http_request_duration_seconds = Histogram(
    f"{METRICS_NAMESPACE}_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    labelnames=("method", "route", "status"),
    buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
    registry=registry,
)

http_requests_in_flight = Gauge(
    f"{METRICS_NAMESPACE}_http_requests_in_flight",
    "HTTP requests currently being processed.",
    labelnames=("method", "route"),
    registry=registry,
)

http_request_exceptions_total = Counter(
    f"{METRICS_NAMESPACE}_http_request_exceptions_total",
    "Unhandled HTTP request exceptions by route and exception type.",
    labelnames=("method", "route", "exception_type"),
    registry=registry,
)


def _route_label():
    from flask import request

    if request.url_rule is not None:
        return request.url_rule.rule
    if request.endpoint:
        return request.endpoint
    return request.path


def start_request_timer():
    from flask import g, request

    route = _route_label()
    g._metrics_started = time.perf_counter()
    g._metrics_route = route
    g._metrics_method = request.method
    http_requests_in_flight.labels(method=request.method, route=route).inc()


def finish_request(response):
    from flask import g

    route = getattr(g, "_metrics_route", None)
    method = getattr(g, "_metrics_method", None)
    started = getattr(g, "_metrics_started", None)
    if route is None or method is None or started is None:
        return response

    status = str(response.status_code)
    duration = time.perf_counter() - started
    http_requests_total.labels(method=method, route=route, status=status).inc()
    http_request_duration_seconds.labels(method=method, route=route, status=status).observe(duration)
    http_requests_in_flight.labels(method=method, route=route).dec()
    return response


def finish_exception(exception):
    from flask import g

    route = getattr(g, "_metrics_route", None)
    method = getattr(g, "_metrics_method", None)
    started = getattr(g, "_metrics_started", None)
    if route is None or method is None:
        return

    http_request_exceptions_total.labels(
        method=method,
        route=route,
        exception_type=type(exception).__name__,
    ).inc()


def render_metrics():
    return generate_latest(registry), CONTENT_TYPE_LATEST
