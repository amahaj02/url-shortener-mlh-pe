import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.database import close_db, db, ensure_url_user_original_url_index
from app.models import ALL_MODELS


@pytest.fixture(scope="session")
def app():
    os.environ["TESTING"] = "true"
    return create_app()


@pytest.fixture
def test_db(app):
    if db.is_closed():
        db.connect(reuse_if_open=True)
    db.create_tables(ALL_MODELS, safe=True)
    ensure_url_user_original_url_index()
    yield db


@pytest.fixture(autouse=True)
def clean_db(test_db, app):
    from app.cache import clear_namespace

    with app.app_context():
        clear_namespace()
    for model in reversed(ALL_MODELS):
        model.delete().execute()
    yield


@pytest.fixture(scope="session", autouse=True)
def close_test_db():
    yield
    close_db()


@pytest.fixture
def client(app):
    return app.test_client()
