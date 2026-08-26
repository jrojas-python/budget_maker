import io

import pytest
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
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_upload_image_png(client: AsyncClient, auth_headers: dict):
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
    assert res.json().get("image_url")

    # Delete image
    res = await client.delete(f"/api/v1/products/{pid}/image", headers=auth_headers)
    assert res.status_code == 200


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
