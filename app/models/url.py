from datetime import datetime

from peewee import AutoField, BooleanField, CharField, DateTimeField, ForeignKeyField, TextField

from app.database import BaseModel
from app.models.user import User

SHORT_CODE_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


class Url(BaseModel):
    id = AutoField()
    user = ForeignKeyField(User, backref="urls", on_delete="CASCADE")
    short_code = CharField(unique=True, null=True)
    original_url = TextField()
    title = CharField(null=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    @classmethod
    def short_code_from_id(cls, row_id):
        if not isinstance(row_id, int) or row_id < 1:
            raise ValueError("row_id must be a positive integer")

        base = len(SHORT_CODE_ALPHABET)
        value = row_id
        encoded = []

        while value > 0:
            value, remainder = divmod(value, base)
            encoded.append(SHORT_CODE_ALPHABET[remainder])

        return "".join(reversed(encoded))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "short_code": self.short_code,
            "original_url": self.original_url,
            "title": self.title,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(timespec="seconds"),
            "updated_at": self.updated_at.isoformat(timespec="seconds"),
        }
