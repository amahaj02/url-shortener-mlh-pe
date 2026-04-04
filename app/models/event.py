import json
from datetime import datetime

from peewee import AutoField, CharField, DateTimeField, ForeignKeyField, TextField

from app.database import BaseModel
from app.models.url import Url
from app.models.user import User


class Event(BaseModel):
    id = AutoField()
    url = ForeignKeyField(Url, null=True, backref="events", on_delete="SET NULL")
    user = ForeignKeyField(User, null=True, backref="events", on_delete="SET NULL")
    event_type = CharField()
    timestamp = DateTimeField(default=datetime.utcnow)
    details = TextField(default="{}")

    @classmethod
    def serialize_details(cls, details):
        if not isinstance(details, dict):
            details = {}
        return json.dumps(details)

    @classmethod
    def create_event(cls, *, url, user, event_type, details):
        from app.event_pipeline import enqueue

        if not isinstance(details, dict):
            details = {}

        url_id = getattr(url, "id", None) if url is not None else None
        if isinstance(user, int):
            user_id = user
        elif user is None:
            user_id = None
        else:
            user_id = getattr(user, "id", None)

        enqueue(url_id, user_id, event_type, details)
        return None

    def to_dict(self):
        try:
            details = json.loads(self.details) if self.details else {}
        except json.JSONDecodeError:
            details = {}

        return {
            "id": self.id,
            "url_id": self.url_id,
            "user_id": self.user_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(timespec="seconds"),
            "details": details,
        }
