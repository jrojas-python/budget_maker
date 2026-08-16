import logging
from typing import Any

from beanie import PydanticObjectId

from app.domain.models.budget import Budget
from app.infrastructure.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class BudgetRepository(BaseRepository):
    """Repositorio de presupuestos."""

    model = Budget

    async def get_all(self) -> list[Budget]:
        return await Budget.find_all().to_list()

    async def get_by_id(self, doc_id: str) -> Budget | None:
        return await Budget.get(PydanticObjectId(doc_id))

    async def get_by_uuid(self, uuid: str) -> Budget | None:
        return await Budget.find_one(Budget.uuid == uuid)

    async def create(self, data: dict[str, Any]) -> Budget:
        budget = Budget(**data)
        await budget.insert()
        logger.info("Presupuesto creado: %s", budget.code)
        return budget

    async def update(self, doc_id: str, data: dict[str, Any]) -> Budget | None:
        budget = await self.get_by_id(doc_id)
        if not budget:
            return None
        await budget.set(data)
        return budget

    async def delete(self, doc_id: str) -> bool:
        budget = await self.get_by_id(doc_id)
        if not budget:
            return False
        await budget.delete()
        return True
