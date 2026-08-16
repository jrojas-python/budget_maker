from app.domain.models.product import Product
from app.domain.schemas.product import ProductCreate, ProductUpdate
from app.infrastructure.repositories.product_repo import ProductRepository
from app.infrastructure.services.excel_service import ExcelService


class ProductUseCases:
    """Casos de uso para gestión de productos."""

    def __init__(self, repo: ProductRepository, excel_service: ExcelService) -> None:
        self._repo = repo
        self._excel = excel_service

    async def list_all(self) -> list[Product]:
        return await self._repo.get_all()

    async def get_by_id(self, product_id: str) -> Product | None:
        return await self._repo.get_by_id(product_id)

    async def create(self, data: ProductCreate) -> Product:
        return await self._repo.create(data.model_dump())

    async def update(self, product_id: str, data: ProductUpdate) -> Product | None:
        update_data = data.model_dump(exclude_none=True)
        if not update_data:
            return await self._repo.get_by_id(product_id)
        return await self._repo.update(product_id, update_data)

    async def delete(self, product_id: str) -> bool:
        return await self._repo.delete(product_id)

    async def bulk_import_from_excel(self, file_bytes: bytes) -> dict[str, int]:
        """Importa productos desde Excel con regla upsert por SKU."""
        products_data = self._excel.parse_products(file_bytes)
        created = 0
        updated = 0
        for data in products_data:
            existing = await self._repo.get_by_sku(data["sku"])
            await self._repo.upsert_by_sku(data)
            if existing:
                updated += 1
            else:
                created += 1
        return {"created": created, "updated": updated, "total": created + updated}
