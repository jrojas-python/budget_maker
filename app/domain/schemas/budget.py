from datetime import datetime, timezone

from pydantic import UUID4, BaseModel, Field, field_serializer

from app.domain.models.budget import BudgetItem, ClientInfo


class BudgetItemCreate(BaseModel):
    sku: str
    quantity: int = Field(gt=0)
    color_hex: str | None = None


class BudgetCreate(BaseModel):
    client_info: ClientInfo
    items: list[BudgetItemCreate] = Field(min_length=1)
    payment_method: str | None = None


class ClientInfoUpdate(BaseModel):
    nombres: str | None = None
    apellidos: str | None = None
    documento: str | None = None
    direccion: str | None = None
    email: str | None = None
    vendedor: str | None = None
    compania: str | None = None
    observaciones: str | None = None


class BudgetUpdate(BaseModel):
    client_info: ClientInfoUpdate | None = None
    items: list[BudgetItemCreate] | None = Field(default=None, min_length=1)
    payment_method: str | None = None


class BudgetSearchParams(BaseModel):
    q: str | None = None
    client_id: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    is_expired: bool | None = None
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)


class BudgetResponse(BaseModel):
    code: str
    uuid: UUID4
    client_info: ClientInfo
    items: list[BudgetItem]
    subtotal: float
    tax_percent: float
    tax_amount: float
    total: float
    payment_method: str | None = None
    link_ttl_minutes: int
    created_at: datetime
    expires_at: datetime | None = None

    @field_serializer("created_at", "expires_at")
    def serialize_utc_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        aware_value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        return aware_value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class BudgetAdminResponse(BudgetResponse):
    id: str
    client_id: str | None = None
    is_expired: bool


class BudgetWhatsappShareResponse(BaseModel):
    whatsapp_url: str
