import logging
from typing import Any

from beanie import PydanticObjectId

from app.domain.models.product import Product
from app.infrastructure.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class ProductRepository(BaseRepository):
    """Repositorio de productos con soporte upsert por SKU."""

    model = Product

    async def get_all(self) -> list[Product]:
        return await Product.find_all().to_list()

    async def get_by_id(self, doc_id: str) -> Product | None:
        return await Product.get(PydanticObjectId(doc_id))

    async def get_by_sku(self, sku: str) -> Product | None:
        return await Product.find_one(Product.sku == sku)

    async def create(self, data: dict[str, Any]) -> Product:
        product = Product(**data)
        await product.insert()
        logger.info("Producto creado: %s", product.sku)
        return product

    async def update(self, doc_id: str, data: dict[str, Any]) -> Product | None:
        product = await self.get_by_id(doc_id)
        if not product:
            return None
        await product.set(data)
        return product

    async def delete(self, doc_id: str) -> bool:
        product = await self.get_by_id(doc_id)
        if not product:
            return False
        await product.delete()
        return True

    async def upsert_by_sku(self, data: dict[str, Any]) -> Product:
        """Actualiza si el SKU existe, crea si no."""
        existing = await self.get_by_sku(data["sku"])
        if existing:
            update_data = {k: v for k, v in data.items() if k != "sku"}
            await existing.set(update_data)
            logger.info("Producto actualizado por SKU: %s", data["sku"])
            return existing
        return await self.create(data)
