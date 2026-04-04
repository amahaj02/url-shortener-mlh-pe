"""
Strict JSON request bodies: object-only, invalid JSON rejected, force=True so
valid JSON is not ignored when Content-Type is not application/json.

Uses json.loads on the raw body so behavior matches curl and clients that send
valid non-object JSON (e.g. Postman's JSON mode may replace invalid input with
``null``, which is valid JSON but not an object).
"""

from __future__ import annotations

import json

from flask import jsonify, request


def require_json_object():
    """
    Parse the body as a JSON object (dict).

    Returns (payload_dict, None) on success, or (None, (response, status_code)).
    """
    raw = request.get_data(cache=True)
    if not raw or not raw.strip():
        return None, (jsonify(errors={"payload": "JSON object required"}), 400)

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, (jsonify(errors={"payload": "Invalid JSON"}), 400)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, (jsonify(errors={"payload": "Invalid JSON"}), 400)

    if not isinstance(data, dict):
        return None, (
            jsonify(
                errors={
                    "payload": "JSON body must be a JSON object (not null, an array, or a primitive)",
                }
            ),
            400,
        )

    return data, None
