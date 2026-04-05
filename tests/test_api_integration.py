import io

from peewee import OperationalError

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


def test_create_user_is_idempotent_for_exact_same_input(client, test_db):
    first = client.post(
        "/users",
        json={"username": "same-user", "email": "same-user@example.com"},
    )
    second = client.post(
        "/users",
        json={"username": "same-user", "email": "same-user@example.com"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.get_json()["username"] == "same-user"
    assert User.select().where(User.username == "same-user").count() == 1


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
    assert created_payload["short_code"] == Url.short_code_from_id(url_id)

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
    assert [event.event_type for event in events] == ["created", "updated", "click"]
    assert events[-1].to_dict()["details"]["ip_address"] == "203.0.113.1"


def test_list_urls_filters_by_is_active(client, test_db):
    user = User.create(username="active-filter", email="active-filter@example.com")
    active_url = Url.create(user=user, short_code="af1", original_url="https://example.com/a", is_active=True)
    inactive_url = Url.create(user=user, short_code="af2", original_url="https://example.com/b", is_active=False)

    response = client.get("/urls?is_active=true")

    assert response.status_code == 200
    payload = response.get_json()
    short_codes = {item["short_code"] for item in payload}
    assert active_url.short_code in short_codes
    assert inactive_url.short_code not in short_codes


def test_create_url_returns_404_when_user_does_not_exist(client, test_db):
    response = client.post(
        "/urls",
        json={
            "user_id": 999999,
            "original_url": "https://example.com/missing-user",
            "title": "Missing User",
        },
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "User not found"}

def test_create_url_short_code_is_generated_from_row_id(client, test_db):
    user = User.create(username="deterministic-owner", email="deterministic-owner@example.com")

    response = client.post(
        "/urls",
        json={
            "user_id": user.id,
            "original_url": "https://example.com/deterministic",
            "title": "Deterministic Code",
        },
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["short_code"] == Url.short_code_from_id(payload["id"])


def test_inactive_short_url_returns_gone(client, test_db):
    user = User.create(username="inactive", email="inactive@example.com")
    url_entry = Url.create(
        user=user,
        short_code="dead01",
        original_url="https://example.com/inactive",
        is_active=False,
    )

    events_before = Event.select().count()

    response = client.get(f"/{url_entry.short_code}")

    assert response.status_code == 410
    assert response.get_json() == {"error": "Short URL is inactive"}
    assert Event.select().count() == events_before


def test_json_body_rejects_malformed_json(client, test_db):
    response = client.post(
        "/users",
        data="{not-json",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json() == {"errors": {"payload": "Invalid JSON"}}


def test_json_body_accepts_object_without_json_content_type(client, test_db):
    response = client.post(
        "/users",
        data='{"username": "plain", "email": "plain@example.com"}',
        content_type="text/plain",
    )

    assert response.status_code == 201
    assert response.get_json()["username"] == "plain"


def test_json_empty_body_requires_object(client, test_db):
    response = client.post("/urls", data="", content_type="application/json")

    assert response.status_code == 400
    assert response.get_json() == {"errors": {"payload": "JSON object required"}}


def test_json_array_rejected_for_urls_create(client, test_db):
    user = User.create(username="arr", email="arr@example.com")

    response = client.post(
        "/urls",
        data=f'[{{"user_id": {user.id}, "original_url": "https://x.com"}}]',
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "errors": {"payload": "JSON body must be a JSON object (not null, an array, or a primitive)"}
    }


def test_json_invalid_syntax_on_url_update(client, test_db):
    user = User.create(username="badput", email="badput@example.com")
    url_entry = Url.create(
        user=user,
        short_code="put01",
        original_url="https://example.com/put",
        is_active=True,
    )

    response = client.put(
        f"/urls/{url_entry.id}",
        data="{",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json() == {"errors": {"payload": "Invalid JSON"}}


def test_unknown_short_code_returns_404_without_recording_event(client, test_db):
    events_before = Event.select().count()

    response = client.get("/noSuchCodeZZ9")

    assert response.status_code == 404
    assert response.get_json() == {"error": "Short URL not found"}
    assert Event.select().count() == events_before


def test_two_creations_same_destination_get_distinct_short_codes(client, test_db):
    user = User.create(username="twin", email="twin@example.com")

    first = client.post(
        "/urls",
        json={
            "user_id": user.id,
            "original_url": "https://example.com/same-destination",
        },
    )
    second = client.post(
        "/urls",
        json={
            "user_id": user.id,
            "original_url": "https://example.com/same-destination",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 201
    a, b = first.get_json(), second.get_json()
    assert a["id"] != b["id"]
    assert a["short_code"] != b["short_code"]
    assert a["short_code"] == Url.short_code_from_id(a["id"])
    assert b["short_code"] == Url.short_code_from_id(b["id"])


def test_create_url_rejects_non_numeric_user_id_string(client, test_db):
    user = User.create(username="strid", email="strid@example.com")

    response = client.post(
        "/urls",
        json={
            "user_id": "not-a-valid-id",
            "original_url": "https://example.com/x",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["errors"]["user_id"] == "user_id must be an integer"


def test_create_url_accepts_numeric_string_user_id(client, test_db):
    user = User.create(username="strid2", email="strid2@example.com")

    response = client.post(
        "/urls",
        json={
            "user_id": str(user.id),
            "original_url": "https://example.com/x",
        },
    )

    assert response.status_code == 201
    assert response.get_json()["user_id"] == user.id


def test_create_url_rejects_non_string_title(client, test_db):
    user = User.create(username="titletype", email="titletype@example.com")

    response = client.post(
        "/urls",
        json={
            "user_id": user.id,
            "original_url": "https://example.com/y",
            "title": 12345,
        },
    )

    assert response.status_code == 400
    assert response.get_json()["errors"]["title"] == "title must be a string"


def test_deactivated_url_returns_410_without_redirect_event(client, test_db):
    user = User.create(username="sleep", email="sleep@example.com")
    created = client.post(
        "/urls",
        json={"user_id": user.id, "original_url": "https://example.com/active"},
    )
    assert created.status_code == 201
    url_id = created.get_json()["id"]
    short_code = created.get_json()["short_code"]

    client.put(f"/urls/{url_id}", json={"is_active": False})

    events_before_get = Event.select().count()
    response = client.get(f"/{short_code}")

    assert response.status_code == 410
    assert response.get_json() == {"error": "Short URL is inactive"}
    assert Event.select().count() == events_before_get
    assert "click" not in [e.event_type for e in Event.select()]


def test_create_user_rejects_json_string_body(client, test_db):
    response = client.post(
        "/users",
        data='"only-a-string"',
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "errors": {"payload": "JSON body must be a JSON object (not null, an array, or a primitive)"}
    }


def test_update_user_rejects_extra_unknown_fields(client, test_db):
    user = User.create(username="strict", email="strict@example.com")

    response = client.put(
        f"/users/{user.id}",
        json={"username": "newname", "email": "strict@example.com", "is_admin": True},
    )

    assert response.status_code == 400
    assert "Only username and email" in response.get_json()["errors"]["payload"]


def test_update_url_rejects_extra_unknown_fields(client, test_db):
    user = User.create(username="urlstrict", email="urlstrict@example.com")
    url_entry = Url.create(
        user=user,
        short_code="exFld1",
        original_url="https://example.com/extra-field",
        is_active=True,
    )

    response = client.put(
        f"/urls/{url_entry.id}",
        json={"title": "ok", "short_code": "hijack"},
    )

    assert response.status_code == 400
    assert "Only title, is_active and original_url" in response.get_json()["errors"]["payload"]


def test_create_url_rejects_non_http_scheme(client, test_db):
    user = User.create(username="scheme", email="scheme@example.com")

    response = client.post(
        "/urls",
        json={
            "user_id": user.id,
            "original_url": "ftp://files.example.com/x",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["errors"]["original_url"] == "original_url must be a valid http/https URL"


def test_list_urls_rejects_non_integer_user_id_query(client, test_db):
    response = client.get("/urls?user_id=not-an-int")

    assert response.status_code == 400
    assert response.get_json()["errors"]["user_id"] == "user_id must be an integer"


def test_unknown_route_returns_json_404(client, test_db):
    response = client.get("/definitely/missing")

    assert response.status_code == 404
    assert response.get_json() == {"error": "Not found"}


def test_delete_user_returns_204(client, test_db):
    user = User.create(username="delete-me", email="delete-me@example.com")

    response = client.delete(f"/users/{user.id}")

    assert response.status_code == 204
    assert User.select().where(User.id == user.id).count() == 0


def test_delete_url_returns_204(client, test_db):
    user = User.create(username="delete-url", email="delete-url@example.com")
    url_entry = Url.create(user=user, short_code="delurl", original_url="https://example.com/delete", is_active=True)

    response = client.delete(f"/urls/{url_entry.id}")

    assert response.status_code == 204
    assert Url.select().where(Url.id == url_entry.id).count() == 0


def test_events_endpoint_filters_by_url_and_event_type(client, test_db):
    user = User.create(username="evt-filter", email="evt-filter@example.com")
    url_a = Url.create(user=user, short_code="evta", original_url="https://example.com/a", is_active=True)
    url_b = Url.create(user=user, short_code="evtb", original_url="https://example.com/b", is_active=True)
    Event.create(url=url_a, user=user, event_type="click", details=Event.serialize_details({"n": 1}))
    Event.create(url=url_b, user=user, event_type="created", details=Event.serialize_details({"n": 2}))

    by_url = client.get(f"/events?url_id={url_a.id}")
    by_type = client.get("/events?event_type=click")

    assert by_url.status_code == 200
    assert all(item["url_id"] == url_a.id for item in by_url.get_json())
    assert by_type.status_code == 200
    assert all(item["event_type"] == "click" for item in by_type.get_json())


def test_create_event_returns_201(client, test_db):
    user = User.create(username="evt-user", email="evt-user@example.com")
    url_entry = Url.create(user=user, short_code="evt01", original_url="https://example.com/event", is_active=True)

    response = client.post(
        "/events",
        json={
            "url_id": url_entry.id,
            "user_id": user.id,
            "event_type": "click",
            "details": {"referrer": "https://google.com"},
        },
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["event_type"] == "click"
    assert payload["url_id"] == url_entry.id
    assert payload["user_id"] == user.id


def test_clear_db_endpoint_deletes_all_rows(client, test_db):
    user = User.create(username="clear-me", email="clear-me@example.com")
    url_entry = Url.create(
        user=user,
        short_code="clr001",
        original_url="https://example.com/clear",
        is_active=True,
    )
    Event.create_event(
        url=url_entry,
        user=user,
        event_type="created",
        details={"short_code": url_entry.short_code},
    )

    response = client.post("/admin/clear-db")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["message"] == "Database cleared"
    assert payload["total_deleted"] == 3
    assert User.select().count() == 0
    assert Url.select().count() == 0
    assert Event.select().count() == 0


def test_clear_db_get_returns_admin_help(client, test_db):
    response = client.get("/admin/clear-db")

    assert response.status_code == 200
    assert response.get_json() == {
        "endpoint": "/admin/clear-db",
        "method": "POST",
        "description": "Deletes all rows from known tables in reverse dependency order.",
    }


def test_internal_server_error_returns_json_response(test_db):
    app = create_app(testing=True)
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.route("/boom")
    def boom():
        raise RuntimeError("unexpected failure")

    response = app.test_client().get("/boom")

    assert response.status_code == 500
    assert response.get_json() == {"error": "Internal server error"}


def test_database_operational_error_returns_service_unavailable(test_db):
    app = create_app(testing=True)
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.route("/db-down")
    def db_down():
        raise OperationalError("database is unavailable")

    response = app.test_client().get("/db-down")

    assert response.status_code == 503
    assert response.get_json() == {"error": "Service unavailable"}
