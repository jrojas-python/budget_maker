import logging

from app.domain.models.user import User
from app.domain.schemas.user import LoginRequest
from app.infrastructure.repositories.user_repo import UserRepository
from app.infrastructure.services.auth_service import (
    create_access_token,
    hash_password,
    verify_password,
)
from settings.config import settings

logger = logging.getLogger(__name__)


class AuthUseCases:
    """Casos de uso de autenticación."""

    def __init__(self, user_repo: UserRepository) -> None:
        self._repo = user_repo

    async def login(self, data: LoginRequest) -> str | None:
        """Verifica credenciales y retorna access token, o None si fallan."""
        user = await self._repo.get_by_username(data.username)
        if not user or not verify_password(data.password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        return create_access_token({"sub": str(user.id)})

    async def seed_superadmin(self) -> None:
        """Crea el usuario superadmin si no existe."""
        existing = await self._repo.get_by_username(settings.default_admin_username)
        if existing:
            return
        await self._repo.create({
            "username": settings.default_admin_username,
            "email": settings.default_admin_email,
            "hashed_password": hash_password(settings.default_admin_password),
        })
        logger.info("Superadmin creado: %s", settings.default_admin_username)
