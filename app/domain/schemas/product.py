import re

from pydantic import BaseModel, Field, field_validator

from app.domain.schemas.category import CategoryResponse

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _normalize_tags(tags: list[str] | None) -> list[str] | None:
    if tags is None:
        return None

    normalized_tags: list[str] = []
    seen_tags: set[str] = set()
    for tag in tags:
        normalized_tag = tag.strip().lower()
        if not normalized_tag or normalized_tag in seen_tags:
            continue
        seen_tags.add(normalized_tag)
        normalized_tags.append(normalized_tag)

    if len(normalized_tags) > 15:
        raise ValueError("Un producto puede tener máximo 15 tags")

    return normalized_tags


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
    category_ids: list[str] = Field(default_factory=list)
    colors: list[ProductColorSchema] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list, max_length=15)

    @field_validator("colors")
    @classmethod
    def max_colors(cls, v: list[ProductColorSchema]) -> list[ProductColorSchema]:
        if len(v) > 6:
            raise ValueError("Un producto puede tener máximo 6 colores")
        return v

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, v: list[str]) -> list[str]:
        return _normalize_tags(v) or []


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    brand: str | None = None
    cost: float | None = None
    unit: str | None = None
    currency: str | None = None
    category_ids: list[str] | None = None
    colors: list[ProductColorSchema] | None = None
    tags: list[str] | None = Field(default=None, max_length=15)

    @field_validator("colors")
    @classmethod
    def max_colors(cls, v: list[ProductColorSchema] | None) -> list[ProductColorSchema] | None:
        if v is not None and len(v) > 6:
            raise ValueError("Un producto puede tener máximo 6 colores")
        return v

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, v: list[str] | None) -> list[str] | None:
        return _normalize_tags(v)


class ProductResponse(BaseModel):
    id: str
    name: str
    sku: str
    description: str = ""
    brand: str = ""
    cost: float
    unit: str
    currency: str
    image_urls: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    category_ids: list[str] = Field(default_factory=list)
    categories: list[CategoryResponse] = Field(default_factory=list)
    colors: list[ProductColorSchema] = Field(default_factory=list)
