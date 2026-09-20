from datetime import datetime, timezone

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field
from pymongo import IndexModel

from app.domain.models.product import Product


class ClientInfo(BaseModel):
    """Datos del cliente en el presupuesto."""

    nombres: str
    apellidos: str = ""
    documento: str = ""
    direccion: str = ""
    email: str = ""
    vendedor: str = ""
    compania: str = ""
    observaciones: str = ""


class BudgetItem(BaseModel):
    """Línea de producto dentro del presupuesto."""

    sku: str
    name: str
    quantity: int
    unit_cost: float
    line_total: float = 0.0
    color_name: str | None = None
    color_hex: str | None = None


class BudgetIdentifierCollisionError(ValueError):
    """Error de colisión de identificador público en presupuesto."""

    def __init__(self, identifier: str):
        self.identifier = identifier
        super().__init__(f"Identificador público duplicado: {identifier}")


class Budget(Document):
    """Presupuesto / cotización generada."""

    code: str = Field(..., description="Formato BM-YYYYMMDD-XXXX")
    uuid: str = Field(..., description="UUID4 público para URLs")
    client_id: PydanticObjectId | None = None
    client_info: ClientInfo
    items: list[BudgetItem]
    subtotal: float = 0.0
    tax_percent: float = 0.0
    tax_amount: float = 0.0
    total: float = 0.0
    payment_method: str | None = None
    link_ttl_minutes: int = 30
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None

    class Settings:
        name = "budgets"
        indexes = [
            IndexModel(
                [("code", 1)],
                name="uq_budget_code",
                unique=True,
                partialFilterExpression={"code": {"$exists": True}},
            ),
            IndexModel(
                [("uuid", 1)],
                name="uq_budget_uuid",
                unique=True,
                partialFilterExpression={"uuid": {"$exists": True}},
            ),
        ]
