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
        client_data["email"] = self.normalize_email(client_data.get("email") or "")
        client_data["documento"] = self.normalize_documento(client_data.get("documento") or "")
        if client_data["email"] and await self._repo.get_by_email(client_data["email"]):
            raise ValueError("Ya existe un cliente con ese correo electrónico")
        return await self._repo.create(client_data)

    async def update(self, client_id: str, data: ClientUpdate) -> Client | None:
        existing = await self._repo.get_by_id(client_id)
        if not existing:
            return None

        update_data = data.model_dump(exclude_unset=True)
        if "email" in update_data:
            update_data["email"] = self.normalize_email(update_data["email"] or "")
            if update_data["email"]:
                duplicate = await self._repo.get_by_email(update_data["email"])
                if duplicate and str(duplicate.id) != client_id:
                    raise ValueError("Ya existe un cliente con ese correo electrónico")
        if "documento" in update_data:
            update_data["documento"] = self.normalize_documento(update_data["documento"] or "")
        if not update_data:
            return existing
        return await self._repo.update(client_id, update_data)

    async def delete(self, client_id: str) -> bool:
        return await self._repo.soft_delete(client_id)

    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def normalize_documento(documento: str) -> str:
        return "".join(documento.split()).upper()

