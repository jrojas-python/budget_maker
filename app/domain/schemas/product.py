from pydantic import BaseModel


class ProductCreate(BaseModel):
    name: str
    sku: str
    cost: float
    unit: str = "unidad"
    currency: str = "USD"


class ProductUpdate(BaseModel):
    name: str | None = None
    cost: float | None = None
    unit: str | None = None
    currency: str | None = None


class ProductResponse(BaseModel):
    id: str
    name: str
    sku: str
    cost: float
    unit: str
    currency: str
