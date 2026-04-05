from types import SimpleNamespace

from peewee import IntegrityError

from app.models.url import Url
from app.routes.urls import _is_user_fk_violation, _is_valid_url


def test_is_valid_url_accepts_http_and_https_only():
    assert _is_valid_url("https://example.com")
    assert _is_valid_url("http://example.com/path")
    assert not _is_valid_url("ftp://example.com")
    assert not _is_valid_url("example.com")


def test_generate_short_code_is_unique_alphanumeric_six_chars(test_db):
    codes = {Url.generate_short_code() for _ in range(40)}
    assert len(codes) == 40
    for code in codes:
        assert len(code) == Url.DEFAULT_SHORT_CODE_LENGTH
        assert code.isalnum()
        assert not code.isdigit()


def test_short_code_from_id_is_deterministic_base62():
    assert Url.short_code_from_id(1) == "1"
    assert Url.short_code_from_id(10) == "A"
    assert Url.short_code_from_id(61) == "z"
    assert Url.short_code_from_id(62) == "10"
    assert Url.short_code_from_id(63) == "11"


def test_short_code_from_id_is_pure_base62_encoding():
    assert Url.short_code_from_id(7254958) == "URLS"


def test_short_code_from_id_rejects_invalid_ids():
    try:
        Url.short_code_from_id(0)
    except ValueError as error:
        assert str(error) == "row_id must be a positive integer"
    else:
        raise AssertionError("Expected ValueError for non-positive row id")


def test_integrity_error_helper_identifies_user_fk_failures():
    assert _is_user_fk_violation(IntegrityError("insert or update on table \"url\" violates foreign key constraint \"url_user_id_fkey\""))


def test_redirect_short_url_returns_404_for_missing_code(client, monkeypatch):
    def fake_get(*args, **kwargs):
        raise Url.DoesNotExist()

    monkeypatch.setattr(Url, "get", fake_get)

    response = client.get("/missing")

    assert response.status_code == 404
    assert response.get_json() == {"error": "Resource not found"}


def test_redirect_short_url_returns_410_for_inactive_code(client, monkeypatch):
    inactive_url = SimpleNamespace(is_active=False)
    monkeypatch.setattr(Url, "get", lambda *args, **kwargs: inactive_url)

    response = client.get("/inactive")

    assert response.status_code == 410
    assert response.get_json() == {"error": "Short URL is inactive"}


def test_redirect_short_url_redirects_and_logs_event(client, monkeypatch):
    url_entry = SimpleNamespace(
        is_active=True,
        user=SimpleNamespace(id=1),
        short_code="abc123",
        original_url="https://example.com",
    )
    events = []

    monkeypatch.setattr(Url, "get", lambda *args, **kwargs: url_entry)
    monkeypatch.setattr(
        "app.routes.urls.Event.create_event",
        lambda **kwargs: events.append(kwargs),
    )

    response = client.get("/abc123")

    assert response.status_code == 302
    assert response.headers["Location"] == "https://example.com"
    assert len(events) == 1
    assert events[0]["event_type"] == "click"
    assert events[0]["url"] is url_entry
