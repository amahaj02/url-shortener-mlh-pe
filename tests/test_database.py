from app.database import _postgres_connect_kwargs


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
