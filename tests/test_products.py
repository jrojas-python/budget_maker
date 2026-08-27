import io

import pytest
from app.domain.models.product import Product
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_product_requires_auth(client: AsyncClient):
    res = await client.post("/api/v1/products/", json={
        "name": "Test", "sku": "T-001", "cost": 10.0,
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_crud_product(client: AsyncClient, auth_headers: dict):
    # Create
    res = await client.post("/api/v1/products/", json={
        "name": "Cemento Portland",
        "sku": "CEM-001",
        "cost": 25.50,
        "unit": "bolsa",
        "currency": "USD",
    }, headers=auth_headers)
    assert res.status_code == 201
    p = res.json()
    assert p["name"] == "Cemento Portland"
    assert p["sku"] == "CEM-001"
    assert p["image_urls"] == []
    assert p["tags"] == []
    pid = p["id"]

    # List
    res = await client.get("/api/v1/products/")
    assert res.status_code == 200

    # Get
    res = await client.get(f"/api/v1/products/{pid}")
    assert res.status_code == 200
    assert res.json()["sku"] == "CEM-001"

    # Update
    res = await client.put(f"/api/v1/products/{pid}", json={
        "name": "Cemento Portland Tipo I",
        "sku": "CEM-001",
        "cost": 27.00,
    }, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["cost"] == 27.00

    # Delete
    res = await client.delete(f"/api/v1/products/{pid}", headers=auth_headers)
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_create_product_normalizes_tags(client: AsyncClient, auth_headers: dict):
    res = await client.post("/api/v1/products/", json={
        "name": "Perfil Metálico",
        "sku": "TAG-001",
        "cost": 12.5,
        "tags": ["Metal", " industrial ", "METAL", "  "],
    }, headers=auth_headers)
    assert res.status_code == 201
    assert res.json()["tags"] == ["metal", "industrial"]


@pytest.mark.asyncio
async def test_create_product_rejects_more_than_fifteen_tags(client: AsyncClient, auth_headers: dict):
    res = await client.post("/api/v1/products/", json={
        "name": "Perfil Saturado",
        "sku": "TAG-002",
        "cost": 8.0,
        "tags": [f"tag-{i}" for i in range(16)],
    }, headers=auth_headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_upload_product_images_supports_multiple_files(client: AsyncClient, auth_headers: dict):
    # Create product first
    res = await client.post("/api/v1/products/", json={
        "name": "Producto Img", "sku": "IMG-001", "cost": 10.0,
    }, headers=auth_headers)
    pid = res.json()["id"]

    # Upload valid PNG (1x1 pixel)
    png_bytes = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
        b'\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
        b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    res = await client.post(
        f"/api/v1/products/{pid}/image",
        files={"file": ("test.png", io.BytesIO(png_bytes), "image/png")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    first_upload = res.json()
    assert len(first_upload["image_urls"]) == 1

    res = await client.post(
        f"/api/v1/products/{pid}/image",
        files={"file": ("second.png", io.BytesIO(png_bytes), "image/png")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert len(res.json()["image_urls"]) == 2


@pytest.mark.asyncio
async def test_upload_tenth_image_succeeds(client: AsyncClient, auth_headers: dict):
    product = Product(
        name="Producto nueve",
        sku="IMG-009",
        cost=10.0,
        images=[f"img_{i}.png" for i in range(9)],
    )
    await product.insert()

    png_bytes = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
        b'\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
        b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )

    res = await client.post(
        f"/api/v1/products/{product.id}/image",
        files={"file": ("tenth.png", io.BytesIO(png_bytes), "image/png")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert len(res.json()["image_urls"]) == 10


@pytest.mark.asyncio
async def test_upload_image_rejects_when_limit_reached(client: AsyncClient, auth_headers: dict):
    product = Product(
        name="Producto límite",
        sku="IMG-010",
        cost=10.0,
        images=[f"img_{i}.png" for i in range(10)],
    )
    await product.insert()

    png_bytes = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
        b'\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
        b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )

    res = await client.post(
        f"/api/v1/products/{product.id}/image",
        files={"file": ("overflow.png", io.BytesIO(png_bytes), "image/png")},
        headers=auth_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_upload_image_rejects_invalid_format(client: AsyncClient, auth_headers: dict):
    res = await client.post("/api/v1/products/", json={
        "name": "Producto Inválido", "sku": "IMG-011", "cost": 10.0,
    }, headers=auth_headers)
    pid = res.json()["id"]

    res = await client.post(
        f"/api/v1/products/{pid}/image",
        files={"file": ("bad.gif", io.BytesIO(b"GIF89a"), "image/gif")},
        headers=auth_headers,
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_delete_specific_image_removes_only_requested_file(client: AsyncClient, auth_headers: dict):
    res = await client.post("/api/v1/products/", json={
        "name": "Producto Eliminar", "sku": "IMG-012", "cost": 10.0,
    }, headers=auth_headers)
    pid = res.json()["id"]

    png_bytes = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
        b'\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
        b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )

    first_upload = await client.post(
        f"/api/v1/products/{pid}/image",
        files={"file": ("first.png", io.BytesIO(png_bytes), "image/png")},
        headers=auth_headers,
    )
    second_upload = await client.post(
        f"/api/v1/products/{pid}/image",
        files={"file": ("second.png", io.BytesIO(png_bytes), "image/png")},
        headers=auth_headers,
    )
    assert first_upload.status_code == 200
    assert second_upload.status_code == 200
    image_urls = second_upload.json()["image_urls"]
    filename_to_delete = image_urls[0].rsplit("/", 1)[-1]

    res = await client.delete(f"/api/v1/products/{pid}/images/{filename_to_delete}", headers=auth_headers)
    assert res.status_code == 200
    remaining_urls = res.json()["image_urls"]
    assert len(remaining_urls) == 1
    assert filename_to_delete not in remaining_urls[0]


@pytest.mark.asyncio
async def test_delete_product_image_returns_404_when_missing(client: AsyncClient, auth_headers: dict):
    res = await client.post("/api/v1/products/", json={
        "name": "Producto Sin Imagen", "sku": "IMG-013", "cost": 10.0,
    }, headers=auth_headers)
    pid = res.json()["id"]

    res = await client.delete(f"/api/v1/products/{pid}/images/no-existe.png", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_product_includes_image_urls_and_tags(client: AsyncClient, auth_headers: dict):
    res = await client.post("/api/v1/products/", json={
        "name": "Producto Respuesta",
        "sku": "RESP-001",
        "cost": 18.0,
        "tags": ["Decoración", " interior "],
    }, headers=auth_headers)
    assert res.status_code == 201
    product = res.json()

    res = await client.get(f"/api/v1/products/{product['id']}")
    assert res.status_code == 200
    body = res.json()
    assert body["image_urls"] == []
    assert body["tags"] == ["decoración", "interior"]


@pytest.mark.asyncio
async def test_get_product_uses_legacy_image_filename_fallback(client: AsyncClient):
    product = Product(
        name="Producto Legacy",
        sku="LEG-001",
        cost=20.0,
        image_filename="legacy.png",
    )
    await product.insert()

    res = await client.get(f"/api/v1/products/{product.id}")
    assert res.status_code == 200
    assert res.json()["image_urls"] == ["http://test/uploads/products/legacy.png"]


@pytest.mark.asyncio
async def test_update_preserves_existing_tags(client: AsyncClient, auth_headers: dict):
    """Actualizar un campo sin enviar tags no debe borrar tags existentes."""
    res = await client.post("/api/v1/products/", json={
        "name": "Producto Tags", "sku": "TAG-KEEP", "cost": 10.0,
        "tags": ["acero", "galvanizado"],
    }, headers=auth_headers)
    pid = res.json()["id"]

    res = await client.put(f"/api/v1/products/{pid}", json={"cost": 15.0}, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["tags"] == ["acero", "galvanizado"]


@pytest.mark.asyncio
async def test_upload_image_to_legacy_product_migrates(client: AsyncClient, auth_headers: dict):
    """Subir imagen a producto legacy migra image_filename a images."""
    product = Product(
        name="Legacy Upload", sku="LEG-UP", cost=10.0, image_filename="old.png",
    )
    await product.insert()

    png_bytes = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
        b'\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
        b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    res = await client.post(
        f"/api/v1/products/{product.id}/image",
        files={"file": ("new.png", io.BytesIO(png_bytes), "image/png")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert len(res.json()["image_urls"]) == 2


@pytest.mark.asyncio
async def test_create_product_with_colors(client: AsyncClient, auth_headers: dict):
    res = await client.post("/api/v1/products/", json={
        "name": "Pintura Latex",
        "sku": "PIN-001",
        "cost": 45.00,
        "colors": [
            {"name": "Rojo", "hex": "#FF0000"},
            {"name": "Azul", "hex": "#0000FF"},
        ],
    }, headers=auth_headers)
    assert res.status_code == 201
    p = res.json()
    assert len(p["colors"]) == 2
    assert p["colors"][0]["name"] == "Rojo"
    assert p["colors"][0]["hex"] == "#FF0000"


@pytest.mark.asyncio
async def test_update_colors_endpoint(client: AsyncClient, auth_headers: dict):
    res = await client.post("/api/v1/products/", json={
        "name": "Barniz", "sku": "BAR-001", "cost": 30.00,
    }, headers=auth_headers)
    pid = res.json()["id"]

    res = await client.put(f"/api/v1/products/{pid}/colors", json={
        "colors": [
            {"name": "Natural", "hex": "#D2B48C"},
            {"name": "Nogal", "hex": "#3B2F2F"},
            {"name": "Caoba", "hex": "#8B0000"},
        ],
    }, headers=auth_headers)
    assert res.status_code == 200
    assert len(res.json()["colors"]) == 3


@pytest.mark.asyncio
async def test_colors_max_six_validation(client: AsyncClient, auth_headers: dict):
    colors = [{"name": f"Color{i}", "hex": f"#{'%02X' % (i * 40)}0000"} for i in range(7)]
    res = await client.post("/api/v1/products/", json={
        "name": "Exceso", "sku": "EXC-001", "cost": 10.0, "colors": colors,
    }, headers=auth_headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_invalid_hex_validation(client: AsyncClient, auth_headers: dict):
    res = await client.post("/api/v1/products/", json={
        "name": "Bad Hex", "sku": "HEX-001", "cost": 10.0,
        "colors": [{"name": "Malo", "hex": "NOTHEX"}],
    }, headers=auth_headers)
    assert res.status_code == 422


def _make_excel(rows: list[list]) -> bytes:
    """Helper para crear archivos Excel en memoria."""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_import_excel_with_tags_normalizes(client: AsyncClient, auth_headers: dict):
    """Importar Excel con columna tags normaliza correctamente."""
    excel_bytes = _make_excel([
        ["nombre", "sku", "costo", "unidad", "moneda", "tags"],
        ["Tornillo Hex", "IMP-001", 5.0, "caja", "USD", "Metal, INDUSTRIAL, metal "],
        ["Tuerca M8", "IMP-002", 3.0, "bolsa", "USD", "metal, fijacion"],
    ])
    res = await client.post(
        "/api/v1/products/import",
        files={"file": ("productos.xlsx", io.BytesIO(excel_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["created"] == 2

    res = await client.get("/api/v1/products/")
    products = {p["sku"]: p for p in res.json()}
    assert products["IMP-001"]["tags"] == ["metal", "industrial"]
    assert products["IMP-002"]["tags"] == ["metal", "fijacion"]


@pytest.mark.asyncio
async def test_import_excel_upsert_rewrites_tags(client: AsyncClient, auth_headers: dict):
    """Upsert por SKU reescribe tags con valores nuevos."""
    excel1 = _make_excel([
        ["nombre", "sku", "costo", "unidad", "moneda", "tags"],
        ["Producto X", "UPS-001", 10.0, "unidad", "USD", "original, viejo"],
    ])
    await client.post(
        "/api/v1/products/import",
        files={"file": ("p.xlsx", io.BytesIO(excel1), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=auth_headers,
    )

    excel2 = _make_excel([
        ["nombre", "sku", "costo", "unidad", "moneda", "tags"],
        ["Producto X", "UPS-001", 12.0, "unidad", "USD", "nuevo, actualizado"],
    ])
    res = await client.post(
        "/api/v1/products/import",
        files={"file": ("p.xlsx", io.BytesIO(excel2), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=auth_headers,
    )
    assert res.json()["updated"] == 1

    res = await client.get("/api/v1/products/")
    products = {p["sku"]: p for p in res.json()}
    assert products["UPS-001"]["tags"] == ["nuevo", "actualizado"]


@pytest.mark.asyncio
async def test_import_excel_without_tags_column(client: AsyncClient, auth_headers: dict):
    """Excel sin columna tags no rompe la importación."""
    excel_bytes = _make_excel([
        ["nombre", "sku", "costo", "unidad", "moneda"],
        ["Producto Simple", "NOTAG-001", 7.0, "unidad", "USD"],
    ])
    res = await client.post(
        "/api/v1/products/import",
        files={"file": ("p.xlsx", io.BytesIO(excel_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["created"] == 1


@pytest.mark.asyncio
async def test_import_excel_truncates_excess_tags(client: AsyncClient, auth_headers: dict):
    """Fila con 16+ tags solo persiste los primeros 15."""
    many_tags = ", ".join([f"tag-{i}" for i in range(20)])
    excel_bytes = _make_excel([
        ["nombre", "sku", "costo", "unidad", "moneda", "tags"],
        ["Producto Exceso", "EXC-001", 5.0, "unidad", "USD", many_tags],
    ])
    res = await client.post(
        "/api/v1/products/import",
        files={"file": ("p.xlsx", io.BytesIO(excel_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=auth_headers,
    )
    assert res.status_code == 200

    res = await client.get("/api/v1/products/")
    products = {p["sku"]: p for p in res.json()}
    assert len(products["EXC-001"]["tags"]) == 15
