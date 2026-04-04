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
    def create_event(cls, *, url, user, event_type, details):
        return cls.create(
            url=url,
            user=user,
            event_type=event_type,
            details=json.dumps(details),
        )

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