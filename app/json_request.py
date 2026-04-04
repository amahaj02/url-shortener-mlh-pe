"""
Strict JSON request bodies: object-only, invalid JSON rejected, force=True so
valid JSON is not ignored when Content-Type is not application/json.
"""

from __future__ import annotations

from flask import jsonify, request
from werkzeug.exceptions import BadRequest


def require_json_object():
    """
    Parse the body as a JSON object (dict).

    Returns (payload_dict, None) on success, or (None, (response, status_code)).
    """
    raw = request.get_data(cache=True)
    if not raw or not raw.strip():
        return None, (jsonify(errors={"payload": "JSON object required"}), 400)

    try:
        data = request.get_json(force=True, silent=False)
    except BadRequest:
        return None, (jsonify(errors={"payload": "Invalid JSON"}), 400)

    if not isinstance(data, dict):
        return None, (jsonify(errors={"payload": "JSON object required"}), 400)

    return data, None
