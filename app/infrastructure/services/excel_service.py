import logging
from io import BytesIO

from openpyxl import load_workbook

logger = logging.getLogger(__name__)

EXPECTED_COLUMNS = {"nombre", "sku", "costo", "unidad", "moneda"}
COLUMN_MAP = {
    "nombre": "name",
    "sku": "sku",
    "costo": "cost",
    "unidad": "unit",
    "moneda": "currency",
}


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
                products.append(row_dict)

        logger.info("Excel parseado: %d productos encontrados", len(products))
        wb.close()
        return products
