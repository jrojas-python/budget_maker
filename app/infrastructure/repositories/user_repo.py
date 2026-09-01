import logging
from typing import Any

from beanie import PydanticObjectId

from app.domain.models.user import User
from app.infrastructure.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository):
    """Repositorio de usuarios administradores."""

    model = User

    async def get_all(self) -> list[User]:
        return await User.find_all().to_list()

    async def get_by_id(self, doc_id: str) -> User | None:
        return await User.get(PydanticObjectId(doc_id))

    async def get_by_username(self, username: str) -> User | None:
        return await User.find_one(User.username == username)

    async def get_by_email(self, email: str) -> User | None:
        return await User.find_one(User.email == email)

    async def create(self, data: dict[str, Any]) -> User:
        user = User(**data)
        await user.insert()
        logger.info("Usuario creado: %s", user.username)
        return user

    async def update(self, doc_id: str, data: dict[str, Any]) -> User | None:
        user = await self.get_by_id(doc_id)
        if not user:
            return None
        await user.set(data)
        return user

    async def delete(self, doc_id: str) -> bool:
        user = await self.get_by_id(doc_id)
        if not user:
            return False
        await user.delete()
        return True
