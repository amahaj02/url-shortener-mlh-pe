import os

from peewee import DatabaseProxy, Model, SqliteDatabase
from playhouse.pool import PooledPostgresqlDatabase

db = DatabaseProxy()


class BaseModel(Model):
    class Meta:
        database = db


def init_db(testing=False):
    if getattr(db, "obj", None) is not None and not db.is_closed():
        db.close()

    if testing:
        database = SqliteDatabase(
            "file:testing?mode=memory&cache=shared",
            uri=True,
            pragmas={"foreign_keys": 1},
            check_same_thread=False,
        )
    else:
        database = PooledPostgresqlDatabase(
            os.environ.get("DATABASE_NAME", "hackathon_db"),
            host=os.environ.get("DATABASE_HOST", "localhost"),
            port=int(os.environ.get("DATABASE_PORT", 5432)),
            user=os.environ.get("DATABASE_USER", "postgres"),
            password=os.environ.get("DATABASE_PASSWORD", "postgres"),
            max_connections=int(os.environ.get("DATABASE_MAX_CONNECTIONS", "20")),
            stale_timeout=int(os.environ.get("DATABASE_STALE_TIMEOUT_SECONDS", "300")),
            timeout=int(os.environ.get("DATABASE_POOL_WAIT_TIMEOUT_SECONDS", "10")),
        )

    db.initialize(database)


def connect_db():
    db.connect(reuse_if_open=True)


def close_db():
    if not db.is_closed():
        db.close()
