from datetime import datetime

from app.routes.users import _parse_datetime, _validate_user_payload


def test_parse_datetime_supports_expected_formats():
    assert _parse_datetime("2026-04-04 12:30:45") == datetime(2026, 4, 4, 12, 30, 45)
    assert _parse_datetime("2026-04-04T12:30:45") == datetime(2026, 4, 4, 12, 30, 45)


def test_parse_datetime_returns_none_for_invalid_values():
    assert _parse_datetime("") is None
    assert _parse_datetime("not-a-date") is None


def test_validate_user_payload_requires_username_and_email():
    errors = _validate_user_payload({}, is_partial=False)

    assert errors == {
        "username": "username must be a non-empty string",
        "email": "email must be a valid email string",
    }


def test_validate_user_payload_allows_partial_updates():
    assert _validate_user_payload({"email": "valid@example.com"}, is_partial=True) == {}
    assert _validate_user_payload({"email": "bad-email"}, is_partial=True) == {
        "email": "email must be a valid email string"
    }


def test_validate_user_payload_rejects_whitespace_only_username():
    errors = _validate_user_payload({"username": "   ", "email": "ok@example.com"}, is_partial=False)
    assert errors["username"] == "username must be a non-empty string"


def test_validate_user_payload_rejects_non_string_username():
    errors = _validate_user_payload({"username": 42, "email": "ok@example.com"}, is_partial=False)
    assert errors["username"] == "username must be a non-empty string"


def test_validate_user_payload_rejects_missing_at_in_email():
    errors = _validate_user_payload({"username": "u", "email": "not-an-email"}, is_partial=False)
    assert "email" in errors
