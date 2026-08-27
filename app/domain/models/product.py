import pymongo
from beanie import Document, Indexed, PydanticObjectId
from pydantic import BaseModel, Field


class ProductColor(BaseModel):
    name: str
    hex: str


class Product(Document):
    """Producto del catálogo."""

    name: str
    sku: Indexed(str, unique=True)
    description: str = ""
    brand: str = ""
    cost: float
    unit: str = "unidad"
    currency: str = "USD"
    image_filename: str | None = None
    images: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    category_ids: list[PydanticObjectId] = Field(default_factory=list)
    colors: list[ProductColor] = Field(default_factory=list)

    class Settings:
        name = "products"
        indexes = [
            [("name", pymongo.TEXT)],
        ]
