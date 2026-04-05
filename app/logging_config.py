import json
import logging
import os
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_path_var: ContextVar[str | None] = ContextVar("path", default=None)
_method_var: ContextVar[str | None] = ContextVar("method", default=None)

STANDARD_LOG_RECORD_FIELDS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


def set_log_context(*, request_id=None, path=None, method=None):
    if request_id is not None:
        _request_id_var.set(request_id)
    if path is not None:
        _path_var.set(path)
    if method is not None:
        _method_var.set(method)


def clear_log_context():
    _request_id_var.set(None)
    _path_var.set(None)
    _method_var.set(None)


def get_log_context():
    return {
        "request_id": _request_id_var.get(),
        "path": _path_var.get(),
        "method": _method_var.get(),
    }


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        context = get_log_context()
        for key, value in context.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key in STANDARD_LOG_RECORD_FIELDS or key.startswith("_"):
                continue
            if value is None:
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    http_level = getattr(logging, os.getenv("HTTP_LOG_LEVEL", "WARNING").upper(), logging.WARNING)
    sql_level = getattr(logging, os.getenv("SQL_LOG_LEVEL", "INFO").upper(), logging.INFO)

    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        for handler in root.handlers:
            handler.setLevel(level)
            handler.setFormatter(JsonFormatter())
            if not any(isinstance(existing, RequestContextFilter) for existing in handler.filters):
                handler.addFilter(RequestContextFilter())
        logging.getLogger("werkzeug").setLevel(logging.WARNING)
        logging.getLogger("app.http").setLevel(http_level)
        logging.getLogger("app.sql").setLevel(sql_level)
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestContextFilter())
    root.addHandler(handler)
    root.setLevel(level)

    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("app.http").setLevel(http_level)
    logging.getLogger("app.sql").setLevel(sql_level)
