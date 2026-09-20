from __future__ import annotations

from app.domain.models.client import Client
from app.domain.schemas.client import ClientCreate, ClientUpdate
from app.infrastructure.repositories.client_repo import ClientRepository


class ClientUseCases:
    """Reglas de negocio para la gestión administrativa de clientes."""

    def __init__(self, repo: ClientRepository) -> None:
        self._repo = repo

    async def search(
        self,
        *,
        q: str | None,
        active_only: bool,
        page: int,
        limit: int,
    ) -> tuple[list[Client], int]:
        return await self._repo.search(
            q=q,
            active_only=active_only,
            page=page,
            limit=limit,
        )

    async def get_by_id(self, client_id: str) -> Client | None:
        return await self._repo.get_by_id(client_id)

    async def create(self, data: ClientCreate) -> Client:
        client_data = data.model_dump()
        client_data["documento"] = self.normalize_documento(client_data["documento"])
        if client_data["documento"] and await self._repo.get_by_documento(client_data["documento"]):
            raise ValueError("Ya existe un cliente con ese documento")
        return await self._repo.create(client_data)

    async def update(self, client_id: str, data: ClientUpdate) -> Client | None:
        existing = await self._repo.get_by_id(client_id)
        if not existing:
            return None

        update_data = data.model_dump(exclude_unset=True)
        if "documento" in update_data:
            update_data["documento"] = self.normalize_documento(update_data["documento"] or "")
            if update_data["documento"]:
                duplicate = await self._repo.get_by_documento(update_data["documento"])
                if duplicate and str(duplicate.id) != client_id:
                    raise ValueError("Ya existe un cliente con ese documento")
        if not update_data:
            return existing
        return await self._repo.update(client_id, update_data)

    async def delete(self, client_id: str) -> bool:
        return await self._repo.soft_delete(client_id)

    @staticmethod
    def normalize_documento(documento: str) -> str:
        return "".join(documento.split()).upper()
