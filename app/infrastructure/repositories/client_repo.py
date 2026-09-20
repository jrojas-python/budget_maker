from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from beanie import PydanticObjectId
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from app.domain.models.client import Client

logger = logging.getLogger(__name__)


class ClientRepository:
    """Persistencia de clientes con búsqueda y borrado lógico."""

    async def get_all(self) -> list[Client]:
        return await Client.find_all().to_list()

    async def get_by_id(self, client_id: str) -> Client | None:
        try:
            return await Client.get(PydanticObjectId(client_id))
        except (TypeError, ValueError):
            return None

    async def get_by_documento(
        self,
        documento: str,
        *,
        active_only: bool = False,
    ) -> Client | None:
        query: dict[str, Any] = {"documento": documento}
        if active_only:
            query["is_active"] = True
        return await Client.find_one(query)

    async def search(
        self,
        *,
        q: str | None,
        active_only: bool,
        page: int,
        limit: int,
    ) -> tuple[list[Client], int]:
        query: dict[str, Any] = {}
        if active_only:
            query["is_active"] = True
        if q:
            regex_filter = {"$regex": re.escape(q.strip()), "$options": "i"}
            query["$or"] = [
                {"nombres": regex_filter},
                {"apellidos": regex_filter},
                {"email": regex_filter},
                {"documento": regex_filter},
                {"compania": regex_filter},
            ]

        find_query = Client.find(query)
        total = await find_query.count()
        items = await (
            find_query.sort([("nombres", ASCENDING), ("apellidos", ASCENDING)])
            .skip((page - 1) * limit)
            .limit(limit)
            .to_list()
        )
        return items, total

    async def create(self, data: dict[str, Any]) -> Client:
        client = Client(**data)
        try:
            await client.insert()
        except DuplicateKeyError as exc:
            raise ValueError("Ya existe un cliente con ese documento") from exc
        logger.info("Cliente creado: %s", client.id)
        return client

    async def update(self, client_id: str, data: dict[str, Any]) -> Client | None:
        client = await self.get_by_id(client_id)
        if not client:
            return None
        data["updated_at"] = datetime.now(timezone.utc)
        try:
            await client.set(data)
        except DuplicateKeyError as exc:
            raise ValueError("Ya existe un cliente con ese documento") from exc
        return await self.get_by_id(client_id)

    async def soft_delete(self, client_id: str) -> bool:
        client = await self.get_by_id(client_id)
        if not client or not client.is_active:
            return False
        await client.set({"is_active": False, "updated_at": datetime.now(timezone.utc)})
        return True

    async def upsert_by_documento(
        self,
        data: dict[str, Any],
        *,
        update_fields: set[str] | None = None,
    ) -> Client:
        documento = str(data["documento"])
        existing = await self.get_by_documento(documento)
        if existing:
            if update_fields is None:
                update_data = {
                    key: value
                    for key, value in data.items()
                    if key != "documento" and (not isinstance(value, str) or value)
                }
            else:
                update_data = {
                    key: data[key]
                    for key in update_fields
                    if key in data and key != "documento"
                }
            if not existing.is_active:
                update_data["is_active"] = True
            if not update_data:
                return existing
            updated = await self.update(str(existing.id), update_data)
            if updated is None:
                raise RuntimeError("No se pudo actualizar el cliente")
            return updated
        return await self.create(data)
