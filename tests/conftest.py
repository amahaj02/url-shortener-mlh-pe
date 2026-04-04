import sys
from pathlib import Path

import pytest
from peewee import SqliteDatabase

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.database import db
from app.models import ALL_MODELS


@pytest.fixture(scope="session")
def app():
    return create_app(testing=True)


@pytest.fixture
def test_db():
    database = SqliteDatabase(":memory:", pragmas={"foreign_keys": 1})
    db.initialize(database)
    database.connect()
    database.create_tables(ALL_MODELS)
    yield database
    database.drop_tables(list(reversed(ALL_MODELS)))
    database.close()


@pytest.fixture(autouse=True)
def clean_db(test_db):
    for model in reversed(ALL_MODELS):
        model.delete().execute()
    yield


@pytest.fixture
def client(app):
    return app.test_client()
