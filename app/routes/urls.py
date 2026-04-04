from datetime import datetime
from urllib.parse import urlparse

from flask import Blueprint, jsonify, redirect, request
from peewee import IntegrityError

from app.models.event import Event
from app.models.url import Url

urls_bp = Blueprint("urls", __name__)


def _is_valid_url(value):
    if not isinstance(value, str) or not value.strip():
        return False

    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _resolve_user_id(url_entry):
    if hasattr(url_entry, "user_id"):
        return url_entry.user_id

    user = getattr(url_entry, "user", None)
    return getattr(user, "id", None)


def _is_user_fk_violation(error):
    message = str(error).lower()
    return "foreign key" in message or "url_user_id_fkey" in message


@urls_bp.route("/urls", methods=["POST"])
def create_url():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(errors={"payload": "JSON object required"}), 400

    user_id = payload.get("user_id")
    original_url = payload.get("original_url")
    title = payload.get("title")

    errors = {}
    if not isinstance(user_id, int):
        errors["user_id"] = "user_id must be an integer"
    if not _is_valid_url(original_url):
        errors["original_url"] = "original_url must be a valid http/https URL"
    if title is not None and not isinstance(title, str):
        errors["title"] = "title must be a string"
    if errors:
        return jsonify(errors=errors), 400

    try:
        url_entry = Url.create(
            user=user_id,
            original_url=original_url.strip(),
            title=title.strip() if isinstance(title, str) else None,
            is_active=True,
        )
    except IntegrityError as error:
        if _is_user_fk_violation(error):
            return jsonify(error="User not found"), 404
        return jsonify(errors={"url": "Could not create URL"}), 400

    url_entry.short_code = Url.short_code_from_id(url_entry.id)
    url_entry.save(only=[Url.short_code])

    Event.create_event(
        url=url_entry,
        user=user_id,
        event_type="created",
        details={
            "short_code": url_entry.short_code,
            "original_url": url_entry.original_url,
        },
    )

    return jsonify(url_entry.to_dict()), 201


@urls_bp.route("/urls", methods=["GET"])
def list_urls():
    query = Url.select().order_by(Url.id)

    user_id = request.args.get("user_id")
    if user_id is not None:
        try:
            user_id_num = int(user_id)
        except ValueError:
            return jsonify(errors={"user_id": "user_id must be an integer"}), 400
        query = query.where(Url.user == user_id_num)

    return jsonify([url_entry.to_dict() for url_entry in query])


@urls_bp.route("/urls/<int:url_id>", methods=["GET"])
def get_url(url_id):
    try:
        url_entry = Url.get_by_id(url_id)
    except Url.DoesNotExist:
        return jsonify(error="URL not found"), 404

    return jsonify(url_entry.to_dict())


@urls_bp.route("/urls/<int:url_id>", methods=["PUT"])
def update_url(url_id):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not payload:
        return jsonify(errors={"payload": "JSON object with updatable fields is required"}), 400

    allowed = {"title", "is_active", "original_url"}
    if any(field not in allowed for field in payload.keys()):
        return jsonify(errors={"payload": "Only title, is_active and original_url can be updated"}), 400

    errors = {}
    if "title" in payload and payload["title"] is not None and not isinstance(payload["title"], str):
        errors["title"] = "title must be a string"
    if "is_active" in payload and not isinstance(payload["is_active"], bool):
        errors["is_active"] = "is_active must be a boolean"
    if "original_url" in payload and not _is_valid_url(payload["original_url"]):
        errors["original_url"] = "original_url must be a valid http/https URL"
    if errors:
        return jsonify(errors=errors), 400

    try:
        url_entry = Url.get_by_id(url_id)
    except Url.DoesNotExist:
        return jsonify(error="URL not found"), 404

    if "title" in payload:
        raw_title = payload["title"]
        url_entry.title = raw_title.strip() if isinstance(raw_title, str) else None
    if "is_active" in payload:
        url_entry.is_active = payload["is_active"]
    if "original_url" in payload:
        url_entry.original_url = payload["original_url"].strip()

    url_entry.updated_at = datetime.utcnow()
    url_entry.save()

    Event.create_event(
        url=url_entry,
        user=_resolve_user_id(url_entry),
        event_type="updated",
        details={
            "short_code": url_entry.short_code,
            "original_url": url_entry.original_url,
            "is_active": url_entry.is_active,
            "title": url_entry.title,
        },
    )

    return jsonify(url_entry.to_dict())


@urls_bp.route("/<string:short_code>", methods=["GET"])
def redirect_short_url(short_code):
    try:
        url_entry = Url.get(Url.short_code == short_code)
    except Url.DoesNotExist:
        return jsonify(error="Short URL not found"), 404

    if not url_entry.is_active:
        return jsonify(error="Short URL is inactive"), 410

    Event.create_event(
        url=url_entry,
        user=_resolve_user_id(url_entry),
        event_type="redirected",
        details={
            "short_code": url_entry.short_code,
            "original_url": url_entry.original_url,
            "ip_address": request.headers.get("X-Forwarded-For", request.remote_addr),
            "user_agent": request.user_agent.string,
        },
    )

    return redirect(url_entry.original_url, code=302)
