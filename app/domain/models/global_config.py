from beanie import Document
from pydantic import Field
from pymongo import IndexModel


class GlobalConfig(Document):
    """Configuración global tipada del negocio con espacio para claves auxiliares."""

    singleton_key: str = Field(default="global", description="Identificador único del documento global")
    tax_rate: float = Field(default=18.0, ge=0, le=100)
    link_ttl_minutes: int = Field(default=30, ge=1, le=10080)
    show_product_photos_in_pdf: bool = True
    extra_settings: dict[str, float | str | int | bool] = Field(default_factory=dict)
    descriptions: dict[str, str] = Field(default_factory=dict)

    class Settings:
        name = "global_config"
        indexes = [
            IndexModel(
                [("singleton_key", 1)],
                unique=True,
                partialFilterExpression={"singleton_key": {"$exists": True}},
            ),
        ]
