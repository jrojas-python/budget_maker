import re

from pydantic import BaseModel, field_validator

from app.domain.schemas.category import CategoryResponse

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class ProductColorSchema(BaseModel):
    name: str
    hex: str

    @field_validator("hex")
    @classmethod
    def validate_hex(cls, v: str) -> str:
        if not _HEX_RE.match(v):
            raise ValueError("El color debe ser un código hexadecimal válido, ej: #FF0000")
        return v.upper()


class ProductColorsUpdate(BaseModel):
    colors: list[ProductColorSchema]

    @field_validator("colors")
    @classmethod
    def max_colors(cls, v: list[ProductColorSchema]) -> list[ProductColorSchema]:
        if len(v) > 6:
            raise ValueError("Un producto puede tener máximo 6 colores")
        return v


class ProductCreate(BaseModel):
    name: str
    sku: str
    description: str = ""
    brand: str = ""
    cost: float
    unit: str = "unidad"
    currency: str = "USD"
    category_ids: list[str] = []
    colors: list[ProductColorSchema] = []

    @field_validator("colors")
    @classmethod
    def max_colors(cls, v: list[ProductColorSchema]) -> list[ProductColorSchema]:
        if len(v) > 6:
            raise ValueError("Un producto puede tener máximo 6 colores")
        return v


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    brand: str | None = None
    cost: float | None = None
    unit: str | None = None
    currency: str | None = None
    category_ids: list[str] | None = None
    colors: list[ProductColorSchema] | None = None

    @field_validator("colors")
    @classmethod
    def max_colors(cls, v: list[ProductColorSchema] | None) -> list[ProductColorSchema] | None:
        if v is not None and len(v) > 6:
            raise ValueError("Un producto puede tener máximo 6 colores")
        return v


class ProductResponse(BaseModel):
    id: str
    name: str
    sku: str
    description: str = ""
    brand: str = ""
    cost: float
    unit: str
    currency: str
    image_url: str | None = None
    category_ids: list[str] = []
    categories: list[CategoryResponse] = []
    colors: list[ProductColorSchema] = []
