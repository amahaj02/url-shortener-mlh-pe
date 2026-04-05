import csv
import io
import logging
import re
from datetime import datetime

from flask import Blueprint, jsonify, request
from peewee import IntegrityError, chunked

from app.database import db
from app.json_request import require_json_object
from app.models.event import Event
from app.models.user import User

users_bp = Blueprint("users", __name__)
logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
BULK_IMPORT_BATCH_SIZE = 100


def _parse_datetime(value):
    if not value:
        return None

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    return None


def _validate_user_payload(data, is_partial=False):
    errors = {}

    if not isinstance(data, dict):
        return {"payload": "JSON object required"}

    username = data.get("username")
    email = data.get("email")

    if not is_partial or "username" in data:
        if not isinstance(username, str) or not username.strip():
            errors["username"] = "username must be a non-empty string"

    if not is_partial or "email" in data:
        if not isinstance(email, str) or not EMAIL_PATTERN.match(email):
            errors["email"] = "email must be a valid email string"

    return errors


def _build_user_create_fields(row):
    username = (row.get("username") or "").strip()
    email = (row.get("email") or "").strip()
    created_at = _parse_datetime((row.get("created_at") or "").strip())

    if not username or not EMAIL_PATTERN.match(email):
        return None

    create_fields = {
        "username": username,
        "email": email,
    }

    if created_at is not None:
        create_fields["created_at"] = created_at

    return create_fields


@users_bp.route("/users/bulk", methods=["POST"])
def bulk_import_users():
    if not request.files:
        return jsonify(errors={"file": "multipart file upload is required"}), 400

    uploaded_file = request.files.get("file")
    if uploaded_file is None:
        uploaded_file = next(iter(request.files.values()))

    content = uploaded_file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))

    rows = []
    for row in reader:
        create_fields = _build_user_create_fields(row)
        if create_fields is not None:
            rows.append(create_fields)

    count = 0
    with db.atomic():
        for batch in chunked(rows, BULK_IMPORT_BATCH_SIZE):
            count += (
                User.insert_many(batch)
                .on_conflict_ignore()
                .as_rowcount()
                .execute()
            )

    Event.create_event(
        url=None,
        user=None,
        event_type="bulk_users_imported",
        details={"imported_row_count": count},
    )
    logger.info(
        "bulk_users_imported",
        extra={"component": "users", "imported_row_count": count},
    )

    return jsonify(count=count), 201


@users_bp.route("/users", methods=["GET"])
def list_users():
    query = User.select().order_by(User.id)

    page = request.args.get("page")
    per_page = request.args.get("per_page")
    if page is not None or per_page is not None:
        try:
            page_num = max(int(page or 1), 1)
            size = max(int(per_page or 20), 1)
        except ValueError:
            return jsonify(errors={"pagination": "page and per_page must be integers"}), 400

        query = query.paginate(page_num, size)

    return jsonify([user.to_dict() for user in query])


@users_bp.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    try:
        user = User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="User not found"), 404

    return jsonify(user.to_dict())


@users_bp.route("/users", methods=["POST"])
def create_user():
    payload, err = require_json_object()
    if err:
        return err
    errors = _validate_user_payload(payload, is_partial=False)
    if errors:
        return jsonify(errors=errors), 400

    try:
        user = User.create(
            username=payload["username"].strip(),
            email=payload["email"].strip(),
        )
    except IntegrityError:
        existing_user = (
            User.select()
            .where(
                (User.username == payload["username"].strip())
                & (User.email == payload["email"].strip())
            )
            .first()
        )
        if existing_user is not None:
            logger.info(
                "user_create_idempotent",
                extra={
                    "component": "users",
                    "user_id": existing_user.id,
                    "username": existing_user.username,
                },
            )
            return jsonify(existing_user.to_dict()), 201
        logger.warning(
            "user_create_conflict",
            extra={"component": "users", "username": payload.get("username")},
        )
        return jsonify(errors={"user": "username or email already exists"}), 409

    Event.create_event(
        url=None,
        user=user.id,
        event_type="user_created",
        details={"username": user.username, "email": user.email},
    )
    logger.info(
        "user_created",
        extra={"component": "users", "user_id": user.id, "username": user.username},
    )

    return jsonify(user.to_dict()), 201


@users_bp.route("/users/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    payload, err = require_json_object()
    if err:
        return err
    if not payload:
        return jsonify(errors={"payload": "JSON object with updatable fields is required"}), 400

    allowed = {"username", "email"}
    if any(field not in allowed for field in payload.keys()):
        return jsonify(errors={"payload": "Only username and email can be updated"}), 400

    errors = _validate_user_payload(payload, is_partial=True)
    if errors:
        return jsonify(errors=errors), 400

    try:
        user = User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="User not found"), 404

    if "username" in payload:
        user.username = payload["username"].strip()
    if "email" in payload:
        user.email = payload["email"].strip()

    try:
        user.save()
    except IntegrityError:
        logger.warning(
            "user_update_conflict",
            extra={"component": "users", "user_id": user_id},
        )
        return jsonify(errors={"user": "username or email already exists"}), 409

    Event.create_event(
        url=None,
        user=user.id,
        event_type="user_updated",
        details={"username": user.username, "email": user.email},
    )
    logger.info(
        "user_updated",
        extra={"component": "users", "user_id": user.id},
    )

    return jsonify(user.to_dict())


@users_bp.route("/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    deleted = User.delete().where(User.id == user_id).execute()
    if deleted == 0:
        return jsonify(error="User not found"), 404

    logger.info(
        "user_deleted",
        extra={"component": "users", "user_id": user_id},
    )
    return ("", 204)
