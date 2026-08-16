from datetime import datetime

from pydantic import BaseModel

from app.domain.models.budget import BudgetItem, ClientInfo


class BudgetItemCreate(BaseModel):
    sku: str
    quantity: int


class BudgetCreate(BaseModel):
    client_info: ClientInfo
    items: list[BudgetItemCreate]


class BudgetResponse(BaseModel):
    code: str
    uuid: str
    client_info: ClientInfo
    items: list[BudgetItem]
    subtotal: float
    tax_percent: float
    tax_amount: float
    total: float
    created_at: datetime
