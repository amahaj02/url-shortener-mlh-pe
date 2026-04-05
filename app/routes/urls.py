import logging
import re
from datetime import datetime
from urllib.parse import urlparse

from flask import Blueprint, jsonify, make_response, request
from peewee import IntegrityError

from app.cache import delete_short_link, get_short_link, set_short_link
from app.database import db
from app.json_request import require_json_object
from app.models.event import Event
from app.models.url import Url

urls_bp = Blueprint("urls", __name__)
redirect_bp = Blueprint("redirect", __name__)
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


def _event_client_ip():
    """Client IP: first non-empty address in X-Forwarded-For, else remote_addr."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        for part in forwarded.split(","):
            ip = part.strip()
            if ip:
                return ip
    return request.remote_addr


def _normalize_title(value):
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _parse_query_bool(raw):
    """Query param is_active: true/false (case-insensitive) or 1/0."""
    s = raw.strip().lower()
    if s in {"true", "1"}:
        return True
    if s in {"false", "0"}:
        return False
    return None


def _is_user_fk_violation(error):
    message = str(error).lower()
    return "foreign key" in message or "url_user_id_fkey" in message


_CUSTOM_SHORT_CODE_RE = re.compile(r"^[A-Za-z0-9]{4,20}$")


def _is_short_code_unique_violation(error):
    message = str(error).lower()
    return "short_code" in message and ("unique" in message or "duplicate" in message)


@urls_bp.route("/urls", methods=["POST"])
def create_url():
    payload, err = require_json_object()
    if err:
        return err

    allowed_create = {"user_id", "original_url", "title", "short_code"}
    if set(payload.keys()) - allowed_create:
        return jsonify(
            errors={"payload": "Only user_id, original_url, title and short_code can be provided"},
        ), 400

    errors = {}
    uid_raw = payload.get("user_id")
    if type(uid_raw) is int:
        user_id = uid_raw
    else:
        user_id = None
        errors["user_id"] = "must be an integer"

    original_url = payload.get("original_url")
    if not isinstance(original_url, str):
        errors["original_url"] = "must be a non-empty string"
    elif not original_url.strip():
        errors["original_url"] = "must be a non-empty string"
    elif not _is_valid_url(original_url):
        errors["original_url"] = "must be a valid http or https URL"

    if "title" in payload:
        tv = payload["title"]
        if tv is not None and not isinstance(tv, str):
            errors["title"] = "must be a string"

    if errors:
        return jsonify(errors=errors), 400

    stripped_url = original_url.strip()
    existing = (
        Url.select()
        .where((Url.user == user_id) & (Url.original_url == stripped_url))
        .first()
    )
    if existing:
        if existing.is_active:
            set_short_link(existing)
        return jsonify(existing.to_dict()), 200

    custom_short_code = None
    short_code_errors = {}
    if "short_code" in payload:
        sc = payload["short_code"]
        if not isinstance(sc, str):
            short_code_errors["short_code"] = "must be a non-empty string"
        else:
            stripped_sc = sc.strip()
            if not stripped_sc:
                short_code_errors["short_code"] = "must be a non-empty string"
            elif not _CUSTOM_SHORT_CODE_RE.fullmatch(stripped_sc):
                short_code_errors["short_code"] = "must be 4-20 alphanumeric characters"
            else:
                custom_short_code = stripped_sc

    if short_code_errors:
        return jsonify(errors=short_code_errors), 400

    if custom_short_code and Url.select().where(Url.short_code == custom_short_code).exists():
        return jsonify(errors={"short_code": "already taken"}), 400

    title = payload.get("title")
    try:
        if custom_short_code:
            url_entry = Url.create(
                user=user_id,
                original_url=stripped_url,
                title=_normalize_title(title) if title is not None else None,
                is_active=True,
                short_code=custom_short_code,
            )
        else:
            url_entry = Url.create(
                user=user_id,
                original_url=stripped_url,
                title=_normalize_title(title) if title is not None else None,
                is_active=True,
            )
    except IntegrityError as error:
        if _is_user_fk_violation(error):
            return jsonify(error="User not found"), 404
        if _is_short_code_unique_violation(error):
            return jsonify(errors={"short_code": "already taken"}), 400
        return jsonify(errors={"url": "Could not create URL"}), 400

    if not custom_short_code:
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
            return jsonify(errors={"user_id": "must be an integer"}), 400
        query = query.where(Url.user == user_id_num)

    is_active = request.args.get("is_active")
    if is_active is not None:
        normalized = _parse_query_bool(is_active)
        if normalized is None:
            return jsonify(
                errors={"is_active": "must be true, false, 1, or 0"},
            ), 400
        query = query.where(Url.is_active == normalized)

    return jsonify([url_entry.to_dict() for url_entry in query.iterator()])


@urls_bp.route("/urls/<int:url_id>", methods=["GET"])
def get_url(url_id):
    try:
        url_entry = Url.get_by_id(url_id)
    except Url.DoesNotExist:
        return jsonify(error="Resource not found"), 404

    return jsonify(url_entry.to_dict())


@urls_bp.route("/urls/<int:url_id>", methods=["PUT"])
def update_url(url_id):
    payload, err = require_json_object()
    if err:
        return err
    if len(payload) == 0:
        return jsonify(errors={"payload": "JSON object with updatable fields is required"}), 400

    allowed = {"title", "is_active", "original_url"}
    if any(field not in allowed for field in payload.keys()):
        return jsonify(errors={"payload": "Only title, is_active and original_url can be updated"}), 400

    errors = {}
    if "title" in payload and payload["title"] is not None and not isinstance(payload["title"], str):
        errors["title"] = "must be a string"
    if "is_active" in payload and not isinstance(payload["is_active"], bool):
        errors["is_active"] = "must be a boolean"
    if "original_url" in payload:
        ou = payload["original_url"]
        if not isinstance(ou, str):
            errors["original_url"] = "must be a non-empty string"
        elif not ou.strip():
            errors["original_url"] = "must be a non-empty string"
        elif not _is_valid_url(ou):
            errors["original_url"] = "must be a valid http or https URL"
    if errors:
        return jsonify(errors=errors), 400

    try:
        url_entry = Url.get_by_id(url_id)
    except Url.DoesNotExist:
        return jsonify(error="Resource not found"), 404

    if "title" in payload:
        raw_title = payload["title"]
        url_entry.title = _normalize_title(raw_title) if raw_title is not None else None
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

    if url_entry.is_active:
        set_short_link(url_entry)
    else:
        delete_short_link(url_entry.short_code)

    return jsonify(url_entry.to_dict())


@urls_bp.route("/urls/<int:url_id>", methods=["DELETE"])
def delete_url(url_id):
    try:
        url_entry = Url.get_by_id(url_id)
    except Url.DoesNotExist:
        return jsonify(error="Resource not found"), 404

    short_code = url_entry.short_code
    Url.delete().where(Url.id == url_id).execute()
    delete_short_link(short_code)

    logger.info(
        "url_deleted",
        extra={"component": "urls", "url_id": url_id, "short_code": short_code},
    )
    return ("", 204)


@redirect_bp.route("/<string:short_code>", methods=["GET"])
def redirect_short_url(short_code):
    """Resolve redirects from the database so is_active is never stale vs Redis."""
    try:
        url_entry = Url.get(Url.short_code == short_code)
    except Url.DoesNotExist:
        return jsonify(error="Resource not found"), 404

    if not url_entry.is_active:
        return jsonify(error="Short URL is inactive"), 410

    cached = get_short_link(short_code)
    cache_hit = cached is not None
    if cached and cached.get("original_url"):
        destination = cached["original_url"]
        if destination != url_entry.original_url:
            destination = url_entry.original_url
            set_short_link(url_entry)
    else:
        destination = url_entry.original_url
        set_short_link(url_entry)

    Event.create_event(
        url=url_entry,
        user=_resolve_user_id(url_entry),
        event_type="click",
        details={
            "short_code": url_entry.short_code,
            "original_url": destination,
            "ip_address": _event_client_ip(),
            "user_agent": request.headers.get("User-Agent")
            or (request.user_agent.string if request.user_agent else "")
            or "",
        },
        immediate=True,
    )

    logger.info(
        "short_url_redirect",
        extra={
            "component": "urls",
            "url_id": getattr(url_entry, "id", None),
            "short_code": url_entry.short_code,
            "cache_hit": cache_hit,
        },
    )

    response = make_response("", 302)
    response.headers["Location"] = destination
    return response
