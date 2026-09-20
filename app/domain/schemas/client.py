from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class ClientCreate(BaseModel):
    nombres: str
    apellidos: str = ""
    email: str = ""
    documento: str = ""
    compania: str = ""
    direccion: str = ""
    observaciones: str = ""

    @field_validator("nombres", "apellidos", "email", "documento", "compania", "direccion", "observaciones")
    @classmethod
    def strip_strings(cls, value: str) -> str:
        return value.strip()

    @field_validator("nombres")
    @classmethod
    def validate_nombres(cls, value: str) -> str:
        if not value:
            raise ValueError("nombres es obligatorio")
        return value


class ClientUpdate(BaseModel):
    nombres: str | None = None
    apellidos: str | None = None
    email: str | None = None
    documento: str | None = None
    compania: str | None = None
    direccion: str | None = None
    observaciones: str | None = None

    @field_validator(
        "nombres",
        "apellidos",
        "email",
        "documento",
        "compania",
        "direccion",
        "observaciones",
        mode="before",
    )
    @classmethod
    def reject_nulls(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("el campo no admite null")
        return value.strip()

    @field_validator("nombres")
    @classmethod
    def validate_optional_nombres(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("nombres no puede estar vacío")
        return value


class ClientResponse(BaseModel):
    id: str
    nombres: str
    apellidos: str
    email: str
    documento: str
    compania: str
    direccion: str
    observaciones: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
