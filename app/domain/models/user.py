from datetime import datetime, timezone

from beanie import Document, Indexed
from pydantic import Field


class User(Document):
    """Usuario administrador del sistema."""

    username: Indexed(str, unique=True)
    email: Indexed(str, unique=True)
    hashed_password: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "users"
