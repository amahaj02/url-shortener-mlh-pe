from flask import Blueprint, jsonify, request
from peewee import IntegrityError

from app.json_request import require_json_object

from app.models.event import Event
from app.models.url import Url
from app.models.user import User

events_bp = Blueprint("events", __name__)


def _is_strict_json_int(value):
    """True JSON integers only — bool is a subclass of int in Python."""
    return type(value) is int


@events_bp.route("/events", methods=["GET"])
def list_events():
    query = Event.select().order_by(Event.id)

    url_id = request.args.get("url_id")
    if url_id is not None:
        try:
            query = query.where(Event.url == int(url_id))
        except ValueError:
            return jsonify(errors={"url_id": "url_id must be an integer"}), 400

    user_id = request.args.get("user_id")
    if user_id is not None:
        try:
            query = query.where(Event.user == int(user_id))
        except ValueError:
            return jsonify(errors={"user_id": "user_id must be an integer"}), 400

    event_type = request.args.get("event_type")
    if event_type is not None:
        query = query.where(Event.event_type == event_type.strip())

    events = query
    return jsonify([event.to_dict() for event in events])


@events_bp.route("/events", methods=["POST"])
def create_event():
    payload, err = require_json_object()
    if err:
        return err

    url_id = payload.get("url_id")
    user_id = payload.get("user_id")
    event_type = payload.get("event_type")
    details = payload.get("details", {})

    errors = {}
    if url_id is not None and not _is_strict_json_int(url_id):
        errors["url_id"] = "url_id must be an integer or null"
    if user_id is not None and not _is_strict_json_int(user_id):
        errors["user_id"] = "user_id must be an integer or null"
    if not isinstance(event_type, str) or not event_type.strip():
        errors["event_type"] = "event_type must be a non-empty string"
    if not isinstance(details, dict):
        errors["details"] = "details must be a JSON object"
    if errors:
        return jsonify(errors=errors), 400

    url = None
    user = None
    if url_id is not None:
        try:
            url = Url.get_by_id(url_id)
        except Url.DoesNotExist:
            return jsonify(error="URL not found"), 404
    if user_id is not None:
        try:
            user = User.get_by_id(user_id)
        except User.DoesNotExist:
            return jsonify(error="User not found"), 404

    try:
        event = Event.create(
            url=url,
            user=user,
            event_type=event_type.strip(),
            details=Event.serialize_details(details),
        )
    except IntegrityError:
        return jsonify(errors={"event": "Could not create event"}), 400

    return jsonify(event.to_dict()), 201
