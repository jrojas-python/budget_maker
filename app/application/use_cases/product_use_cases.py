from beanie import PydanticObjectId

from app.domain.models.product import Product
from app.domain.schemas.category import CategoryResponse
from app.domain.schemas.product import ProductColorsUpdate, ProductCreate, ProductResponse, ProductUpdate, ProductColorSchema
from app.domain.schemas.search import PaginatedResponse, ProductSearchParams
from app.infrastructure.repositories.category_repo import CategoryRepository
from app.infrastructure.repositories.product_repo import ProductRepository
from app.infrastructure.services.excel_service import ExcelService
from app.infrastructure.services.image_service import ImageService


def _build_image_url(product: Product, base_url: str) -> str | None:
    if not product.image_filename:
        return None
    return f"{base_url}uploads/products/{product.image_filename}"


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
        image_url=_build_image_url(product, base_url),
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
            dump["category_ids"] = [PydanticObjectId(cid) for cid in dump["category_ids"]]
        return await self._repo.create(dump)

    async def update(self, product_id: str, data: ProductUpdate) -> Product | None:
        update_data = data.model_dump(exclude_none=True)
        if "category_ids" in update_data:
            update_data["category_ids"] = [PydanticObjectId(cid) for cid in update_data["category_ids"]]
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
        """Elimina producto y su imagen del disco (cascade)."""
        product = await self._repo.get_by_id(product_id)
        if not product:
            return False
        if product.image_filename:
            self._image.delete_image(product.image_filename)
        await product.delete()
        return True

    async def upload_image(self, product_id: str, content: bytes, original_filename: str) -> Product:
        """Sube o reemplaza la imagen de un producto."""
        product = await self._repo.get_by_id(product_id)
        if not product:
            raise ValueError("Producto no encontrado")
        if product.image_filename:
            self._image.delete_image(product.image_filename)
        filename = self._image.save_image(content, product_id, original_filename)
        await product.set({"image_filename": filename})
        return product

    async def delete_image(self, product_id: str) -> Product:
        """Elimina la imagen de un producto."""
        product = await self._repo.get_by_id(product_id)
        if not product:
            raise ValueError("Producto no encontrado")
        if product.image_filename:
            self._image.delete_image(product.image_filename)
            await product.set({"image_filename": None})
        return product

    async def search(self, params: ProductSearchParams, base_url: str) -> PaginatedResponse[ProductResponse]:
        """Búsqueda avanzada con resolución de slug y enriquecimiento."""
        resolved_cat_id: str | None = None
        if params.category_slug:
            cat = await self._category_repo.get_by_slug(params.category_slug)
            if cat:
                resolved_cat_id = str(cat.id)
            else:
                return PaginatedResponse.build(items=[], total=0, page=params.page, limit=params.limit)

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
            existing = await self._repo.get_by_sku(data["sku"])
            await self._repo.upsert_by_sku(data)
            if existing:
                updated += 1
            else:
                created += 1
        return {"created": created, "updated": updated, "total": created + updated}
