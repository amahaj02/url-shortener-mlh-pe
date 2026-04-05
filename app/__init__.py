import logging
import os
import time
import uuid

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request
from peewee import InterfaceError, OperationalError
import psutil

from app.cache import init_cache
from app.database import close_db, connect_db, db, init_db
from app.logging_config import clear_log_context, configure_logging, set_log_context
from app.routes import register_routes

logger = logging.getLogger(__name__)


def _client_ip_for_log():
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "-"


def _env_bool(name, default=False):
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name, default):
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


def create_app(testing=None):
    load_dotenv()
    configure_logging()

    app = Flask(__name__)
    effective_testing = _env_bool("TESTING", default=False) if testing is None else testing
    app.config["TESTING"] = effective_testing
    app.config["DEBUG"] = _env_bool("FLASK_DEBUG", default=False)
    app.config["AUTO_CREATE_TABLES"] = _env_bool("AUTO_CREATE_TABLES", default=True)
    app.config["HTTP_LOG_SUCCESS"] = _env_bool("HTTP_LOG_SUCCESS", default=False)
    app.config["HTTP_LOG_SLOW_MS"] = _env_float("HTTP_LOG_SLOW_MS", default=1000.0)

    init_db(testing=effective_testing)

    from app import models  # noqa: F401 - registers models with Peewee
    from app.models import ALL_MODELS

    connect_db()
    if app.config["AUTO_CREATE_TABLES"]:
        db.create_tables(ALL_MODELS, safe=True)
    close_db()

    init_cache(app)

    if not effective_testing:
        db_optional_endpoints = {"health", "metrics"}

        @app.before_request
        def _open_db_and_mark_start():
            request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
            g.request_id = request_id
            set_log_context(request_id=request_id, path=request.path, method=request.method)
            if request.endpoint in db_optional_endpoints:
                return
            request._t0 = time.perf_counter()
            connect_db()

        @app.after_request
        def _log_request_response(response):
            if hasattr(g, "request_id"):
                response.headers["X-Request-ID"] = g.request_id
            if request.endpoint in db_optional_endpoints or request.endpoint is None:
                return response
            if getattr(request, "_t0", None) is not None:
                elapsed_ms = (time.perf_counter() - request._t0) * 1000.0
                should_log_success = app.config["HTTP_LOG_SUCCESS"]
                is_error = response.status_code >= 400
                is_slow = elapsed_ms >= app.config["HTTP_LOG_SLOW_MS"]

                if is_error or is_slow or should_log_success:
                    logging.getLogger("app.http").log(
                        logging.WARNING if is_error else logging.INFO,
                        "request_completed",
                        extra={
                            "component": "http",
                            "client_ip": _client_ip_for_log(),
                            "status_code": response.status_code,
                            "duration_ms": round(elapsed_ms, 2),
                            "slow_request": is_slow or None,
                        },
                    )
            return response

        @app.teardown_request
        def _close_db_connection(_exception=None):
            try:
                if request.endpoint in db_optional_endpoints:
                    return
                close_db()
            finally:
                clear_log_context()

    register_routes(app)

    @app.route("/health")
    def health():
        return jsonify(status="ok")

    @app.route("/metrics")
    def metrics():
        process = psutil.Process()
        virtual_memory = psutil.virtual_memory()

        return jsonify(
            cpu_percent=psutil.cpu_percent(interval=None),
            memory={
                "rss_bytes": process.memory_info().rss,
                "vms_bytes": process.memory_info().vms,
                "system_total_bytes": virtual_memory.total,
                "system_available_bytes": virtual_memory.available,
                "system_percent": virtual_memory.percent,
            },
            process={
                "pid": process.pid,
                "num_threads": process.num_threads(),
                "open_files": len(process.open_files()),
            },
            status="ok",
        )

    @app.after_request
    def _attach_request_id(response):
        if hasattr(g, "request_id"):
            response.headers["X-Request-ID"] = g.request_id
        return response

    @app.errorhandler(404)
    def handle_404(_error):
        return jsonify(error="Not found"), 404

    @app.errorhandler(405)
    def handle_405(_error):
        return jsonify(error="Method not allowed"), 405

    @app.errorhandler(OperationalError)
    @app.errorhandler(InterfaceError)
    def handle_database_unavailable(error):
        logger.exception("Database unavailable: %s", error)
        return jsonify(error="Service unavailable"), 503

    @app.errorhandler(500)
    def handle_500(error):
        logger.exception("Internal server error: %s", error)
        return jsonify(error="Internal server error"), 500

    return app
