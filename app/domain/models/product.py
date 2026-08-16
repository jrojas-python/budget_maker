from beanie import Document, Indexed


class Product(Document):
    """Producto del catálogo."""

    name: str
    sku: Indexed(str, unique=True)
    cost: float
    unit: str = "unidad"
    currency: str = "USD"

    class Settings:
        name = "products"
