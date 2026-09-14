from __future__ import annotations

import inspect
import logging
from pathlib import PurePosixPath
from typing import Any, Callable, Protocol
from urllib.parse import quote, unquote, urlsplit
from uuid import uuid4

from settings.config import Settings, settings

logger = logging.getLogger(__name__)
_PUBLIC_STORAGE_PREFIX = "/storage/v1/object/public"


class SupabaseStorageConfigurationError(RuntimeError):
    """Señala configuración faltante o inválida para escrituras de Storage."""


class SupabaseStorageOperationError(RuntimeError):
    """Señala fallos operativos al interactuar con Supabase Storage."""


class SupabaseStorageReferenceError(ValueError):
    """Señala referencias remotas que no pertenecen al Storage configurado."""


class StorageServiceProtocol(Protocol):
    """Contrato mínimo que la fachada de imágenes consume del backend de Storage."""

    async def upload_product_image(
        self,
        *,
        content: bytes,
        product_id: str,
        original_filename: str,
        content_type: str,
    ) -> str: ...

    async def delete_product_image(self, reference: str) -> None: ...

    async def upload_branding_asset(
        self,
        *,
        key: str,
        content: bytes,
        original_filename: str,
        content_type: str,
    ) -> str: ...

    async def delete_branding_asset(self, reference: str) -> None: ...

    def is_product_public_url(self, reference: str) -> bool: ...

    def is_branding_public_url(self, reference: str) -> bool: ...


class SupabaseStorageService:
    """Adaptador del cliente asíncrono oficial de Supabase Storage."""

    def __init__(self, app_settings: Settings | None = None) -> None:
        self._settings = app_settings or settings
        self._client: Any | None = None

    async def upload_product_image(
        self,
        *,
        content: bytes,
        product_id: str,
        original_filename: str,
        content_type: str,
    ) -> str:
        """Sube una imagen de producto y retorna su URL pública absoluta."""
        ext = _normalize_extension(original_filename)
        object_path = f"{product_id}/{uuid4().hex}{ext}"
        return await self._upload_object(
            bucket_name=self._settings.supabase_products_bucket,
            object_path=object_path,
            content=content,
            content_type=content_type,
            upsert=False,
        )

    async def delete_product_image(self, reference: str) -> None:
        """Elimina una imagen pública del bucket de productos."""
        object_path = self._extract_public_object_path(
            reference,
            bucket_name=self._settings.supabase_products_bucket,
        )
        await self._delete_object(self._settings.supabase_products_bucket, object_path)

    async def upload_branding_asset(
        self,
        *,
        key: str,
        content: bytes,
        original_filename: str,
        content_type: str,
    ) -> str:
        """Sube logo o favicon a la carpeta pública de branding."""
        ext = _normalize_extension(original_filename)
        object_path = f"{self._settings.supabase_branding_prefix}/{key}{ext}"
        return await self._upload_object(
            bucket_name=self._settings.supabase_media_bucket,
            object_path=object_path,
            content=content,
            content_type=content_type,
            upsert=True,
        )

    async def delete_branding_asset(self, reference: str) -> None:
        """Elimina un asset público del bucket de media/branding."""
        object_path = self._extract_public_object_path(
            reference,
            bucket_name=self._settings.supabase_media_bucket,
            expected_prefix=self._settings.supabase_branding_prefix,
        )
        await self._delete_object(self._settings.supabase_media_bucket, object_path)

    def is_product_public_url(self, reference: str) -> bool:
        """Valida si una URL pública pertenece al bucket configurado de productos."""
        return self._try_extract_public_object_path(
            reference,
            bucket_name=self._settings.supabase_products_bucket,
        ) is not None

    def is_branding_public_url(self, reference: str) -> bool:
        """Valida si una URL pública pertenece al bucket configurado de branding."""
        return self._try_extract_public_object_path(
            reference,
            bucket_name=self._settings.supabase_media_bucket,
            expected_prefix=self._settings.supabase_branding_prefix,
        ) is not None

    async def _upload_object(
        self,
        *,
        bucket_name: str,
        object_path: str,
        content: bytes,
        content_type: str,
        upsert: bool,
    ) -> str:
        client = await self._get_client()
        normalized_path = self._validate_object_path(object_path)
        try:
            bucket = client.storage.from_(bucket_name)
            await bucket.upload(
                normalized_path,
                content,
                {"content-type": content_type, "upsert": "true" if upsert else "false"},
            )
            public_candidate = bucket.get_public_url(normalized_path)
            if inspect.isawaitable(public_candidate):
                public_candidate = await public_candidate
            public_url = self._extract_public_url(public_candidate, bucket_name, normalized_path)
            logger.info(
                "[supabase_storage] upload completado | bucket=%s object_path=%s",
                bucket_name,
                normalized_path,
            )
            return public_url
        except Exception as exc:
            logger.warning(
                "[supabase_storage] fallo subiendo objeto | bucket=%s object_path=%s exc=%s",
                bucket_name,
                normalized_path,
                exc,
                exc_info=True,
            )
            raise SupabaseStorageOperationError(
                f"No se pudo subir el archivo a Supabase Storage ({bucket_name})."
            ) from exc

    async def _delete_object(self, bucket_name: str, object_path: str) -> None:
        client = await self._get_client()
        normalized_path = self._validate_object_path(object_path)
        try:
            await client.storage.from_(bucket_name).remove([normalized_path])
            logger.info(
                "[supabase_storage] delete completado | bucket=%s object_path=%s",
                bucket_name,
                normalized_path,
            )
        except Exception as exc:
            logger.warning(
                "[supabase_storage] fallo eliminando objeto | bucket=%s object_path=%s exc=%s",
                bucket_name,
                normalized_path,
                exc,
                exc_info=True,
            )
            raise SupabaseStorageOperationError(
                f"No se pudo eliminar el archivo de Supabase Storage ({bucket_name})."
            ) from exc

    async def _get_client(self) -> Any:
        self._ensure_write_configuration()
        if self._client is not None:
            return self._client

        factory = _load_async_client_factory()
        try:
            self._client = await factory(
                self._settings.supabase_url,
                self._settings.supabase_secret_key,
            )
        except Exception as exc:
            logger.warning(
                "[supabase_storage] fallo inicializando cliente async | exc=%s",
                exc,
                exc_info=True,
            )
            raise SupabaseStorageOperationError(
                "No se pudo inicializar el cliente asíncrono de Supabase Storage."
            ) from exc

        return self._client

    def _ensure_write_configuration(self) -> None:
        if not self._settings.supabase_url:
            raise SupabaseStorageConfigurationError(
                "Configuración incompleta de Supabase Storage. Defina SUPABASE_URL en el backend."
            )
        if not self._settings.supabase_secret_key.strip():
            raise SupabaseStorageConfigurationError(
                "Configuración incompleta de Supabase Storage. Defina SUPABASE_SECRET_KEY en el backend."
            )

    def _extract_public_object_path(
        self,
        reference: str,
        *,
        bucket_name: str,
        expected_prefix: str | None = None,
    ) -> str:
        parsed = urlsplit(reference.strip())
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise SupabaseStorageReferenceError("La referencia remota no es una URL pública válida.")

        configured = urlsplit(self._settings.supabase_url)
        if parsed.hostname.lower() != (configured.hostname or "").lower():
            raise SupabaseStorageReferenceError(
                "La referencia remota no pertenece al proyecto Supabase configurado."
            )

        normalized_path = unquote(parsed.path)
        bucket_prefix = f"{_PUBLIC_STORAGE_PREFIX}/{bucket_name}/"
        if not normalized_path.startswith(bucket_prefix):
            raise SupabaseStorageReferenceError(
                f"La referencia remota no pertenece al bucket público '{bucket_name}'."
            )

        object_path = normalized_path[len(bucket_prefix):]
        return self._validate_object_path(object_path, expected_prefix=expected_prefix)

    def _try_extract_public_object_path(
        self,
        reference: str,
        *,
        bucket_name: str,
        expected_prefix: str | None = None,
    ) -> str | None:
        try:
            return self._extract_public_object_path(
                reference,
                bucket_name=bucket_name,
                expected_prefix=expected_prefix,
            )
        except SupabaseStorageReferenceError:
            return None

    def _extract_public_url(self, candidate: Any, bucket_name: str, object_path: str) -> str:
        if isinstance(candidate, str) and candidate:
            return candidate
        if isinstance(candidate, dict):
            for key in ("publicURL", "publicUrl", "public_url"):
                value = candidate.get(key)
                if isinstance(value, str) and value:
                    return value
        for attribute in ("publicURL", "publicUrl", "public_url"):
            value = getattr(candidate, attribute, None)
            if isinstance(value, str) and value:
                return value
        return self._compose_public_url(bucket_name, object_path)

    def _compose_public_url(self, bucket_name: str, object_path: str) -> str:
        encoded_path = quote(object_path, safe="/")
        return f"{self._settings.supabase_url}{_PUBLIC_STORAGE_PREFIX}/{bucket_name}/{encoded_path}"

    def _validate_object_path(self, object_path: str, expected_prefix: str | None = None) -> str:
        normalized = object_path.strip().strip("/")
        if not normalized:
            raise SupabaseStorageReferenceError("La referencia remota no contiene un object path válido.")

        path = PurePosixPath(normalized)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise SupabaseStorageReferenceError("El object path de Storage no es válido.")

        cleaned = "/".join(path.parts)
        if expected_prefix:
            prefix = expected_prefix.strip("/")
            if cleaned != prefix and not cleaned.startswith(f"{prefix}/"):
                raise SupabaseStorageReferenceError(
                    f"La referencia remota no pertenece al prefijo '{prefix}'."
                )
        return cleaned


def _normalize_extension(original_filename: str) -> str:
    suffix = PurePosixPath(original_filename or "image.jpg").suffix.lower()
    return suffix or ".jpg"


def _load_async_client_factory() -> Callable[..., Any]:
    try:
        from supabase import acreate_client as create_async_client

        return create_async_client
    except Exception:
        pass

    try:
        from supabase import create_async_client

        return create_async_client
    except Exception:
        pass

    try:
        from supabase._async.client import create_client as create_async_client

        return create_async_client
    except Exception as exc:
        raise SupabaseStorageOperationError(
            "No se encontró el cliente asíncrono oficial de Supabase. Instale la dependencia 'supabase'."
        ) from exc
