"""Unit tests for strict JSON object parsing (Deceitful Scroll / Fractured Vessel)."""

import pytest

from app.json_request import require_json_object


@pytest.mark.parametrize(
    ("body", "content_type", "expected_json"),
    [
        (b"", "application/json", {"errors": {"payload": "JSON object required"}}),
        (b"   ", "application/json", {"errors": {"payload": "JSON object required"}}),
        (b"{not valid", "application/json", {"errors": {"payload": "Invalid JSON"}}),
        (
            b"null",
            "application/json",
            {"errors": {"payload": "JSON body must be a JSON object (not null, an array, or a primitive)"}},
        ),
        (
            b"[]",
            "application/json",
            {"errors": {"payload": "JSON body must be a JSON object (not null, an array, or a primitive)"}},
        ),
        (
            b'["a"]',
            "application/json",
            {"errors": {"payload": "JSON body must be a JSON object (not null, an array, or a primitive)"}},
        ),
        (
            b'"hello"',
            "application/json",
            {"errors": {"payload": "JSON body must be a JSON object (not null, an array, or a primitive)"}},
        ),
        (
            b"42",
            "application/json",
            {"errors": {"payload": "JSON body must be a JSON object (not null, an array, or a primitive)"}},
        ),
        (
            b"true",
            "application/json",
            {"errors": {"payload": "JSON body must be a JSON object (not null, an array, or a primitive)"}},
        ),
    ],
)
def test_require_json_object_rejects_non_objects_and_bad_syntax(app, body, content_type, expected_json):
    with app.test_request_context("/", method="POST", data=body, content_type=content_type):
        data, err = require_json_object()
        assert data is None
        response, status = err
        assert status == 400
        assert response.get_json() == expected_json


def test_require_json_object_accepts_dict_with_non_json_content_type(app):
    with app.test_request_context(
        "/",
        method="POST",
        data=b'{"x": 1}',
        content_type="text/plain",
    ):
        data, err = require_json_object()
        assert err is None
        assert data == {"x": 1}


def test_require_json_object_accepts_empty_object(app):
    with app.test_request_context(
        "/",
        method="POST",
        data=b"{}",
        content_type="application/json",
    ):
        data, err = require_json_object()
        assert err is None
        assert data == {}
