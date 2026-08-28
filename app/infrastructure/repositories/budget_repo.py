import logging
from typing import Any

from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from app.domain.models.budget import Budget, BudgetIdentifierCollisionError
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
        try:
            await budget.insert()
        except DuplicateKeyError as exc:
            identifier = "desconocido"
            details = getattr(exc, "details", {}) or {}
            key_pattern = details.get("keyPattern") or {}
            if "code" in key_pattern:
                identifier = "code"
            elif "uuid" in key_pattern:
                identifier = "uuid"
            else:
                message = str(exc).lower()
                if " code " in message or "index: code_" in message or "uq_budget_code" in message:
                    identifier = "code"
                elif " uuid " in message or "index: uuid_" in message or "uq_budget_uuid" in message:
                    identifier = "uuid"
            raise BudgetIdentifierCollisionError(identifier) from exc
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
