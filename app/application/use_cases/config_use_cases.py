from app.domain.models.global_config import GlobalConfig
from app.infrastructure.repositories.config_repo import ConfigRepository

ConfigValue = float | str | int | bool


class ConfigUseCases:
    """Casos de uso para configuración global."""

    def __init__(self, repo: ConfigRepository) -> None:
        self._repo = repo

    async def get_all(self) -> list[dict[str, ConfigValue | str]]:
        return await self._repo.get_all()

    async def get_by_key(self, key: str) -> dict[str, ConfigValue | str] | None:
        return await self._repo.get_by_key(key)

    async def update(self, key: str, value: ConfigValue, description: str | None = None) -> dict[str, ConfigValue | str]:
        return await self._repo.set_value(key, value, description or "")

    async def get_global_config(self) -> GlobalConfig:
        return await self._repo.get_effective_global_config()

    async def update_global_config(
        self,
        tax_rate: float,
        link_ttl_minutes: int,
        show_product_photos_in_pdf: bool,
    ) -> GlobalConfig:
        return await self._repo.update_global_config(
            tax_rate=tax_rate,
            link_ttl_minutes=link_ttl_minutes,
            show_product_photos_in_pdf=show_product_photos_in_pdf,
        )

    async def seed_defaults(self) -> None:
        """Asegura el documento global tipado y valores auxiliares requeridos."""
        config = await self._repo.ensure_global_config()
        if "tax_rate" not in config.descriptions:
            config.descriptions["tax_rate"] = "Porcentaje de impuesto aplicado al presupuesto"
        if "link_ttl_minutes" not in config.descriptions:
            config.descriptions["link_ttl_minutes"] = "Minutos antes de que expire el link del presupuesto"
        if "show_product_photos_in_pdf" not in config.descriptions:
            config.descriptions["show_product_photos_in_pdf"] = "Define si el PDF muestra fotos de productos"
        await config.save()

        defaults = [
            ("site_title", "BUDGET MAKER", "Título principal del sitio"),
            ("site_subtitle", "Catálogo de Productos POP", "Subtítulo del sitio"),
        ]
        for key, value, desc in defaults:
            existing = await self._repo.get_by_key(key)
            if not existing:
                await self._repo.set_value(key, value, desc)
