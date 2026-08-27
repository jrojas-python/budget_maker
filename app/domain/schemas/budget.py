from datetime import datetime

from pydantic import BaseModel

from app.domain.models.budget import BudgetItem, ClientInfo


class BudgetItemCreate(BaseModel):
    sku: str
    quantity: int
    color_hex: str | None = None


class BudgetCreate(BaseModel):
    client_info: ClientInfo
    items: list[BudgetItemCreate]
    payment_method: str | None = None


class BudgetResponse(BaseModel):
    code: str
    uuid: str
    client_info: ClientInfo
    items: list[BudgetItem]
    subtotal: float
    tax_percent: float
    tax_amount: float
    total: float
    payment_method: str | None = None
    link_ttl_minutes: int
    created_at: datetime
