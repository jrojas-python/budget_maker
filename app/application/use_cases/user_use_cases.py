from app.domain.models.user import User
from app.domain.schemas.user import UserCreate, UserUpdate
from app.infrastructure.repositories.user_repo import UserRepository
from app.infrastructure.services.auth_service import hash_password


class UserUseCases:
    """Casos de uso para gestión de usuarios admin."""

    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def list_all(self) -> list[User]:
        return await self._repo.get_all()

    async def get_by_id(self, user_id: str) -> User | None:
        return await self._repo.get_by_id(user_id)

    async def create(self, data: UserCreate) -> User:
        """Crea un usuario validando unicidad de username y email."""
        if await self._repo.get_by_username(data.username):
            raise ValueError(f"Username ya existe: {data.username}")
        if await self._repo.get_by_email(data.email):
            raise ValueError(f"Email ya existe: {data.email}")
        return await self._repo.create({
            "username": data.username,
            "email": data.email,
            "hashed_password": hash_password(data.password),
        })

    async def update(self, user_id: str, data: UserUpdate) -> User | None:
        update_data: dict = {}
        if data.email is not None:
            existing = await self._repo.get_by_email(data.email)
            if existing and str(existing.id) != user_id:
                raise ValueError(f"Email ya existe: {data.email}")
            update_data["email"] = data.email
        if data.password is not None:
            update_data["hashed_password"] = hash_password(data.password)
        if data.is_active is not None:
            update_data["is_active"] = data.is_active
        if not update_data:
            return await self._repo.get_by_id(user_id)
        return await self._repo.update(user_id, update_data)

    async def delete(self, user_id: str) -> bool:
        return await self._repo.delete(user_id)
