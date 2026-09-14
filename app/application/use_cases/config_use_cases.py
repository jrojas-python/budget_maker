from __future__ import annotations

import logging

from fastapi import UploadFile

from app.domain.models.global_config import GlobalConfig
from app.infrastructure.repositories.config_repo import ConfigRepository
from app.infrastructure.services.image_service import ImageReferenceError, ImageService

logger = logging.getLogger(__name__)

ConfigValue = float | str | int | bool


class ConfigUseCases:
    """Casos de uso para configuración global."""

    def __init__(self, repo: ConfigRepository, image_service: ImageService) -> None:
        self._repo = repo
        self._image = image_service

    async def get_all(self) -> list[dict[str, ConfigValue | str]]:
        return await self._repo.get_all()

    async def get_by_key(self, key: str) -> dict[str, ConfigValue | str] | None:
        return await self._repo.get_by_key(key)

    async def update(
        self,
        key: str,
        value: ConfigValue,
        description: str | None = None,
    ) -> dict[str, ConfigValue | str]:
        if key in {"site_logo", "site_icon"}:
            reference = str(value).strip()
            if reference and not self._image.is_managed_branding_reference(key, reference):
                raise ImageReferenceError(
                    "El branding debe gestionarse mediante los endpoints de carga.",
                    422,
                )
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
        for key, value, description in defaults:
            existing = await self._repo.get_by_key(key)
            if not existing:
                await self._repo.set_value(key, value, description)

    async def get_payment_methods(self) -> list[str]:
        return await self._repo.get_payment_methods()

    async def add_payment_method(self, name: str) -> list[str]:
        return await self._repo.add_payment_method(name)

    async def remove_payment_method(self, name: str) -> list[str]:
        return await self._repo.remove_payment_method(name)

    async def upload_branding(self, key: str, file: UploadFile) -> dict[str, ConfigValue | str]:
        """Reemplaza logo o favicon conservando el valor previo ante fallos."""
        previous = await self._repo.get_by_key(key)
        previous_value = str(previous["value"]) if previous else ""
        previous_description = str(previous["description"]) if previous else self._branding_description(key)

        new_url = await self._image.upload_branding_image(key, file)
        try:
            updated = await self._repo.set_value(key, new_url, self._branding_description(key))
        except Exception as exc:
            logger.warning(
                "[config_use_cases] fallo persistiendo branding | key=%s exc=%s",
                key,
                exc,
                exc_info=True,
            )
            await self._safe_delete_branding(new_url)
            raise

        if (
            previous_value
            and previous_value != new_url
            and self._image.is_managed_branding_reference(key, previous_value)
        ):
            try:
                await self._image.delete_branding_image(previous_value, key)
            except Exception as exc:
                logger.warning(
                    "[config_use_cases] fallo limpiando branding previo | key=%s exc=%s",
                    key,
                    exc,
                    exc_info=True,
                )
                await self._restore_previous_branding(
                    key=key,
                    previous_value=previous_value,
                    previous_description=previous_description,
                    new_url=new_url,
                )
                raise

        return updated

    async def delete_branding(self, key: str) -> dict[str, ConfigValue | str]:
        """Elimina branding remoto o legacy y vacía la configuración."""
        previous = await self._repo.get_by_key(key)
        previous_value = str(previous["value"]) if previous else ""
        previous_description = str(previous["description"]) if previous else self._branding_description(key)

        cleared = await self._repo.set_value(key, "", self._branding_description(key))
        if not previous_value:
            return cleared

        try:
            if self._image.is_managed_branding_reference(key, previous_value):
                await self._image.delete_branding_image(previous_value, key)
        except Exception as exc:
            logger.warning(
                "[config_use_cases] fallo eliminando branding | key=%s exc=%s",
                key,
                exc,
                exc_info=True,
            )
            await self._repo.set_value(key, previous_value, previous_description)
            raise

        return cleared

    async def _restore_previous_branding(
        self,
        *,
        key: str,
        previous_value: str,
        previous_description: str,
        new_url: str,
    ) -> None:
        await self._repo.set_value(key, previous_value, previous_description)
        await self._safe_delete_branding(new_url)

    async def _safe_delete_branding(self, reference: str) -> None:
        try:
            await self._image.delete_branding_image(reference)
        except Exception as exc:
            logger.warning(
                "[config_use_cases] rollback de branding falló | reference=%s exc=%s",
                reference,
                exc,
                exc_info=True,
            )

    def _branding_description(self, key: str) -> str:
        return "Logo del sitio" if key == "site_logo" else "Icono del sitio"
