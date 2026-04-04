from dotenv import load_dotenv
from flask import Flask, jsonify

from app.database import db, init_db
from app.routes import register_routes


def create_app(testing=False):
    load_dotenv()

    app = Flask(__name__)
    app.config["TESTING"] = testing

    if not testing:
        init_db(app)

        from app import models  # noqa: F401 - registers models with Peewee
        from app.models import ALL_MODELS

        db.connect(reuse_if_open=True)
        db.create_tables(ALL_MODELS, safe=True)
        if not db.is_closed():
            db.close()

    register_routes(app)

    @app.route("/health")
    def health():
        return jsonify(status="ok")

    return app
