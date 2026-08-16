from datetime import datetime, timezone

from beanie import Document
from pydantic import BaseModel, Field

from app.domain.models.product import Product


class ClientInfo(BaseModel):
    """Datos del cliente en el presupuesto."""

    nombres: str
    apellidos: str
    documento: str = ""
    direccion: str = ""
    vendedor: str = ""


class BudgetItem(BaseModel):
    """Línea de producto dentro del presupuesto."""

    sku: str
    name: str
    quantity: int
    unit_cost: float
    line_total: float = 0.0


class Budget(Document):
    """Presupuesto / cotización generada."""

    code: str = Field(..., description="Formato BM-YYYYMMDD-XXXX")
    uuid: str = Field(..., description="UUID4 público para URLs")
    client_info: ClientInfo
    items: list[BudgetItem]
    subtotal: float = 0.0
    tax_percent: float = 0.0
    tax_amount: float = 0.0
    total: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "budgets"
