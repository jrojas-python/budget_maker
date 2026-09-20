from __future__ import annotations

from datetime import datetime, timezone

from beanie import Document
from pydantic import Field
from pymongo import IndexModel


class Client(Document):
    """Cliente reutilizable para la gestión administrativa."""

    nombres: str
    apellidos: str = ""
    email: str = ""
    documento: str = ""
    compania: str = ""
    direccion: str = ""
    observaciones: str = ""
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "clients"
        indexes = [
            IndexModel(
                [("documento", 1)],
                name="uq_client_documento_non_empty",
                unique=True,
                partialFilterExpression={"documento": {"$type": "string", "$gt": ""}},
            ),
        ]
