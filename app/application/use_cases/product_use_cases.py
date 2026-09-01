from beanie import PydanticObjectId

from app.domain.models.product import Product
from app.domain.schemas.category import CategoryResponse
from app.domain.schemas.product import ProductColorsUpdate, ProductCreate, ProductResponse, ProductUpdate, ProductColorSchema
from app.domain.schemas.search import PaginatedResponse, ProductSearchParams
from app.infrastructure.repositories.category_repo import CategoryRepository
from app.infrastructure.repositories.product_repo import ProductRepository
from app.infrastructure.services.excel_service import ExcelService
from app.infrastructure.services.image_service import ImageService


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


def _get_stored_images(product: Product) -> list[str]:
    if product.images:
        return list(product.images)
    if product.image_filename:
        return [product.image_filename]
    return []


def _build_image_urls(product: Product, base_url: str) -> list[str]:
    root_url = base_url.rstrip("/")
    return [f"{root_url}/uploads/products/{filename}" for filename in _get_stored_images(product)]


def _unique_image_filenames(product: Product) -> list[str]:
    filenames: list[str] = []
    for filename in [*_get_stored_images(product), *([product.image_filename] if product.image_filename else [])]:
        if filename not in filenames:
            filenames.append(filename)
    return filenames


async def _enrich_categories(product: Product, category_repo: CategoryRepository) -> list[CategoryResponse]:
    """Resuelve category_ids a CategoryResponse."""
    if not product.category_ids:
        return []
    cats = []
    for cid in product.category_ids:
        cat = await category_repo.get_by_id(str(cid))
        if cat:
            cats.append(CategoryResponse(id=str(cat.id), name=cat.name, slug=cat.slug, description=cat.description, is_active=cat.is_active))
    return cats


def build_product_response(product: Product, base_url: str, categories: list[CategoryResponse] | None = None) -> ProductResponse:
    return ProductResponse(
        id=str(product.id),
        name=product.name,
        sku=product.sku,
        description=product.description,
        brand=product.brand,
        cost=product.cost,
        unit=product.unit,
        currency=product.currency,
        image_urls=_build_image_urls(product, base_url),
        tags=_normalize_tags(product.tags),
        category_ids=[str(cid) for cid in product.category_ids],
        categories=categories or [],
        colors=[ProductColorSchema(name=c.name, hex=c.hex) for c in product.colors],
    )


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
        await product.set({"colors": [c.model_dump() for c in data.colors]})
        return product

    async def delete(self, product_id: str) -> bool:
        """Elimina producto y sus imágenes del disco (cascade)."""
        product = await self._repo.get_by_id(product_id)
        if not product:
            return False
        for filename in _unique_image_filenames(product):
            self._image.delete_image(filename)
        await product.delete()
        return True

    async def upload_image(self, product_id: str, content: bytes, original_filename: str) -> Product:
        """Sube una imagen a un producto respetando el límite máximo."""
        product = await self._repo.get_by_id(product_id)
        if not product:
            raise ValueError("Producto no encontrado")

        existing_images = _get_stored_images(product)
        if len(existing_images) >= 10:
            raise ValueError("El producto ya tiene el máximo de 10 imágenes")

        if not product.images and existing_images:
            await self._repo.update(product_id, {"images": existing_images})

        filename = self._image.save_image(content, product_id, original_filename)
        try:
            updated_product = await self._repo.add_image(product_id, filename)
        except Exception:
            self._image.delete_image(filename)
            raise
        if not updated_product:
            self._image.delete_image(filename)
            raise ValueError("Producto no encontrado")
        return updated_product

    async def delete_image(self, product_id: str, filename: str) -> Product:
        """Elimina una imagen específica de un producto."""
        product = await self._repo.get_by_id(product_id)
        if not product:
            raise ValueError("Producto no encontrado")

        stored_images = _get_stored_images(product)
        if filename not in stored_images:
            raise ValueError("Imagen no encontrada")

        updated_product: Product | None = product
        if product.images:
            updated_product = await self._repo.remove_image(product_id, filename)
        if product.image_filename == filename:
            updated_product = await self._repo.update(product_id, {"image_filename": None})

        if not updated_product:
            raise ValueError("Producto no encontrado")

        self._image.delete_image(filename)
        return updated_product

    async def search(self, params: ProductSearchParams, base_url: str) -> PaginatedResponse[ProductResponse]:
        """Búsqueda avanzada con resolución de slug y enriquecimiento."""
        resolved_cat_id: str | None = None
        if params.category_slug:
            cat = await self._category_repo.get_by_slug(params.category_slug)
            if cat:
                resolved_cat_id = str(cat.id)
            else:
                return PaginatedResponse.build(items=[], total=0, page=params.page, limit=params.limit)

        if params.category_id:
            _parse_object_id(params.category_id, "category_id")

        products, total = await self._repo.search(params, resolved_cat_id)
        items = [build_product_response(p, base_url) for p in products]
        return PaginatedResponse.build(items=items, total=total, page=params.page, limit=params.limit)

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
                cat_ids = []
                for slug in slugs:
                    cat = await self._category_repo.get_by_slug(slug)
                    if cat:
                        cat_ids.append(PydanticObjectId(str(cat.id)))
                data["category_ids"] = cat_ids
            if "tags" in data:
                normalized = _normalize_tags(data["tags"])
                data["tags"] = normalized[:15]
            existing = await self._repo.get_by_sku(data["sku"])
            await self._repo.upsert_by_sku(data)
            if existing:
                updated += 1
            else:
                created += 1
        return {"created": created, "updated": updated, "total": created + updated}
