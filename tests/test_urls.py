from types import SimpleNamespace

from app.models.url import Url
from app.routes.urls import _is_valid_url


def test_is_valid_url_accepts_http_and_https_only():
    assert _is_valid_url("https://example.com")
    assert _is_valid_url("http://example.com/path")
    assert not _is_valid_url("ftp://example.com")
    assert not _is_valid_url("example.com")


def test_redirect_short_url_returns_404_for_missing_code(client, monkeypatch):
    def fake_get(*args, **kwargs):
        raise Url.DoesNotExist()

    monkeypatch.setattr(Url, "get", fake_get)

    response = client.get("/missing")

    assert response.status_code == 404
    assert response.get_json() == {"error": "Short URL not found"}


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
    assert events[0]["event_type"] == "redirected"
    assert events[0]["url"] is url_entry
