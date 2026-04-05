import os

from flask import Blueprint, jsonify, request
from peewee import SqliteDatabase

from app.cache import clear_namespace
from app.database import db
from app.models import ALL_MODELS

maintenance_bp = Blueprint("maintenance", __name__)


def _env_bool(name, default=False):
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


@maintenance_bp.route("/admin/clear-db", methods=["GET"])
def clear_database_help():
    return jsonify(
        endpoint="/admin/clear-db",
        method="POST",
        description="Deletes all rows from known tables in reverse dependency order.",
    )


@maintenance_bp.route("/admin/clear-db", methods=["POST"])
def clear_database():
    deleted = {}

    with db.atomic():
        if isinstance(db.obj, SqliteDatabase):
            for model in reversed(ALL_MODELS):
                deleted[model.__name__.lower()] = model.delete().execute()
            for model in ALL_MODELS:
                try:
                    db.execute_sql(
                        "DELETE FROM sqlite_sequence WHERE name=?",
                        (model._meta.table_name,),
                    )
                except Exception:
                    pass
        else:
            for model in ALL_MODELS:
                deleted[model.__name__.lower()] = model.select().count()
            tables = ", ".join(f'"{m._meta.table_name}"' for m in reversed(ALL_MODELS))
            db.execute_sql(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE")

    clear_namespace()

    return jsonify(
        message="Database cleared",
        deleted=deleted,
        total_deleted=sum(deleted.values()),
    )


@maintenance_bp.route("/admin/chaos/500", methods=["GET"])
def chaos_500():
    if not _env_bool("CHAOS_MODE", default=False):
        return jsonify(error="Not found"), 404

    expected_token = os.getenv("CHAOS_TOKEN", "").strip()
    provided_token = request.headers.get("X-Chaos-Token", "").strip()
    if not expected_token or provided_token != expected_token:
        return jsonify(error="Forbidden"), 403

    return (
        jsonify(
            error="Chaos mode: forced internal server error",
            code="CHAOS_500",
        ),
        500,
    )
