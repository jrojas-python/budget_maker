import logging

from slugify import slugify

from app.domain.models.category import Category
from app.domain.models.product import Product
from app.domain.schemas.category import CategoryCreate, CategoryUpdate
from app.infrastructure.repositories.category_repo import CategoryRepository
from app.infrastructure.repositories.product_repo import ProductRepository

logger = logging.getLogger(__name__)


class CategoryUseCases:
    """Casos de uso para gestión de categorías."""

    def __init__(self, repo: CategoryRepository, product_repo: ProductRepository) -> None:
        self._repo = repo
        self._product_repo = product_repo

    async def list_all(self, active_only: bool = False) -> list[Category]:
        if active_only:
            return await self._repo.get_active()
        return await self._repo.get_all()

    async def get_by_id(self, category_id: str) -> Category | None:
        return await self._repo.get_by_id(category_id)

    async def create(self, data: CategoryCreate) -> Category:
        slug = slugify(data.name)
        if await self._repo.get_by_slug(slug):
            raise ValueError(f"Ya existe una categoría con slug: {slug}")
        return await self._repo.create({
            "name": data.name,
            "slug": slug,
            "description": data.description,
        })

    async def update(self, category_id: str, data: CategoryUpdate) -> Category | None:
        update_data: dict = {}
        if data.name is not None:
            update_data["name"] = data.name
            new_slug = slugify(data.name)
            existing = await self._repo.get_by_slug(new_slug)
            if existing and str(existing.id) != category_id:
                raise ValueError(f"Ya existe una categoría con slug: {new_slug}")
            update_data["slug"] = new_slug
        if data.description is not None:
            update_data["description"] = data.description
        if data.is_active is not None:
            update_data["is_active"] = data.is_active
        if not update_data:
            return await self._repo.get_by_id(category_id)
        return await self._repo.update(category_id, update_data)

    async def delete(self, category_id: str) -> bool:
        """Elimina la categoría y limpia las referencias en productos."""
        category = await self._repo.get_by_id(category_id)
        if not category:
            return False
        await self._repo.delete(category_id)
        await self._product_repo.remove_category_from_all(category_id)
        logger.info("Cascade cleanup: categoría %s removida de productos", category_id)
        return True
