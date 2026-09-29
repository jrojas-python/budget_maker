import logging
import re
from io import BytesIO
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

EXPECTED_COLUMNS = {"nombre", "sku", "costo", "unidad", "moneda"}
OPTIONAL_COLUMNS = {"colores", "categoría", "categoria", "descripción", "descripcion", "marca", "tags"}
COLUMN_MAP = {
    "nombre": "name",
    "sku": "sku",
    "costo": "cost",
    "unidad": "unit",
    "moneda": "currency",
    "descripción": "description",
    "descripcion": "description",
    "marca": "brand",
}
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class ExcelService:
    """Parsea archivos .xlsx de productos."""

    def parse_products(self, file_bytes: bytes) -> list[dict]:
        """Lee un Excel y retorna lista de dicts con datos de productos."""
        wb = load_workbook(filename=BytesIO(file_bytes), read_only=True)
        ws = wb.active

        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []

        headers = [str(h).strip().lower() for h in rows[0] if h]
        missing = EXPECTED_COLUMNS - set(headers)
        if missing:
            raise ValueError(f"Columnas faltantes en el Excel: {missing}")

        colors_idx = headers.index("colores") if "colores" in headers else None
        cat_idx = next((headers.index(h) for h in ("categoría", "categoria") if h in headers), None)
        tags_idx = headers.index("tags") if "tags" in headers else None

        products = []
        for row in rows[1:]:
            if not any(row):
                continue
            row_dict = {}
            for i, header in enumerate(headers):
                if header in COLUMN_MAP and i < len(row):
                    row_dict[COLUMN_MAP[header]] = row[i]
            if row_dict.get("sku"):
                row_dict["cost"] = float(row_dict.get("cost", 0))
                row_dict.setdefault("description", "")
                row_dict.setdefault("brand", "")
                if colors_idx is not None and colors_idx < len(row) and row[colors_idx]:
                    row_dict["colors"] = self._parse_colors(str(row[colors_idx]))
                if cat_idx is not None and cat_idx < len(row) and row[cat_idx]:
                    row_dict["_category_slugs"] = [s.strip() for s in str(row[cat_idx]).split(",") if s.strip()]
                if tags_idx is not None and tags_idx < len(row) and row[tags_idx]:
                    row_dict["tags"] = [s.strip() for s in str(row[tags_idx]).split(",") if s.strip()]
                products.append(row_dict)

        logger.info("Excel parseado: %d productos encontrados", len(products))
        wb.close()
        return products

    @staticmethod
    def _parse_colors(raw: str) -> list[dict]:
        """Parsea 'Rojo:#FF0000,Azul:#0000FF' a lista de dicts."""
        colors = []
        for entry in raw.split(","):
            entry = entry.strip()
            if ":" not in entry:
                continue
            name, hex_val = entry.rsplit(":", 1)
            hex_val = hex_val.strip()
            if not _HEX_RE.match(hex_val):
                continue
            colors.append({"name": name.strip(), "hex": hex_val.upper()})
        return colors[:6]

    def generate_products_excel(
        self,
        products: list[Any],
        categories_map: dict[str, Any] | None = None,
    ) -> bytes:
        """Genera un archivo Excel (.xlsx) con los productos y categorías dados."""
        categories_map = categories_map or {}
        wb = Workbook()
        ws = wb.active
        ws.title = "Productos"

        headers = [
            "id",
            "nombre",
            "sku",
            "costo",
            "unidad",
            "moneda",
            "descripcion",
            "marca",
            "colores",
            "categoria",
            "categorias_nombres",
            "tags",
            "imagenes",
        ]
        ws.append(headers)

        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_alignment = Alignment(horizontal="center", vertical="center")
        thin_border = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="CBD5E1"),
            bottom=Side(style="thin", color="CBD5E1"),
        )

        ws.row_dimensions[1].height = 26
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment
            cell.border = thin_border

        for row_idx, product in enumerate(products, start=2):
            raw_colors = getattr(product, "colors", []) or []
            colors_str = ", ".join(f"{c.name}:{c.hex}" for c in raw_colors) if raw_colors else ""

            cat_ids = getattr(product, "category_ids", []) or []
            cat_slugs = [categories_map[str(cid)].slug for cid in cat_ids if str(cid) in categories_map]
            cat_names = [categories_map[str(cid)].name for cid in cat_ids if str(cid) in categories_map]

            tags = getattr(product, "tags", []) or []
            tags_str = ", ".join(tags)

            images = getattr(product, "images", []) or []
            image_fn = getattr(product, "image_filename", None)
            images_str = ", ".join(images) if images else (image_fn or "")

            row_data = [
                str(getattr(product, "id", "")),
                getattr(product, "name", ""),
                getattr(product, "sku", ""),
                float(getattr(product, "cost", 0.0)),
                getattr(product, "unit", "unidad"),
                getattr(product, "currency", "USD"),
                getattr(product, "description", "") or "",
                getattr(product, "brand", "") or "",
                colors_str,
                ", ".join(cat_slugs),
                ", ".join(cat_names),
                tags_str,
                images_str,
            ]
            ws.append(row_data)

            for col_idx in range(1, len(row_data) + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.border = thin_border
                if col_idx == 4:  # costo
                    cell.number_format = "#,##0.00"
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                elif col_idx in (1, 3, 5, 6):  # id, sku, unidad, moneda
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")

        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val = str(cell.value or "")
                if len(val) > max_len:
                    max_len = len(val)
            ws.column_dimensions[col_letter].width = max(min(max_len + 3, 50), 12)

        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.getvalue()
