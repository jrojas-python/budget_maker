import logging
import re
from typing import Any

import pymongo
from beanie import PydanticObjectId

from app.domain.models.product import Product
from app.domain.schemas.search import ProductSearchParams, SortBy
from app.infrastructure.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

SORT_MAP = {
    SortBy.price_asc: [("cost", pymongo.ASCENDING)],
    SortBy.price_desc: [("cost", pymongo.DESCENDING)],
    SortBy.name_asc: [("name", pymongo.ASCENDING)],
    SortBy.name_desc: [("name", pymongo.DESCENDING)],
}


class ProductRepository(BaseRepository):
    """Repositorio de productos con soporte upsert por SKU."""

    model = Product

    async def get_all(self) -> list[Product]:
        return await Product.find_all().to_list()

    async def get_by_id(self, doc_id: str) -> Product | None:
        return await Product.get(PydanticObjectId(doc_id))

    async def get_by_sku(self, sku: str) -> Product | None:
        return await Product.find_one(Product.sku == sku)

    async def get_by_skus(self, skus: list[str]) -> dict[str, Product]:
        unique_skus = list(dict.fromkeys(s.strip() for s in skus if s and s.strip()))
        if not unique_skus:
            return {}
        products = await Product.find({"sku": {"$in": unique_skus}}).to_list()
        return {product.sku: product for product in products}

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

    async def add_image(self, doc_id: str, filename: str) -> Product | None:
        oid = PydanticObjectId(doc_id)
        await Product.find_one(Product.id == oid).update({"$push": {"images": filename}})
        return await self.get_by_id(doc_id)

    async def remove_image(self, doc_id: str, filename: str) -> Product | None:
        oid = PydanticObjectId(doc_id)
        await Product.find_one(Product.id == oid).update({"$pull": {"images": filename}})
        return await self.get_by_id(doc_id)

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

    async def remove_category_from_all(self, category_id: str) -> None:
        """Remueve un category_id de todos los productos que lo referencien."""
        oid = PydanticObjectId(category_id)
        await Product.find(Product.category_ids == oid).update(
            {"$pull": {"category_ids": oid}}
        )

    async def search(self, params: ProductSearchParams, resolved_category_id: str | None = None) -> tuple[list[Product], int]:
        """Búsqueda avanzada con filtros acumulativos, paginación y ordenamiento."""
        query: dict[str, Any] = {}

        if params.q:
            escaped = re.escape(params.q)
            regex_filter = {"$regex": escaped, "$options": "i"}
            query["$or"] = [
                {"name": regex_filter},
                {"sku": regex_filter},
                {"tags": regex_filter},
            ]
        if params.sku:
            query["sku"] = params.sku

        if params.tags:
            normalized_tags = [t.strip().lower() for t in params.tags if t.strip()]
            if normalized_tags:
                query["tags"] = {"$in": normalized_tags}

        cat_id = resolved_category_id or params.category_id
        if cat_id:
            query["category_ids"] = PydanticObjectId(cat_id)

        if params.min_price is not None or params.max_price is not None:
            cost_filter: dict[str, float] = {}
            if params.min_price is not None:
                cost_filter["$gte"] = params.min_price
            if params.max_price is not None:
                cost_filter["$lte"] = params.max_price
            query["cost"] = cost_filter

        find_query = Product.find(query)
        total = await find_query.count()

        sort_spec = SORT_MAP.get(params.sort_by, [("name", pymongo.ASCENDING)])
        results = await find_query.sort(sort_spec).skip((params.page - 1) * params.limit).limit(params.limit).to_list()

        return results, total
