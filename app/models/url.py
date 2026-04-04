import random
import string
from datetime import datetime

from peewee import AutoField, BooleanField, CharField, DateTimeField, ForeignKeyField, TextField

from app.database import BaseModel
from app.models.user import User


class Url(BaseModel):
    class Meta:
        indexes = (
            (("user", "id"), False),
        )

    id = AutoField()
    user = ForeignKeyField(User, backref="urls", on_delete="CASCADE")
    short_code = CharField(unique=True)
    original_url = TextField()
    title = CharField(null=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    @classmethod
    def generate_short_code(cls, length=6):
        alphabet = string.ascii_letters + string.digits
        return "".join(random.choices(alphabet, k=length))

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