import logging
from typing import Any

from beanie import PydanticObjectId

from app.domain.models.category import Category
from app.infrastructure.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class CategoryRepository(BaseRepository):
    """Repositorio de categorías de productos."""

    model = Category

    async def get_all(self) -> list[Category]:
        return await Category.find_all().to_list()

    async def get_by_id(self, doc_id: str) -> Category | None:
        return await Category.get(PydanticObjectId(doc_id))

    async def get_by_slug(self, slug: str) -> Category | None:
        return await Category.find_one(Category.slug == slug)

    async def get_active(self) -> list[Category]:
        return await Category.find(Category.is_active == True).to_list()  # noqa: E712

    async def create(self, data: dict[str, Any]) -> Category:
        category = Category(**data)
        await category.insert()
        logger.info("Categoría creada: %s", category.slug)
        return category

    async def update(self, doc_id: str, data: dict[str, Any]) -> Category | None:
        category = await self.get_by_id(doc_id)
        if not category:
            return None
        await category.set(data)
        return category

    async def delete(self, doc_id: str) -> bool:
        category = await self.get_by_id(doc_id)
        if not category:
            return False
        await category.delete()
        return True
