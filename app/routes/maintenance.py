from flask import Blueprint, jsonify
from peewee import SqliteDatabase

from app.cache import clear_namespace
from app.database import db
from app.models import ALL_MODELS

maintenance_bp = Blueprint("maintenance", __name__)


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
