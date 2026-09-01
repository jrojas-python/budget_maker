import logging
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from settings.config import settings

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class ImageService:
    """Servicio para validación, guardado y borrado de imágenes de productos."""

    def _upload_path(self) -> Path:
        return Path(settings.upload_dir)

    async def validate_image(self, file: UploadFile) -> bytes:
        """Valida tipo y tamaño. Retorna los bytes leídos si es válido."""
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError(f"Tipo de archivo no permitido: {file.content_type}. Permitidos: PNG, JPG, WEBP")

        if file.filename:
            ext = Path(file.filename).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise ValueError(f"Extensión no permitida: {ext}")

        max_bytes = settings.max_image_size_mb * 1024 * 1024
        content = await file.read()
        if len(content) > max_bytes:
            raise ValueError(f"Imagen excede el límite de {settings.max_image_size_mb}MB")

        return content

    def save_image(self, content: bytes, product_id: str, original_filename: str) -> str:
        """Guarda la imagen en disco y retorna el nombre del archivo."""
        ext = Path(original_filename).suffix.lower() if original_filename else ".jpg"
        filename = f"{product_id}_{uuid4().hex[:8]}{ext}"
        filepath = self._upload_path() / filename
        filepath.write_bytes(content)
        logger.info("Imagen guardada: %s", filename)
        return filename

    def delete_image(self, filename: str) -> None:
        """Elimina un archivo de imagen del disco."""
        filepath = self._upload_path() / filename
        if filepath.exists():
            filepath.unlink()
            logger.info("Imagen eliminada: %s", filename)
