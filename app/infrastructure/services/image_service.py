from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from fastapi import UploadFile

from app.infrastructure.services.supabase_storage_service import (
    StorageServiceProtocol,
    SupabaseStorageService,
)
from settings.config import Settings, settings

logger = logging.getLogger(__name__)

ALLOWED_PRODUCT_CONTENT_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})
ALLOWED_PRODUCT_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})
_ALLOWED_BRANDING_IMAGE_TYPES = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/webp",
        "image/svg+xml",
        "image/x-icon",
        "image/vnd.microsoft.icon",
    }
)
_ALLOWED_LOGO_TYPES = frozenset({"image/png", "image/jpeg", "image/jpg"})
_ALLOWED_BRANDING_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico"})
_CONTENT_TYPE_EXTENSION_MAP = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
}


class ImageValidationError(ValueError):
    """Señala errores de validación de formato o tamaño en uploads."""

    def __init__(self, detail: str, status_code: int) -> None:
        super().__init__(detail)
        self.status_code = status_code


class ImageReferenceError(ValueError):
    """Señala referencias de imagen ambiguas, ausentes o inválidas."""

    def __init__(self, detail: str, status_code: int) -> None:
        super().__init__(detail)
        self.status_code = status_code


@dataclass(frozen=True)
class ValidatedImageUpload:
    """Representa un upload validado y listo para persistirse."""

    filename: str
    content: bytes
    content_type: str


class ImageService:
    """Fachada para validar, resolver y borrar imágenes con compatibilidad legacy."""

    def __init__(
        self,
        storage_service: StorageServiceProtocol | None = None,
        app_settings: Settings | None = None,
    ) -> None:
        self._settings = app_settings or settings
        self._storage = storage_service or SupabaseStorageService(self._settings)

    async def upload_product_image(self, product_id: str, file: UploadFile) -> str:
        """Valida y sube una imagen de producto al bucket configurado."""
        upload = await self.validate_product_image(file)
        return await self._storage.upload_product_image(
            content=upload.content,
            product_id=product_id,
            original_filename=upload.filename,
            content_type=upload.content_type,
        )

    async def upload_branding_image(self, key: str, file: UploadFile) -> str:
        """Valida y sube un asset de branding al bucket configurado."""
        upload = await self.validate_branding_image(key, file)
        return await self._storage.upload_branding_asset(
            key=key,
            content=upload.content,
            original_filename=upload.filename,
            content_type=upload.content_type,
        )

    async def delete_product_image(
        self,
        reference: str,
        product_id: str | None = None,
    ) -> None:
        """Elimina una referencia de producto en Storage o en disco legacy."""
        normalized_reference = reference.strip()
        if self._is_http_url(normalized_reference):
            if not self._storage.is_product_public_url(normalized_reference):
                raise ImageReferenceError(
                    "La imagen remota no pertenece al Storage configurado.",
                    422,
                )
            await self._storage.delete_product_image(
                normalized_reference,
                expected_product_id=product_id,
            )
            return

        self._delete_legacy_asset(normalized_reference, Path(self._settings.upload_dir), "producto")

    async def delete_branding_image(
        self,
        reference: str,
        key: str | None = None,
    ) -> None:
        """Elimina una referencia de branding en Storage o en disco legacy."""
        normalized_reference = reference.strip()
        if self._is_http_url(normalized_reference):
            if not self._storage.is_branding_public_url(normalized_reference):
                raise ImageReferenceError(
                    "El branding remoto no pertenece al Storage configurado.",
                    422,
                )
            await self._storage.delete_branding_asset(
                normalized_reference,
                expected_key=key,
            )
            return

        self._delete_legacy_asset(normalized_reference, Path(self._settings.branding_dir), "branding")

    def is_product_public_url(self, reference: str) -> bool:
        """Indica si una URL pertenece al bucket público de productos."""
        return self._storage.is_product_public_url(reference)

    def is_branding_public_url(self, reference: str) -> bool:
        """Indica si una URL pertenece al prefijo público de branding."""
        return self._storage.is_branding_public_url(reference)

    def is_managed_branding_reference(self, key: str, reference: str) -> bool:
        """Indica si una referencia de branding pertenece a la clave esperada."""
        normalized_reference = reference.strip()
        if not normalized_reference:
            return False
        basename = self.get_reference_basename(normalized_reference)
        if self._is_http_url(normalized_reference):
            key_matches = basename.startswith(f"{key}-") or basename.startswith(f"{key}.")
            return key_matches and self._storage.is_branding_public_url(normalized_reference)
        return (
            normalized_reference.startswith("/uploads/branding/")
            or Path(normalized_reference).parent in {Path("."), Path(self._settings.branding_dir)}
        )

    def legacy_product_path(self, reference: str) -> Path:
        """Resuelve una referencia legacy dentro del directorio de productos."""
        return Path(self._settings.upload_dir) / self.get_reference_basename(reference)

    def legacy_branding_path(self, reference: str) -> Path:
        """Resuelve una referencia legacy dentro del directorio de branding."""
        return Path(self._settings.branding_dir) / self.get_reference_basename(reference)

    async def validate_product_image(self, file: UploadFile) -> ValidatedImageUpload:
        """Valida un upload de producto con límites de formato y tamaño."""
        return await self._validate_upload(
            file=file,
            allowed_types=ALLOWED_PRODUCT_CONTENT_TYPES,
            allowed_extensions=ALLOWED_PRODUCT_EXTENSIONS,
            invalid_type_status_code=400,
            invalid_type_detail=(
                "Tipo de archivo no permitido: "
                f"{file.content_type}. Permitidos: PNG, JPG, WEBP"
            ),
        )

    async def validate_branding_image(self, key: str, file: UploadFile) -> ValidatedImageUpload:
        """Valida un upload de branding según el tipo de asset solicitado."""
        if key == "site_logo":
            return await self._validate_upload(
                file=file,
                allowed_types=_ALLOWED_LOGO_TYPES,
                allowed_extensions=frozenset({".png", ".jpg", ".jpeg"}),
                invalid_type_status_code=400,
                invalid_type_detail="Formato de logo inválido. Usar PNG o JPG",
            )

        return await self._validate_upload(
            file=file,
            allowed_types=_ALLOWED_BRANDING_IMAGE_TYPES,
            allowed_extensions=_ALLOWED_BRANDING_EXTENSIONS,
            invalid_type_status_code=422,
            invalid_type_detail="Formato no soportado. Usar PNG, JPEG, WebP, SVG o ICO",
        )

    def build_product_image_urls(
        self,
        images: list[str],
        legacy_image_filename: str | None,
        base_url: str,
    ) -> list[str]:
        """Convierte referencias almacenadas en URLs consumibles por frontend."""
        root_url = base_url.rstrip("/")
        urls: list[str] = []
        for reference in self.collect_product_references(images, legacy_image_filename):
            if self._is_http_url(reference):
                if self._storage.is_product_public_url(reference):
                    urls.append(reference)
                continue
            if reference.startswith("/uploads/products/"):
                urls.append(f"{root_url}{reference}")
                continue
            filename = self.get_reference_basename(reference)
            urls.append(f"{root_url}/uploads/products/{quote(filename)}")
        return urls

    def collect_product_references(
        self,
        images: list[str],
        legacy_image_filename: str | None,
    ) -> list[str]:
        """Combina referencias nuevas y legacy sin duplicados."""
        references: list[str] = []
        for candidate in [*images, legacy_image_filename or ""]:
            normalized = str(candidate or "").strip()
            if normalized and normalized not in references:
                references.append(normalized)
        return references

    def resolve_product_reference(
        self,
        images: list[str],
        legacy_image_filename: str | None,
        requested_filename: str,
    ) -> str:
        """Resuelve el filename del endpoint a la referencia exacta persistida."""
        normalized_request = requested_filename.strip()
        if not normalized_request:
            raise ImageReferenceError("Imagen no encontrada", 404)

        references = self.collect_product_references(images, legacy_image_filename)
        exact_matches = [reference for reference in references if reference == normalized_request]
        if len(exact_matches) == 1:
            return exact_matches[0]
        if len(exact_matches) > 1:
            raise ImageReferenceError("La imagen solicitada es ambigua", 422)

        basename_matches = [
            reference
            for reference in references
            if self.get_reference_basename(reference) == normalized_request
        ]
        if not basename_matches:
            raise ImageReferenceError("Imagen no encontrada", 404)
        if len(basename_matches) > 1:
            raise ImageReferenceError("La imagen solicitada es ambigua", 422)
        return basename_matches[0]

    def get_reference_basename(self, reference: str) -> str:
        """Obtiene el basename de una referencia local o URL pública."""
        value = reference.strip()
        if self._is_http_url(value):
            return Path(unquote(urlsplit(value).path)).name
        return Path(value).name

    async def _validate_upload(
        self,
        *,
        file: UploadFile,
        allowed_types: frozenset[str],
        allowed_extensions: frozenset[str],
        invalid_type_status_code: int,
        invalid_type_detail: str,
    ) -> ValidatedImageUpload:
        content_type = (file.content_type or "").lower()
        if content_type not in allowed_types:
            raise ImageValidationError(invalid_type_detail, invalid_type_status_code)

        extension = Path(file.filename or "").suffix.lower()
        if not extension:
            extension = _CONTENT_TYPE_EXTENSION_MAP.get(content_type, "")
        if extension not in allowed_extensions:
            raise ImageValidationError(
                f"Extensión no permitida: {extension or 'sin extensión'}",
                invalid_type_status_code,
            )

        max_bytes = self._settings.max_image_size_mb * 1024 * 1024
        chunks: list[bytes] = []
        total_bytes = 0
        while chunk := await file.read(64 * 1024):
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                raise ImageValidationError(
                    f"Archivo excede {self._settings.max_image_size_mb}MB",
                    422,
                )
            chunks.append(chunk)
        content = b"".join(chunks)
        if not content:
            raise ImageValidationError("El archivo de imagen está vacío", 422)

        filename = file.filename or f"image{extension}"
        return ValidatedImageUpload(
            filename=filename,
            content=content,
            content_type=content_type,
        )

    def _delete_legacy_asset(self, reference: str, base_directory: Path, asset_kind: str) -> None:
        basename = self.get_reference_basename(reference)
        if not basename or basename in {".", ".."}:
            raise ImageReferenceError(f"Referencia de {asset_kind} inválida", 422)

        file_path = base_directory / basename
        if file_path.exists():
            file_path.unlink()
            logger.info(
                "[image_service] archivo legacy eliminado | tipo=%s path=%s",
                asset_kind,
                file_path,
            )

    def _is_http_url(self, value: str) -> bool:
        try:
            parsed = urlsplit(value)
        except ValueError:
            return False
        return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)
