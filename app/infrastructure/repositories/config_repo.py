import logging

from app.domain.models.global_config import GlobalConfig

logger = logging.getLogger(__name__)

ConfigValue = float | str | int | bool

_LEGACY_TAX_KEY = "porcentaje_impuesto"
_LEGACY_TTL_KEY = "tiempo_expiracion_link_minutos"
_KEY_ALIASES = {
    _LEGACY_TAX_KEY: "tax_rate",
    _LEGACY_TTL_KEY: "link_ttl_minutes",
}


class ConfigRepository:
    """Repositorio para configuración global tipada con compatibilidad legacy."""

    async def get_global_config(self) -> GlobalConfig | None:
        return await GlobalConfig.find_one(GlobalConfig.singleton_key == "global")

    async def get_effective_global_config(self) -> GlobalConfig:
        config = await self.get_global_config()
        if config:
            return config

        legacy_values = await self._load_legacy_business_values()
        missing = [key for key in ("tax_rate", "link_ttl_minutes") if key not in legacy_values]
        if missing:
            raise ValueError(f"Configuración global incompleta. Faltan valores críticos: {', '.join(missing)}")

        show_photos = legacy_values.get("show_product_photos_in_pdf", True)
        return GlobalConfig(
            tax_rate=legacy_values["tax_rate"],
            link_ttl_minutes=legacy_values["link_ttl_minutes"],
            show_product_photos_in_pdf=bool(show_photos),
        )

    async def ensure_global_config(self) -> GlobalConfig:
        config = await self.get_global_config()
        if config:
            return config

        try:
            fallback = await self.get_effective_global_config()
        except ValueError:
            fallback = GlobalConfig()

        await fallback.insert()
        logger.info("Configuración global tipada inicializada")
        return fallback

    async def get_all(self) -> list[dict[str, ConfigValue | str]]:
        config = await self.get_global_config()
        entries: list[dict[str, ConfigValue | str]] = []
        if config:
            entries.extend(self._entries_from_typed_config(config))
            return entries

        legacy_entries = await self._load_legacy_entries()
        return legacy_entries

    async def get_by_key(self, key: str) -> dict[str, ConfigValue | str] | None:
        config = await self.get_global_config()
        if config:
            return self._entry_from_typed_config(config, key)

        legacy = await self._get_legacy_by_key(key)
        if not legacy:
            return None
        return {
            "key": legacy["key"],
            "value": legacy["value"],
            "description": str(legacy.get("description", "")),
        }

    async def set_value(self, key: str, value: ConfigValue, description: str = "") -> dict[str, ConfigValue | str]:
        config = await self.ensure_global_config()

        normalized_key = _KEY_ALIASES.get(key, key)
        if normalized_key == "tax_rate":
            config.tax_rate = float(value)
        elif normalized_key == "link_ttl_minutes":
            config.link_ttl_minutes = int(value)
        elif normalized_key == "show_product_photos_in_pdf":
            config.show_product_photos_in_pdf = _coerce_bool(value)
        else:
            config.extra_settings[normalized_key] = value

        if description:
            config.descriptions[normalized_key] = description
        elif normalized_key not in config.descriptions:
            config.descriptions[normalized_key] = ""

        await config.save()
        logger.info("Config actualizada: %s = %s", key, value)

        entry = self._entry_from_typed_config(config, key)
        if not entry:
            raise ValueError(f"No se pudo persistir la configuración para la clave '{key}'")
        return entry

    async def update_global_config(
        self,
        tax_rate: float,
        link_ttl_minutes: int,
        show_product_photos_in_pdf: bool,
    ) -> GlobalConfig:
        config = await self.ensure_global_config()
        config.tax_rate = tax_rate
        config.link_ttl_minutes = link_ttl_minutes
        config.show_product_photos_in_pdf = show_product_photos_in_pdf
        await config.save()
        return config

    async def get_payment_methods(self) -> list[str]:
        config = await self.ensure_global_config()
        methods, changed = _normalize_payment_methods(config.payment_methods)
        if changed:
            config.payment_methods = methods
            await config.save()
        return methods

    async def add_payment_method(self, name: str) -> list[str]:
        config = await self.ensure_global_config()
        methods, changed = _normalize_payment_methods(config.payment_methods)
        normalized_name = _normalize_payment_method(name)
        if any(existing.casefold() == normalized_name.casefold() for existing in methods):
            raise ValueError("El método de pago ya existe")

        methods.append(normalized_name)
        config.payment_methods = methods
        await config.save()
        if changed:
            logger.info("Métodos de pago normalizados durante alta de '%s'", normalized_name)
        return methods

    async def remove_payment_method(self, name: str) -> list[str]:
        config = await self.ensure_global_config()
        methods, changed = _normalize_payment_methods(config.payment_methods)
        normalized_name = _normalize_payment_method(name)

        index_to_remove = -1
        for index, existing in enumerate(methods):
            if existing.casefold() == normalized_name.casefold():
                index_to_remove = index
                break
        if index_to_remove < 0:
            raise KeyError("El método de pago no existe")

        methods.pop(index_to_remove)
        config.payment_methods = methods
        await config.save()
        if changed:
            logger.info("Métodos de pago normalizados durante baja de '%s'", normalized_name)
        return methods

    def _entries_from_typed_config(self, config: GlobalConfig) -> list[dict[str, ConfigValue | str]]:
        entries: list[dict[str, ConfigValue | str]] = [
            {
                "key": "show_product_photos_in_pdf",
                "value": config.show_product_photos_in_pdf,
                "description": self._description(config, "show_product_photos_in_pdf"),
            },
            {"key": _LEGACY_TAX_KEY, "value": config.tax_rate, "description": self._description(config, "tax_rate")},
            {
                "key": _LEGACY_TTL_KEY,
                "value": config.link_ttl_minutes,
                "description": self._description(config, "link_ttl_minutes"),
            },
        ]
        for key, value in config.extra_settings.items():
            entries.append({"key": key, "value": value, "description": self._description(config, key)})
        return entries

    def _entry_from_typed_config(self, config: GlobalConfig, key: str) -> dict[str, ConfigValue | str] | None:
        normalized_key = _KEY_ALIASES.get(key, key)
        if normalized_key == "tax_rate":
            value: ConfigValue = config.tax_rate
        elif normalized_key == "link_ttl_minutes":
            value = config.link_ttl_minutes
        elif normalized_key == "show_product_photos_in_pdf":
            value = config.show_product_photos_in_pdf
        else:
            if normalized_key not in config.extra_settings:
                return None
            value = config.extra_settings[normalized_key]

        return {
            "key": key,
            "value": value,
            "description": self._description(config, normalized_key),
        }

    async def _load_legacy_business_values(self) -> dict[str, ConfigValue]:
        collection = GlobalConfig.get_motor_collection()
        docs = await collection.find({"key": {"$in": [_LEGACY_TAX_KEY, _LEGACY_TTL_KEY, "show_product_photos_in_pdf"]}}).to_list(length=20)
        values: dict[str, ConfigValue] = {}
        for doc in docs:
            key = str(doc.get("key", "")).strip()
            value = doc.get("value")
            if key == _LEGACY_TAX_KEY:
                try:
                    values["tax_rate"] = float(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError("Valor inválido para porcentaje_impuesto en datos legacy") from exc
            elif key == _LEGACY_TTL_KEY:
                try:
                    values["link_ttl_minutes"] = int(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError("Valor inválido para tiempo_expiracion_link_minutos en datos legacy") from exc
            elif key == "show_product_photos_in_pdf":
                values["show_product_photos_in_pdf"] = _coerce_bool(value)
        return values

    async def _load_legacy_entries(self) -> list[dict[str, ConfigValue | str]]:
        collection = GlobalConfig.get_motor_collection()
        docs = await collection.find({"key": {"$exists": True}}).to_list(length=200)
        entries: list[dict[str, ConfigValue | str]] = []
        for doc in docs:
            key = doc.get("key")
            if not key:
                continue
            entries.append(
                {
                    "key": str(key),
                    "value": doc.get("value"),
                    "description": str(doc.get("description", "")),
                }
            )
        return entries

    async def _get_legacy_by_key(self, key: str) -> dict[str, ConfigValue | str] | None:
        collection = GlobalConfig.get_motor_collection()
        return await collection.find_one({"key": key})

    def _description(self, config: GlobalConfig, key: str) -> str:
        return config.descriptions.get(key, "")


def _coerce_bool(value: ConfigValue) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    raise ValueError("Valor inválido para show_product_photos_in_pdf")


def _normalize_payment_methods(methods: list[str]) -> tuple[list[str], bool]:
    unique_methods: list[str] = []
    seen: set[str] = set()
    changed = False
    for method in methods:
        normalized_method = _normalize_payment_method(method)
        key = normalized_method.casefold()
        if key in seen:
            changed = True
            continue
        seen.add(key)
        unique_methods.append(normalized_method)
        if normalized_method != method:
            changed = True
    return unique_methods, changed


def _normalize_payment_method(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError("El método de pago debe ser texto")
    normalized = name.strip()
    if not normalized:
        raise ValueError("El método de pago no puede estar vacío")
    return normalized
