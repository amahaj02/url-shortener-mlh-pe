from flask import Blueprint, jsonify

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
        for model in reversed(ALL_MODELS):
            deleted[model.__name__.lower()] = model.delete().execute()

    clear_namespace()

    return jsonify(
        message="Database cleared",
        deleted=deleted,
        total_deleted=sum(deleted.values()),
    )
