import io

from app import create_app
from app.models.event import Event
from app.models.url import Url
from app.models.user import User


def test_create_user_persists_to_database(client, test_db):
    response = client.post(
        "/users",
        json={"username": "aarav", "email": "aarav@example.com"},
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["username"] == "aarav"
    assert User.select().count() == 1
    assert User.get().email == "aarav@example.com"


def test_create_user_rejects_duplicate_email(client, test_db):
    User.create(username="first", email="shared@example.com")

    response = client.post(
        "/users",
        json={"username": "second", "email": "shared@example.com"},
    )

    assert response.status_code == 409
    assert response.get_json() == {"errors": {"user": "username or email already exists"}}


def test_bulk_import_users_inserts_valid_rows_in_batches(client, test_db):
    csv_bytes = io.BytesIO(
        b"id,username,email,created_at\n"
        b"1,one,one@example.com,2026-04-04 12:00:00\n"
        b"2,two,two@example.com,2026-04-04T12:30:00\n"
        b"3,bad,bad-email,2026-04-04 12:45:00\n"
        b"2,duplicate,two@example.com,2026-04-04 13:00:00\n"
    )

    response = client.post(
        "/users/bulk",
        data={"file": (csv_bytes, "users.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    assert response.get_json() == {"count": 2}
    assert User.select().count() == 2


def test_create_update_and_redirect_url_records_events(client, test_db):
    user = User.create(username="owner", email="owner@example.com")

    create_response = client.post(
        "/urls",
        json={
            "user_id": user.id,
            "original_url": "https://example.com/start",
            "title": " Start Here ",
        },
    )

    assert create_response.status_code == 201
    created_payload = create_response.get_json()
    url_id = created_payload["id"]
    short_code = created_payload["short_code"]
    assert created_payload["title"] == "Start Here"

    update_response = client.put(
        f"/urls/{url_id}",
        json={
            "original_url": "https://example.com/updated",
            "title": " Updated Title ",
            "is_active": True,
        },
    )

    assert update_response.status_code == 200
    updated_payload = update_response.get_json()
    assert updated_payload["original_url"] == "https://example.com/updated"
    assert updated_payload["title"] == "Updated Title"

    redirect_response = client.get(
        f"/{short_code}",
        headers={"X-Forwarded-For": "203.0.113.1"},
        follow_redirects=False,
    )

    assert redirect_response.status_code == 302
    assert redirect_response.headers["Location"] == "https://example.com/updated"

    stored_url = Url.get_by_id(url_id)
    assert stored_url.original_url == "https://example.com/updated"

    events = list(Event.select().order_by(Event.id))
    assert [event.event_type for event in events] == ["created", "updated", "redirected"]
    assert events[-1].to_dict()["details"]["ip_address"] == "203.0.113.1"


def test_inactive_short_url_returns_gone(client, test_db):
    user = User.create(username="inactive", email="inactive@example.com")
    url_entry = Url.create(
        user=user,
        short_code="dead01",
        original_url="https://example.com/inactive",
        is_active=False,
    )

    response = client.get(f"/{url_entry.short_code}")

    assert response.status_code == 410
    assert response.get_json() == {"error": "Short URL is inactive"}


def test_unknown_route_returns_json_404(client, test_db):
    response = client.get("/definitely/missing")

    assert response.status_code == 404
    assert response.get_json() == {"error": "Not found"}


def test_internal_server_error_returns_json_response(test_db):
    app = create_app(testing=True)
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.route("/boom")
    def boom():
        raise RuntimeError("unexpected failure")

    response = app.test_client().get("/boom")

    assert response.status_code == 500
    assert response.get_json() == {"error": "Internal server error"}
