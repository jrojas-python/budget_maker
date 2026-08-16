import logging

from app.domain.models.global_config import GlobalConfig

logger = logging.getLogger(__name__)


class ConfigRepository:
    """Repositorio para configuración global (clave-valor)."""

    async def get_all(self) -> list[GlobalConfig]:
        return await GlobalConfig.find_all().to_list()

    async def get_by_key(self, key: str) -> GlobalConfig | None:
        return await GlobalConfig.find_one(GlobalConfig.key == key)

    async def set_value(self, key: str, value: float | str | int, description: str = "") -> GlobalConfig:
        """Crea o actualiza una configuración por clave."""
        existing = await self.get_by_key(key)
        if existing:
            await existing.set({"value": value, "description": description or existing.description})
            return existing
        config = GlobalConfig(key=key, value=value, description=description)
        await config.insert()
        logger.info("Config creada: %s = %s", key, value)
        return config
