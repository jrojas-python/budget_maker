from beanie import Document, Indexed


class Category(Document):
    """Categoría de productos."""

    name: str
    slug: Indexed(str, unique=True)
    description: str = ""
    is_active: bool = True

    class Settings:
        name = "categories"
