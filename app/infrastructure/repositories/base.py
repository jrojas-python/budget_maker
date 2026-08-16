from abc import ABC, abstractmethod
from typing import Any

from beanie import Document


class BaseRepository(ABC):
    """Contrato base para repositorios CRUD."""

    model: type[Document]

    @abstractmethod
    async def get_all(self) -> list[Document]:
        ...

    @abstractmethod
    async def get_by_id(self, doc_id: str) -> Document | None:
        ...

    @abstractmethod
    async def create(self, data: dict[str, Any]) -> Document:
        ...

    @abstractmethod
    async def update(self, doc_id: str, data: dict[str, Any]) -> Document | None:
        ...

    @abstractmethod
    async def delete(self, doc_id: str) -> bool:
        ...
