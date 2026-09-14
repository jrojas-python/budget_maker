from __future__ import annotations

import logging

from beanie import PydanticObjectId
from fastapi import UploadFile

from app.domain.models.product import Product
from app.domain.schemas.category import CategoryResponse
from app.domain.schemas.product import (
    ProductColorSchema,
    ProductColorsUpdate,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from app.domain.schemas.search import PaginatedResponse, ProductSearchParams
from app.infrastructure.repositories.category_repo import CategoryRepository
from app.infrastructure.repositories.product_repo import ProductRepository
from app.infrastructure.services.excel_service import ExcelService
from app.infrastructure.services.image_service import ImageService

logger = logging.getLogger(__name__)


def _parse_object_id(value: str, field_name: str) -> PydanticObjectId:
    try:
        return PydanticObjectId(value)
    except Exception as exc:
        raise ValueError(f"{field_name} inválido") from exc


def _parse_object_ids(values: list[str], field_name: str) -> list[PydanticObjectId]:
    return [_parse_object_id(value, field_name) for value in values]


def _normalize_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []

    normalized_tags: list[str] = []
    seen_tags: set[str] = set()
    for tag in tags:
        normalized_tag = tag.strip().lower()
        if not normalized_tag or normalized_tag in seen_tags:
            continue
        seen_tags.add(normalized_tag)
        normalized_tags.append(normalized_tag)

    return normalized_tags


def _build_product_image_update(
    *,
    original_images: list[str],
    original_legacy: str | None,
    references: list[str],
) -> dict[str, list[str] | str | None]:
    """Reconstruye images/image_filename sin reintroducir referencias borradas."""
    normalized_references = [str(reference).strip() for reference in references if str(reference).strip()]

    normalized_legacy = str(original_legacy or "").strip()
    keep_legacy_field = bool(
        normalized_legacy
        and normalized_legacy not in original_images
        and normalized_legacy in normalized_references
    )

    legacy_reference = normalized_legacy if keep_legacy_field else None
    images = [
        reference
        for reference in normalized_references
        if not legacy_reference or reference != legacy_reference
    ]
    return {"images": images, "image_filename": legacy_reference}


async def _enrich_categories(
    product: Product,
    category_repo: CategoryRepository,
) -> list[CategoryResponse]:
    """Resuelve category_ids a CategoryResponse."""
    if not product.category_ids:
        return []

    categories: list[CategoryResponse] = []
    for category_id in product.category_ids:
        category = await category_repo.get_by_id(str(category_id))
        if category:
            categories.append(
                CategoryResponse(
                    id=str(category.id),
                    name=category.name,
                    slug=category.slug,
                    description=category.description,
                    is_active=category.is_active,
                )
            )
    return categories


class ProductUseCases:
    """Casos de uso para gestión de productos."""

    def __init__(
        self,
        repo: ProductRepository,
        excel_service: ExcelService,
        image_service: ImageService,
        category_repo: CategoryRepository,
    ) -> None:
        self._repo = repo
        self._excel = excel_service
        self._image = image_service
        self._category_repo = category_repo

    def build_response(
        self,
        product: Product,
        base_url: str,
        categories: list[CategoryResponse] | None = None,
    ) -> ProductResponse:
        """Construye la respuesta pública de un producto."""
        return ProductResponse(
            id=str(product.id),
            name=product.name,
            sku=product.sku,
            description=product.description,
            brand=product.brand,
            cost=product.cost,
            unit=product.unit,
            currency=product.currency,
            image_urls=self._image.build_product_image_urls(
                product.images,
                product.image_filename,
                base_url,
            ),
            tags=_normalize_tags(product.tags),
            category_ids=[str(category_id) for category_id in product.category_ids],
            categories=categories or [],
            colors=[ProductColorSchema(name=color.name, hex=color.hex) for color in product.colors],
        )

    async def list_all(self) -> list[Product]:
        return await self._repo.get_all()

    async def get_by_id(self, product_id: str) -> Product | None:
        return await self._repo.get_by_id(product_id)

    async def create(self, data: ProductCreate) -> Product:
        dump = data.model_dump()
        if dump.get("category_ids"):
            dump["category_ids"] = _parse_object_ids(dump["category_ids"], "category_ids")
        dump["tags"] = _normalize_tags(dump.get("tags"))
        return await self._repo.create(dump)

    async def update(self, product_id: str, data: ProductUpdate) -> Product | None:
        update_data = data.model_dump(exclude_none=True)
        if "category_ids" in update_data:
            update_data["category_ids"] = _parse_object_ids(update_data["category_ids"], "category_ids")
        if "tags" in update_data:
            update_data["tags"] = _normalize_tags(update_data.get("tags"))
        if not update_data:
            return await self._repo.get_by_id(product_id)
        return await self._repo.update(product_id, update_data)

    async def update_colors(self, product_id: str, data: ProductColorsUpdate) -> Product | None:
        product = await self._repo.get_by_id(product_id)
        if not product:
            return None
        await product.set({"colors": [color.model_dump() for color in data.colors]})
        return product

    async def delete(self, product_id: str) -> bool:
        """Elimina producto y sus referencias de imágenes."""
        product = await self._repo.get_by_id(product_id)
        if not product:
            return False

        original_images = list(product.images)
        original_legacy = product.image_filename
        references = self._image.collect_product_references(product.images, product.image_filename)

        deleted_references: list[str] = []
        if references:
            try:
                for reference in references:
                    await self._image.delete_product_image(reference)
                    deleted_references.append(reference)
            except Exception as exc:
                remaining_references = [
                    reference for reference in references if reference not in deleted_references
                ]
                logger.warning(
                    "[product_use_cases] fallo eliminando imágenes en cascada | product_id=%s exc=%s",
                    product_id,
                    exc,
                    exc_info=True,
                )
                await self._repo.update(
                    product_id,
                    _build_product_image_update(
                        original_images=original_images,
                        original_legacy=original_legacy,
                        references=remaining_references,
                    ),
                )
                raise

        refreshed_product = await self._repo.get_by_id(product_id)
        if not refreshed_product:
            return False

        try:
            await refreshed_product.delete()
        except Exception as exc:
            logger.warning(
                "[product_use_cases] fallo eliminando producto tras borrar assets | product_id=%s exc=%s",
                product_id,
                exc,
                exc_info=True,
            )
            if references:
                await self._repo.update(product_id, {"images": [], "image_filename": None})
            raise
        return True

    async def upload_image(self, product_id: str, file: UploadFile) -> Product:
        """Sube una imagen a un producto respetando el límite máximo."""
        product = await self._repo.get_by_id(product_id)
        if not product:
            raise ValueError("Producto no encontrado")

        stored_references = self._image.collect_product_references(
            product.images,
            product.image_filename,
        )
        if len(stored_references) >= 10:
            raise ValueError("El producto ya tiene el máximo de 10 imágenes")

        image_url = await self._image.upload_product_image(product_id, file)
        update_data = {"images": [*stored_references, image_url]}
        if product.image_filename and product.image_filename not in product.images:
            update_data["image_filename"] = None

        try:
            updated_product = await self._repo.update(product_id, update_data)
        except Exception as exc:
            logger.warning(
                "[product_use_cases] fallo persistiendo upload | product_id=%s exc=%s",
                product_id,
                exc,
                exc_info=True,
            )
            await self._safe_delete_uploaded_image(image_url)
            raise

        if not updated_product:
            await self._safe_delete_uploaded_image(image_url)
            raise ValueError("Producto no encontrado")
        return updated_product

    async def delete_image(self, product_id: str, filename: str) -> Product:
        """Elimina una imagen específica de un producto."""
        product = await self._repo.get_by_id(product_id)
        if not product:
            raise ValueError("Producto no encontrado")

        target_reference = self._image.resolve_product_reference(
            product.images,
            product.image_filename,
            filename,
        )
        original_images = list(product.images)
        original_legacy = product.image_filename
        current_references = self._image.collect_product_references(
            product.images,
            product.image_filename,
        )
        updated_references = [
            reference for reference in current_references if reference != target_reference
        ]

        updated_product = await self._repo.update(
            product_id,
            {"images": updated_references, "image_filename": None},
        )
        if not updated_product:
            raise ValueError("Producto no encontrado")

        try:
            await self._image.delete_product_image(target_reference)
        except Exception as exc:
            logger.warning(
                "[product_use_cases] fallo borrando imagen | product_id=%s reference=%s exc=%s",
                product_id,
                target_reference,
                exc,
                exc_info=True,
            )
            await self._repo.update(
                product_id,
                {"images": original_images, "image_filename": original_legacy},
            )
            raise

        return updated_product

    async def search(
        self,
        params: ProductSearchParams,
        base_url: str,
    ) -> PaginatedResponse[ProductResponse]:
        """Búsqueda avanzada con resolución de slug y enriquecimiento."""
        resolved_category_id: str | None = None
        if params.category_slug:
            category = await self._category_repo.get_by_slug(params.category_slug)
            if category:
                resolved_category_id = str(category.id)
            else:
                return PaginatedResponse.build(
                    items=[],
                    total=0,
                    page=params.page,
                    limit=params.limit,
                )

        if params.category_id:
            _parse_object_id(params.category_id, "category_id")

        products, total = await self._repo.search(params, resolved_category_id)
        items = [self.build_response(product, base_url) for product in products]
        return PaginatedResponse.build(
            items=items,
            total=total,
            page=params.page,
            limit=params.limit,
        )

    async def enrich_categories(self, product: Product) -> list[CategoryResponse]:
        return await _enrich_categories(product, self._category_repo)

    async def bulk_import_from_excel(self, file_bytes: bytes) -> dict[str, int]:
        """Importa productos desde Excel con regla upsert por SKU."""
        products_data = self._excel.parse_products(file_bytes)
        created = 0
        updated = 0
        for data in products_data:
            slugs = data.pop("_category_slugs", None)
            if slugs:
                category_ids: list[PydanticObjectId] = []
                for slug in slugs:
                    category = await self._category_repo.get_by_slug(slug)
                    if category:
                        category_ids.append(PydanticObjectId(str(category.id)))
                data["category_ids"] = category_ids
            if "tags" in data:
                data["tags"] = _normalize_tags(data["tags"])[:15]
            existing = await self._repo.get_by_sku(data["sku"])
            await self._repo.upsert_by_sku(data)
            if existing:
                updated += 1
            else:
                created += 1
        return {"created": created, "updated": updated, "total": created + updated}

    async def _safe_delete_uploaded_image(self, image_url: str) -> None:
        try:
            await self._image.delete_product_image(image_url)
        except Exception as exc:
            logger.warning(
                "[product_use_cases] rollback remoto falló | image_url=%s exc=%s",
                image_url,
                exc,
                exc_info=True,
            )
