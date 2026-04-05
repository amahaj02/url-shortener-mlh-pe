import logging

from peewee import IntegrityError

from app.database import LoggingSqlMixin, _postgres_connect_kwargs


class _BaseDb:
    def execute_sql(self, sql, params=None):
        return {"sql": sql, "params": params}


class _CommitDb:
    def execute_sql(self, sql, params=None, commit=None):
        return {"sql": sql, "params": params, "commit": commit}


class _TypeErrorCommitDb:
    def execute_sql(self, sql, params=None):
        return {"sql": sql, "params": params}


class _ErrorDb:
    def __init__(self, error):
        self.error = error

    def execute_sql(self, sql, params=None):
        raise self.error


class LoggingDb(LoggingSqlMixin, _BaseDb):
    pass


class CommitLoggingDb(LoggingSqlMixin, _CommitDb):
    pass


class FallbackCommitLoggingDb(LoggingSqlMixin, _TypeErrorCommitDb):
    pass


class ErrorLoggingDb(LoggingSqlMixin, _ErrorDb):
    pass


def test_postgres_connect_kwargs_empty(monkeypatch):
    monkeypatch.delenv("DATABASE_SSLMODE", raising=False)
    monkeypatch.delenv("DATABASE_CONNECT_TIMEOUT", raising=False)
    assert _postgres_connect_kwargs() == {}


def test_postgres_connect_kwargs_ssl_and_timeout(monkeypatch):
    monkeypatch.setenv("DATABASE_SSLMODE", "require")
    monkeypatch.setenv("DATABASE_CONNECT_TIMEOUT", "12")
    assert _postgres_connect_kwargs() == {"sslmode": "require", "connect_timeout": 12}


def test_postgres_connect_kwargs_invalid_timeout_ignored(monkeypatch):
    monkeypatch.delenv("DATABASE_SSLMODE", raising=False)
    monkeypatch.setenv("DATABASE_CONNECT_TIMEOUT", "not-a-number")
    assert _postgres_connect_kwargs() == {}


def test_logging_sql_mixin_executes_without_commit(monkeypatch):
    monkeypatch.setenv("SQL_LOG_ALL", "false")
    result = LoggingDb().execute_sql("SELECT 1", params=[1])
    assert result == {"sql": "SELECT 1", "params": [1]}


def test_logging_sql_mixin_uses_commit_when_supported(monkeypatch):
    monkeypatch.setenv("SQL_LOG_ALL", "false")
    result = CommitLoggingDb().execute_sql("SELECT 1", params=[1], commit=True)
    assert result == {"sql": "SELECT 1", "params": [1], "commit": True}


def test_logging_sql_mixin_falls_back_when_commit_signature_missing(monkeypatch):
    monkeypatch.setenv("SQL_LOG_ALL", "false")
    result = FallbackCommitLoggingDb().execute_sql("SELECT 1", params=[1], commit=True)
    assert result == {"sql": "SELECT 1", "params": [1]}


def test_logging_sql_mixin_logs_integrity_error_at_info(monkeypatch, caplog):
    monkeypatch.setenv("SQL_LOG_ALL", "false")
    db = ErrorLoggingDb(IntegrityError("duplicate short_code"))

    with caplog.at_level(logging.INFO):
        try:
            db.execute_sql("INSERT INTO url VALUES (?)", params=["abc"])
        except IntegrityError:
            pass

    assert "sql_integrity_constraint" in caplog.text


def test_logging_sql_mixin_logs_non_integrity_error(monkeypatch, caplog):
    monkeypatch.setenv("SQL_LOG_ALL", "false")
    db = ErrorLoggingDb(RuntimeError("boom"))

    with caplog.at_level(logging.ERROR):
        try:
            db.execute_sql("SELECT * FROM url", params=[])
        except RuntimeError:
            pass

    assert "sql_query_failed" in caplog.text
