import logging
from datetime import datetime
from types import SimpleNamespace
from urllib.parse import urlparse

from flask import Blueprint, jsonify, redirect, request
from peewee import IntegrityError

from app.cache import delete_short_link, get_short_link, set_short_link
from app.database import db
from app.json_request import require_json_object
from app.models.event import Event
from app.models.url import Url

urls_bp = Blueprint("urls", __name__)
logger = logging.getLogger(__name__)


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


def _parse_user_id(value):
    """Accept JSON int, whole float (common from JS/k6), or numeric string."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


@urls_bp.route("/urls", methods=["POST"])
def create_url():
    payload, err = require_json_object()
    if err:
        return err

    user_id = _parse_user_id(payload.get("user_id"))
    original_url = payload.get("original_url")
    title = payload.get("title")

    errors = {}
    if user_id is None:
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
    logger.info(
        "url_created",
        extra={
            "component": "urls",
            "url_id": url_entry.id,
            "user_id": user_id,
            "short_code": url_entry.short_code,
        },
    )

    set_short_link(url_entry)

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

    is_active = request.args.get("is_active")
    if is_active is not None:
        normalized = is_active.strip().lower()
        if normalized not in {"true", "false"}:
            return jsonify(errors={"is_active": "is_active must be true or false"}), 400
        query = query.where(Url.is_active == (normalized == "true"))

    return jsonify([url_entry.to_dict() for url_entry in query.iterator()])


@urls_bp.route("/urls/<int:url_id>", methods=["GET"])
def get_url(url_id):
    try:
        url_entry = Url.get_by_id(url_id)
    except Url.DoesNotExist:
        return jsonify(error="URL not found"), 404

    return jsonify(url_entry.to_dict())


@urls_bp.route("/urls/<int:url_id>", methods=["PUT"])
def update_url(url_id):
    payload, err = require_json_object()
    if err:
        return err
    if not payload:
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

    with db.atomic():
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
    logger.info(
        "url_updated",
        extra={
            "component": "urls",
            "url_id": url_id,
            "user_id": _resolve_user_id(url_entry),
            "is_active": url_entry.is_active,
        },
    )

    set_short_link(url_entry)

    return jsonify(url_entry.to_dict())


@urls_bp.route("/urls/<int:url_id>", methods=["DELETE"])
def delete_url(url_id):
    try:
        url_entry = Url.get_by_id(url_id)
    except Url.DoesNotExist:
        return jsonify(error="URL not found"), 404

    short_code = url_entry.short_code
    Url.delete().where(Url.id == url_id).execute()
    delete_short_link(short_code)

    logger.info(
        "url_deleted",
        extra={"component": "urls", "url_id": url_id, "short_code": short_code},
    )
    return ("", 204)


@urls_bp.route("/<string:short_code>", methods=["GET"])
def redirect_short_url(short_code):
    cached = get_short_link(short_code)
    if cached is not None:
        url_entry = SimpleNamespace(
            id=cached["id"],
            short_code=cached["short_code"],
            original_url=cached["original_url"],
            is_active=cached["is_active"],
            user_id=cached.get("user_id"),
        )
    else:
        try:
            url_entry = Url.get(Url.short_code == short_code)
        except Url.DoesNotExist:
            return jsonify(error="Short URL not found"), 404
        set_short_link(url_entry)

    if not url_entry.is_active:
        return jsonify(error="Short URL is inactive"), 410

    Event.create_event(
        url=url_entry,
        user=_resolve_user_id(url_entry),
        event_type="click",
        details={
            "short_code": url_entry.short_code,
            "original_url": url_entry.original_url,
            "ip_address": request.headers.get("X-Forwarded-For", request.remote_addr),
            "user_agent": request.user_agent.string,
        },
        immediate=True,
    )

    logger.info(
        "short_url_redirect",
        extra={
            "component": "urls",
            "url_id": getattr(url_entry, "id", None),
            "short_code": url_entry.short_code,
            "cache_hit": cached is not None,
        },
    )

    return redirect(url_entry.original_url, code=302)
