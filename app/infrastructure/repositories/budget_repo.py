import logging
import re
from datetime import datetime
from typing import Any

from beanie import PydanticObjectId
from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError

from app.domain.models.budget import Budget, BudgetIdentifierCollisionError
from app.domain.schemas.budget import BudgetSearchParams
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

    async def search(self, params: BudgetSearchParams, now: datetime) -> tuple[list[Budget], int]:
        """Lista presupuestos con filtros administrativos acumulativos."""
        query: dict[str, Any] = {}
        if params.q:
            regex_filter = {"$regex": re.escape(params.q.strip()), "$options": "i"}
            query["$or"] = [
                {"code": regex_filter},
                {"client_info.nombres": regex_filter},
                {"client_info.apellidos": regex_filter},
                {"client_info.documento": regex_filter},
                {"client_info.email": regex_filter},
                {"client_info.compania": regex_filter},
            ]
        if params.client_id:
            try:
                query["client_id"] = PydanticObjectId(params.client_id)
            except (TypeError, ValueError) as exc:
                raise ValueError("client_id inválido") from exc
        if params.date_from is not None or params.date_to is not None:
            date_filter: dict[str, datetime] = {}
            if params.date_from is not None:
                date_filter["$gte"] = params.date_from
            if params.date_to is not None:
                date_filter["$lte"] = params.date_to
            query["created_at"] = date_filter
        if params.is_expired is True:
            query["$expr"] = {"$lte": [self._effective_expiration_expression(), now]}
        elif params.is_expired is False:
            query["$expr"] = {"$gt": [self._effective_expiration_expression(), now]}

        find_query = Budget.find(query)
        total = await find_query.count()
        items = await (
            find_query.sort([("created_at", DESCENDING)])
            .skip((params.page - 1) * params.limit)
            .limit(params.limit)
            .to_list()
        )
        return items, total

    @staticmethod
    def _effective_expiration_expression() -> dict[str, Any]:
        return {
            "$ifNull": [
                "$expires_at",
                {
                    "$add": [
                        "$created_at",
                        {"$multiply": [{"$ifNull": ["$link_ttl_minutes", 30]}, 60_000]},
                    ]
                },
            ]
        }

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

    async def update_by_uuid(self, uuid: str, data: dict[str, Any]) -> Budget | None:
        budget = await self.get_by_uuid(uuid)
        if not budget:
            return None
        await budget.set(data)
        return await self.get_by_uuid(uuid)

    async def delete(self, doc_id: str) -> bool:
        budget = await self.get_by_id(doc_id)
        if not budget:
            return False
        await budget.delete()
        return True

    async def delete_by_uuid(self, uuid: str) -> bool:
        budget = await self.get_by_uuid(uuid)
        if not budget:
            return False
        await budget.delete()
        return True

    async def count_created_between(self, date_from: datetime, date_to: datetime) -> int:
        return await Budget.find(
            {"created_at": {"$gte": date_from, "$lt": date_to}}
        ).count()

    async def aggregate_daily_counts(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> list[dict[str, Any]]:
        return await Budget.aggregate(
            [
                {"$match": {"created_at": {"$gte": date_from, "$lte": date_to}}},
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": "$created_at",
                                "timezone": "UTC",
                            }
                        },
                        "count": {"$sum": 1},
                    }
                },
                {"$sort": {"_id": 1}},
            ]
        ).to_list()

    async def aggregate_client_frequency(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> list[dict[str, Any]]:
        return await Budget.aggregate(
            [
                {
                    "$match": {
                        "created_at": {"$gte": date_from, "$lte": date_to},
                        "client_id": {"$ne": None},
                    }
                },
                {"$group": {"_id": "$client_id", "count": {"$sum": 1}}},
            ]
        ).to_list()

    async def aggregate_top_products(
        self,
        date_from: datetime,
        date_to: datetime,
        limit: int,
    ) -> list[dict[str, Any]]:
        return await Budget.aggregate(
            [
                {"$match": {"created_at": {"$gte": date_from, "$lte": date_to}}},
                {"$unwind": "$items"},
                {
                    "$group": {
                        "_id": {"sku": "$items.sku", "name": "$items.name"},
                        "quantity": {"$sum": "$items.quantity"},
                        "amount": {"$sum": "$items.line_total"},
                    }
                },
                {"$sort": {"quantity": -1, "amount": -1, "_id.sku": 1}},
                {"$limit": limit},
            ]
        ).to_list()

    async def aggregate_payment_methods(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> list[dict[str, Any]]:
        return await Budget.aggregate(
            [
                {"$match": {"created_at": {"$gte": date_from, "$lte": date_to}}},
                {
                    "$group": {
                        "_id": {"$ifNull": ["$payment_method", "Sin especificar"]},
                        "count": {"$sum": 1},
                    }
                },
                {"$sort": {"count": -1, "_id": 1}},
            ]
        ).to_list()
