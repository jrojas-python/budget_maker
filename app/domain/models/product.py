import pymongo
from beanie import Document, Indexed, PydanticObjectId
from pydantic import BaseModel


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
    category_ids: list[PydanticObjectId] = []
    colors: list[ProductColor] = []

    class Settings:
        name = "products"
        indexes = [
            [("name", pymongo.TEXT)],
        ]
