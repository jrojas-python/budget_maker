from __future__ import annotations

import random
import string
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.models.budget import Budget, BudgetIdentifierCollisionError, BudgetItem, ClientInfo
from app.domain.schemas.budget import BudgetCreate, BudgetItemCreate, BudgetSearchParams, BudgetUpdate
from app.infrastructure.repositories.budget_repo import BudgetRepository
from app.infrastructure.repositories.client_repo import ClientRepository
from app.infrastructure.repositories.config_repo import ConfigRepository
from app.infrastructure.repositories.product_repo import ProductRepository
from app.infrastructure.services.pdf_service import PdfService
from app.infrastructure.services.image_service import ImageService


class BudgetUseCases:
    """Casos de uso para presupuestos/cotizaciones."""

    _DEFAULT_SITE_TITLE = "BUDGET MAKER"
    _MAX_CODE_GENERATION_ATTEMPTS = 5

    def __init__(
        self,
        budget_repo: BudgetRepository,
        product_repo: ProductRepository,
        config_repo: ConfigRepository,
        client_repo: ClientRepository,
        pdf_service: PdfService,
        image_service: ImageService,
    ) -> None:
        self._budget_repo = budget_repo
        self._product_repo = product_repo
        self._config_repo = config_repo
        self._client_repo = client_repo
        self._pdf = pdf_service
        self._image = image_service

    async def create_budget(self, data: BudgetCreate) -> Budget:
        """Crea un presupuesto congelando montos como snapshot inmutable."""
        config = await self._config_repo.get_effective_global_config()
        self._validate_payment_method(data.payment_method, config.payment_methods)
        items, subtotal, tax_percent, tax_amount, total = await self._calculate_amounts(
            data.items,
            float(config.tax_rate),
        )
        client_id, client_info = await self._resolve_client_snapshot(data.client_info)
        link_ttl_minutes = int(config.link_ttl_minutes)

        budget_uuid = str(uuid4())
        now = datetime.now(timezone.utc)
        created_at = now.replace(microsecond=(now.microsecond // 1000) * 1000)
        expires_at = created_at + timedelta(minutes=link_ttl_minutes)
        code_attempts = 0

        while code_attempts < self._MAX_CODE_GENERATION_ATTEMPTS:
            budget_data = {
                "code": self._generate_code(),
                "uuid": budget_uuid,
                "client_id": client_id,
                "client_info": client_info.model_dump(),
                "items": [item.model_dump() for item in items],
                "subtotal": round(subtotal, 2),
                "tax_percent": tax_percent,
                "tax_amount": round(tax_amount, 2),
                "total": round(total, 2),
                "payment_method": data.payment_method,
                "link_ttl_minutes": link_ttl_minutes,
                "created_at": created_at,
                "expires_at": expires_at,
            }
            try:
                return await self._budget_repo.create(budget_data)
            except BudgetIdentifierCollisionError as exc:
                if exc.identifier == "uuid":
                    raise
                code_attempts += 1
                if code_attempts >= self._MAX_CODE_GENERATION_ATTEMPTS:
                    raise BudgetIdentifierCollisionError("code") from exc

        raise BudgetIdentifierCollisionError("code")

    async def get_by_uuid(self, uuid: str) -> Budget | None:
        return await self._budget_repo.get_by_uuid(uuid)

    async def search(self, params: BudgetSearchParams) -> tuple[list[Budget], int]:
        params.date_from = self._as_utc(params.date_from)
        params.date_to = self._as_utc(params.date_to)
        if params.date_from and params.date_to and params.date_from > params.date_to:
            raise ValueError("El rango de fechas es inválido")
        return await self._budget_repo.search(params, datetime.now(timezone.utc))

    async def update_budget(self, uuid: str, data: BudgetUpdate) -> Budget | None:
        budget = await self._budget_repo.get_by_uuid(uuid)
        if not budget:
            return None

        update_data: dict[str, Any] = {}
        config = None
        if data.items is not None:
            config = await self._config_repo.get_effective_global_config()
            items, subtotal, tax_percent, tax_amount, total = await self._calculate_amounts(
                data.items,
                float(config.tax_rate),
            )
            update_data.update(
                {
                    "items": [item.model_dump() for item in items],
                    "subtotal": round(subtotal, 2),
                    "tax_percent": tax_percent,
                    "tax_amount": round(tax_amount, 2),
                    "total": round(total, 2),
                }
            )

        if "payment_method" in data.model_fields_set:
            config = config or await self._config_repo.get_effective_global_config()
            self._validate_payment_method(data.payment_method, config.payment_methods)
            update_data["payment_method"] = data.payment_method

        if data.client_info is not None:
            merged_client_info = {
                **budget.client_info.model_dump(),
                **data.client_info.model_dump(exclude_unset=True),
            }
            client_id, client_info = await self._resolve_client_snapshot(
                ClientInfo(**merged_client_info),
                update_fields=data.client_info.model_fields_set,
            )
            update_data["client_id"] = client_id
            update_data["client_info"] = client_info.model_dump()

        if not update_data:
            return budget
        return await self._budget_repo.update_by_uuid(uuid, update_data)

    async def delete_budget(self, uuid: str) -> bool:
        return await self._budget_repo.delete_by_uuid(uuid)

    async def is_expired(self, budget: Budget) -> bool:
        """Verifica si el link del presupuesto ha expirado."""
        now = datetime.now(timezone.utc)
        if budget.expires_at:
            expires = (
                budget.expires_at.replace(tzinfo=timezone.utc)
                if budget.expires_at.tzinfo is None
                else budget.expires_at
            )
            return now >= expires

        minutes = int(budget.link_ttl_minutes)
        created = (
            budget.created_at.replace(tzinfo=timezone.utc)
            if budget.created_at.tzinfo is None
            else budget.created_at
        )
        elapsed = (now - created).total_seconds() / 60
        return elapsed >= minutes

    async def build_budget_render_context(self, budget: Budget, for_pdf: bool) -> dict[str, Any]:
        """Construye contexto de render para web/PDF usando configuración global."""
        config = await self._config_repo.get_effective_global_config()
        site_title = self._sanitize_site_title(
            str(config.extra_settings.get("site_title", self._DEFAULT_SITE_TITLE))
        )
        site_subtitle = str(config.extra_settings.get("site_subtitle", "")).strip()
        show_photos = bool(config.show_product_photos_in_pdf)

        logo_path = str(config.extra_settings.get("site_logo", "")).strip()
        logo_url = self._resolve_branding_asset(logo_path, for_pdf=for_pdf)

        products_by_sku = (
            await self._product_repo.get_by_skus([item.sku for item in budget.items])
            if show_photos
            else {}
        )
        budget_items: list[dict[str, Any]] = []
        for item in budget.items:
            image_url = (
                await self._resolve_product_image(
                    item.sku,
                    for_pdf=for_pdf,
                    products_by_sku=products_by_sku,
                )
                if show_photos
                else None
            )
            budget_items.append({"item": item, "image_url": image_url})

        return {
            "budget": budget,
            "budget_items": budget_items,
            "show_product_photos_in_pdf": show_photos,
            "site_title": site_title,
            "site_subtitle": site_subtitle,
            "site_logo_url": logo_url,
            "is_pdf": for_pdf,
        }

    def generate_pdf(self, html_content: str, base_url: str | None = None) -> bytes:
        return self._pdf.generate_from_html(html_content, base_url=base_url)

    async def generate_whatsapp_share_url(
        self,
        budget: Budget,
        public_budget_url: str,
        site_title: str | None = None,
    ) -> str:
        """Genera URL canónica de WhatsApp para compartir la cotización."""
        if not public_budget_url or not public_budget_url.strip():
            raise ValueError("public_budget_url requerido")

        company_name = site_title
        if company_name is None:
            config = await self._config_repo.get_effective_global_config()
            company_name = str(config.extra_settings.get("site_title", self._DEFAULT_SITE_TITLE))
        company_name = self._sanitize_site_title(company_name)

        text = "\n".join(
            [
                f"Empresa: {company_name}",
                f"Código: {budget.code}",
                f"Total: ${budget.total:.2f}",
                f"Link: {public_budget_url}",
            ]
        )
        return f"https://wa.me/?text={urllib.parse.quote(text, safe='')}"

    def _generate_code(self) -> str:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"BM-{today}-{suffix}"

    async def _calculate_amounts(
        self,
        requested_items: list[BudgetItemCreate],
        tax_percent: float,
    ) -> tuple[list[BudgetItem], float, float, float, float]:
        items: list[BudgetItem] = []
        subtotal = 0.0
        for item_req in requested_items:
            product = await self._product_repo.get_by_sku(item_req.sku)
            if not product:
                raise ValueError(f"Producto no encontrado: {item_req.sku}")
            line_total = product.cost * item_req.quantity
            color_name = None
            color_hex = None
            if product.colors:
                match = None
                if item_req.color_hex:
                    match = next(
                        (
                            color
                            for color in product.colors
                            if color.hex.upper() == item_req.color_hex.upper()
                        ),
                        None,
                    )
                selected_color = match or product.colors[0]
                color_name = selected_color.name
                color_hex = selected_color.hex
            items.append(
                BudgetItem(
                    sku=product.sku,
                    name=product.name,
                    quantity=item_req.quantity,
                    unit_cost=product.cost,
                    line_total=line_total,
                    color_name=color_name,
                    color_hex=color_hex,
                )
            )
            subtotal += line_total
        tax_amount = subtotal * (tax_percent / 100)
        return items, subtotal, tax_percent, tax_amount, subtotal + tax_amount

    async def _resolve_client_snapshot(
        self,
        client_info: ClientInfo,
        *,
        update_fields: set[str] | None = None,
    ) -> tuple[Any | None, ClientInfo]:
        snapshot_data = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in client_info.model_dump().items()
        }
        if not snapshot_data["nombres"]:
            raise ValueError("nombres es obligatorio")
        documento = "".join(snapshot_data["documento"].split()).upper()
        snapshot_data["documento"] = documento
        if not documento:
            return None, ClientInfo(**snapshot_data)

        client = await self._client_repo.upsert_by_documento(
            {
                "nombres": snapshot_data["nombres"],
                "apellidos": snapshot_data["apellidos"],
                "email": snapshot_data["email"],
                "documento": documento,
                "compania": snapshot_data["compania"],
                "direccion": snapshot_data["direccion"],
                "observaciones": snapshot_data["observaciones"],
            },
            update_fields=update_fields,
        )
        final_snapshot = ClientInfo(
            nombres=client.nombres,
            apellidos=client.apellidos,
            email=client.email,
            documento=client.documento,
            compania=client.compania,
            direccion=client.direccion,
            observaciones=client.observaciones,
            vendedor=snapshot_data["vendedor"],
        )
        return client.id, final_snapshot

    @staticmethod
    def _validate_payment_method(payment_method: str | None, active_methods: list[str]) -> None:
        if payment_method and payment_method not in active_methods:
            raise ValueError(f"Método de pago no disponible: {payment_method}")

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _resolve_branding_asset(self, value: str, for_pdf: bool) -> str | None:
        if not value:
            return None
        if self._image.is_branding_public_url(value) or value.startswith("file://"):
            return value
        if value.startswith("/uploads/branding/"):
            if not for_pdf:
                return value
            filename = Path(value).name
            file_path = self._image.legacy_branding_path(filename)
            if file_path.exists():
                return file_path.resolve().as_uri()
            return None

        file_path = Path(value)
        if file_path.exists():
            if for_pdf:
                return file_path.resolve().as_uri()
            return value
        return None

    def _sanitize_site_title(self, site_title: str) -> str:
        value = str(site_title or "").strip()
        if value:
            return value
        return self._DEFAULT_SITE_TITLE

    async def _resolve_product_image(
        self,
        sku: str,
        for_pdf: bool,
        products_by_sku: dict[str, Any] | None = None,
    ) -> str | None:
        if products_by_sku is not None:
            product = products_by_sku.get(sku)
        else:
            product = await self._product_repo.get_by_sku(sku)
        if not product:
            return None

        for reference in self._get_stored_images(product.images, product.image_filename):
            if self._image.is_product_public_url(reference):
                return reference
            if reference.startswith("/uploads/products/"):
                if not for_pdf:
                    return reference
                filename = Path(reference).name
            else:
                filename = Path(reference).name if reference else ""
                if not for_pdf and filename:
                    return f"/uploads/products/{urllib.parse.quote(filename)}"

            if not filename:
                continue
            file_path = self._image.legacy_product_path(filename)
            if file_path.exists():
                return file_path.resolve().as_uri()
        return None

    def _get_stored_images(
        self,
        images: list[str],
        legacy_image_filename: str | None,
    ) -> list[str]:
        references: list[str] = []
        for candidate in [*images, legacy_image_filename or ""]:
            normalized = str(candidate or "").strip()
            if normalized and normalized not in references:
                references.append(normalized)
        return references
