import random
import string
import urllib.parse
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.domain.models.budget import Budget, BudgetItem
from app.domain.schemas.budget import BudgetCreate
from app.infrastructure.repositories.budget_repo import BudgetRepository
from app.infrastructure.repositories.config_repo import ConfigRepository
from app.infrastructure.repositories.product_repo import ProductRepository
from app.infrastructure.services.pdf_service import PdfService


class BudgetUseCases:
    """Casos de uso para presupuestos/cotizaciones."""

    def __init__(
        self,
        budget_repo: BudgetRepository,
        product_repo: ProductRepository,
        config_repo: ConfigRepository,
        pdf_service: PdfService,
    ) -> None:
        self._budget_repo = budget_repo
        self._product_repo = product_repo
        self._config_repo = config_repo
        self._pdf = pdf_service

    async def create_budget(self, data: BudgetCreate) -> Budget:
        """Crea un presupuesto congelando montos como snapshot inmutable."""
        items: list[BudgetItem] = []
        subtotal = 0.0

        for item_req in data.items:
            product = await self._product_repo.get_by_sku(item_req.sku)
            if not product:
                raise ValueError(f"Producto no encontrado: {item_req.sku}")
            line_total = product.cost * item_req.quantity

            color_name = None
            color_hex = None
            if product.colors:
                if item_req.color_hex:
                    match = next((c for c in product.colors if c.hex.upper() == item_req.color_hex.upper()), None)
                    if match:
                        color_name, color_hex = match.name, match.hex
                    else:
                        color_name = product.colors[0].name
                        color_hex = product.colors[0].hex
                else:
                    color_name = product.colors[0].name
                    color_hex = product.colors[0].hex

            items.append(BudgetItem(
                sku=product.sku,
                name=product.name,
                quantity=item_req.quantity,
                unit_cost=product.cost,
                line_total=line_total,
                color_name=color_name,
                color_hex=color_hex,
            ))
            subtotal += line_total

        config = await self._config_repo.get_effective_global_config()

        if data.payment_method:
            if data.payment_method not in config.payment_methods:
                raise ValueError(f"Método de pago no disponible: {data.payment_method}")

        tax_percent = float(config.tax_rate)
        link_ttl_minutes = int(config.link_ttl_minutes)
        tax_amount = subtotal * (tax_percent / 100)
        total = subtotal + tax_amount

        code = self._generate_code()
        budget_uuid = str(uuid4())
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(minutes=link_ttl_minutes)

        budget_data = {
            "code": code,
            "uuid": budget_uuid,
            "client_info": data.client_info.model_dump(),
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
        return await self._budget_repo.create(budget_data)

    async def get_by_uuid(self, uuid: str) -> Budget | None:
        return await self._budget_repo.get_by_uuid(uuid)

    async def is_expired(self, budget: Budget) -> bool:
        """Verifica si el link del presupuesto ha expirado."""
        now = datetime.now(timezone.utc)
        if budget.expires_at:
            expires = budget.expires_at.replace(tzinfo=timezone.utc) if budget.expires_at.tzinfo is None else budget.expires_at
            return now >= expires
        # Fallback para presupuestos legacy sin expires_at
        minutes = int(budget.link_ttl_minutes)
        created = budget.created_at.replace(tzinfo=timezone.utc) if budget.created_at.tzinfo is None else budget.created_at
        elapsed = (now - created).total_seconds() / 60
        return elapsed >= minutes

    def generate_pdf(self, html_content: str) -> bytes:
        return self._pdf.generate_from_html(html_content)

    def generate_whatsapp_text(self, budget: Budget) -> str:
        """Genera el texto formateado para compartir por WhatsApp."""
        total_lines = len(budget.items)
        total_units = sum(item.quantity for item in budget.items)
        client_name = f"{budget.client_info.nombres} {budget.client_info.apellidos}".strip()
        fecha = budget.created_at.strftime("%d/%m/%Y")

        lines = [
            f"*COTIZACIÓN {budget.code}*",
            "BUDGET MAKER",
            f"Cliente: {client_name}",
            f"Fecha: {fecha}",
            f"*{total_lines} líneas · {total_units} unidades*",
        ]
        for item in budget.items:
            color_info = f" · {item.color_name} ({item.color_hex})" if item.color_name else ""
            lines.append(f"• {item.sku} · {item.name}{color_info} · {item.quantity}x ${item.unit_cost:.2f}")
        lines.append("*TOTALES:*")
        lines.append(f"Subtotal: ${budget.subtotal:.2f}")
        lines.append(f"Total con impuestos: ${budget.total:.2f}")

        text = "\n".join(lines)
        return f"https://wa.me/?text={urllib.parse.quote(text)}"

    def _generate_code(self) -> str:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"BM-{today}-{suffix}"
