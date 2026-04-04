import logging
import os
import time

from dotenv import load_dotenv
from flask import Flask, jsonify, request

from app.database import close_db, connect_db, db, init_db
from app.logging_config import configure_logging
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


def create_app(testing=None):
    load_dotenv()
    configure_logging()

    app = Flask(__name__)
    effective_testing = _env_bool("TESTING", default=False) if testing is None else testing
    app.config["TESTING"] = effective_testing
    app.config["DEBUG"] = _env_bool("FLASK_DEBUG", default=False)
    app.config["AUTO_CREATE_TABLES"] = _env_bool("AUTO_CREATE_TABLES", default=True)

    init_db(testing=effective_testing)

    from app import models  # noqa: F401 - registers models with Peewee
    from app.models import ALL_MODELS

    connect_db()
    if app.config["AUTO_CREATE_TABLES"]:
        db.create_tables(ALL_MODELS, safe=True)
    close_db()

    if not effective_testing:
        db_optional_endpoints = {"health"}

        @app.before_request
        def _open_db_and_mark_start():
            if request.endpoint in db_optional_endpoints:
                return
            request._t0 = time.perf_counter()
            if request.endpoint and request.endpoint != "health":
                logging.getLogger("app.http").debug("%s %s", request.method, request.path)
            connect_db()

        @app.after_request
        def _log_request_response(response):
            if request.endpoint in db_optional_endpoints or request.endpoint is None:
                return response
            if getattr(request, "_t0", None) is not None:
                elapsed_ms = (time.perf_counter() - request._t0) * 1000.0
                logging.getLogger("app.http").info(
                    "%s %s %s %s %.2fms",
                    _client_ip_for_log(),
                    request.method,
                    request.path,
                    response.status_code,
                    elapsed_ms,
                )
            return response

        @app.teardown_request
        def _close_db_connection(_exception=None):
            if request.endpoint in db_optional_endpoints:
                return
            close_db()

    register_routes(app)

    @app.route("/health")
    def health():
        return jsonify(status="ok")

    @app.errorhandler(404)
    def handle_404(_error):
        return jsonify(error="Not found"), 404

    @app.errorhandler(405)
    def handle_405(_error):
        return jsonify(error="Method not allowed"), 405

    @app.errorhandler(500)
    def handle_500(error):
        logger.exception("Internal server error: %s", error)
        return jsonify(error="Internal server error"), 500

    return app
