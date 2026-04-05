import logging
import os
import time

from peewee import DatabaseProxy, IntegrityError, Model, SqliteDatabase
from playhouse.pool import PooledPostgresqlDatabase

from app.logging_config import get_log_context

db = DatabaseProxy()
sql_logger = logging.getLogger("app.sql")


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


def _sql_logging_enabled():
    return _env_bool("SQL_LOG_ALL", default=False)


def _sql_slow_ms():
    return _env_float("SQL_LOG_SLOW_MS", default=100.0)


def _statement_preview(sql):
    compact = " ".join(str(sql).split())
    if len(compact) <= 240:
        return compact
    return f"{compact[:237]}..."


class LoggingSqlMixin:
    def execute_sql(self, sql, params=None, commit=None):
        started = time.perf_counter()
        try:
            if commit is None:
                cursor = super().execute_sql(sql, params)
            else:
                try:
                    cursor = super().execute_sql(sql, params, commit)
                except TypeError:
                    cursor = super().execute_sql(sql, params)
        except Exception as error:
            duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
            extra = {
                "component": "db",
                "duration_ms": duration_ms,
                "statement": _statement_preview(sql),
                "params_count": len(params or ()),
                "db_error": type(error).__name__,
            }
            extra.update(get_log_context())
            # Unique / FK violations are often handled by the route (e.g. idempotent create).
            if isinstance(error, IntegrityError):
                sql_logger.info("sql_integrity_constraint", extra=extra)
            else:
                sql_logger.exception("sql_query_failed", extra=extra)
            raise

        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        if duration_ms >= _sql_slow_ms() or _sql_logging_enabled():
            extra = {
                "component": "db",
                "duration_ms": duration_ms,
                "statement": _statement_preview(sql),
                "params_count": len(params or ()),
                "slow_query": duration_ms >= _sql_slow_ms() or None,
            }
            extra.update(get_log_context())
            sql_logger.info("sql_query_completed", extra=extra)
        return cursor


class LoggingSqliteDatabase(LoggingSqlMixin, SqliteDatabase):
    pass


class LoggingPooledPostgresqlDatabase(LoggingSqlMixin, PooledPostgresqlDatabase):
    pass


class BaseModel(Model):
    class Meta:
        database = db


def _postgres_connect_kwargs():
    """Extra kwargs for psycopg2.connect (TLS, timeouts). Empty for local Postgres without SSL."""
    connect_kwargs = {}
    sslmode = os.environ.get("DATABASE_SSLMODE", "").strip()
    if sslmode:
        connect_kwargs["sslmode"] = sslmode
    connect_timeout_raw = os.environ.get("DATABASE_CONNECT_TIMEOUT")
    if connect_timeout_raw:
        try:
            connect_kwargs["connect_timeout"] = int(connect_timeout_raw.strip())
        except ValueError:
            pass
    return connect_kwargs


def init_db(testing=False):
    if getattr(db, "obj", None) is not None and not db.is_closed():
        db.close()

    if testing:
        database = LoggingSqliteDatabase(
            "file:testing?mode=memory&cache=shared",
            uri=True,
            pragmas={"foreign_keys": 1},
            check_same_thread=False,
        )
    else:
        database = LoggingPooledPostgresqlDatabase(
            os.environ.get("DATABASE_NAME", "hackathon_db"),
            host=os.environ.get("DATABASE_HOST", "localhost"),
            port=int(os.environ.get("DATABASE_PORT", 5432)),
            user=os.environ.get("DATABASE_USER", "postgres"),
            password=os.environ.get("DATABASE_PASSWORD", "postgres"),
            max_connections=int(os.environ.get("DATABASE_MAX_CONNECTIONS", "20")),
            stale_timeout=int(os.environ.get("DATABASE_STALE_TIMEOUT_SECONDS", "300")),
            timeout=int(os.environ.get("DATABASE_POOL_WAIT_TIMEOUT_SECONDS", "10")),
            **_postgres_connect_kwargs(),
        )

    db.initialize(database)


def connect_db():
    db.connect(reuse_if_open=True)


def close_db():
    if not db.is_closed():
        db.close()


URL_USER_ORIGINAL_URL_INDEX_NAME = "url_user_id_original_url"
_URL_USER_ORIGINAL_URL_INDEX_SQL = (
    f"CREATE INDEX IF NOT EXISTS {URL_USER_ORIGINAL_URL_INDEX_NAME} "
    "ON url (user_id, original_url)"
)


def ensure_url_user_original_url_index() -> None:
    """Ensure btree for idempotent POST /urls lookup (user_id, original_url).

    Not defined in Url.Meta.indexes so existing databases get the index on startup
    (Peewee create_tables(safe=True) does not add new indexes to already-created tables).
    Safe to call repeatedly: ``IF NOT EXISTS``. Works on PostgreSQL and SQLite.
    """
    db.execute_sql(_URL_USER_ORIGINAL_URL_INDEX_SQL)
