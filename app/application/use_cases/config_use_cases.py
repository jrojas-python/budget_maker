from app.domain.models.global_config import GlobalConfig
from app.infrastructure.repositories.config_repo import ConfigRepository


class ConfigUseCases:
    """Casos de uso para configuración global."""

    def __init__(self, repo: ConfigRepository) -> None:
        self._repo = repo

    async def get_all(self) -> list[GlobalConfig]:
        return await self._repo.get_all()

    async def get_by_key(self, key: str) -> GlobalConfig | None:
        return await self._repo.get_by_key(key)

    async def update(self, key: str, value: float | str | int, description: str | None = None) -> GlobalConfig:
        return await self._repo.set_value(key, value, description or "")

    async def seed_defaults(self) -> None:
        """Crea valores iniciales si no existen."""
        defaults = [
            ("porcentaje_impuesto", 18, "Porcentaje de impuesto aplicado al presupuesto"),
            ("tiempo_expiracion_link_minutos", 30, "Minutos antes de que expire el link del presupuesto"),
        ]
        for key, value, desc in defaults:
            existing = await self._repo.get_by_key(key)
            if not existing:
                await self._repo.set_value(key, value, desc)
