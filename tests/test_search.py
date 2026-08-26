import pytest
from httpx import AsyncClient


async def _seed_products(client: AsyncClient, auth_headers: dict):
    """Crea productos de prueba para búsquedas."""
    products = [
        {"name": "Cemento Portland", "sku": "CEM-001", "cost": 25.0, "unit": "bolsa"},
        {"name": "Arena Fina", "sku": "ARE-001", "cost": 15.0, "unit": "m3"},
        {"name": "Cemento Blanco", "sku": "CEM-002", "cost": 35.0, "unit": "bolsa"},
        {"name": "Ladrillo Rojo", "sku": "LAD-001", "cost": 0.50, "unit": "unidad"},
        {"name": "Piedra Chancada", "sku": "PIE-001", "cost": 20.0, "unit": "m3"},
    ]
    for p in products:
        await client.post("/api/v1/products/", json=p, headers=auth_headers)


@pytest.mark.asyncio
async def test_search_text(client: AsyncClient, auth_headers: dict):
    await _seed_products(client, auth_headers)
    res = await client.get("/api/v1/products/search", params={"q": "cemento"})
    assert res.status_code == 200
    data = res.json()
    items = data if isinstance(data, list) else data.get("items", data)
    assert len(items) >= 2
    names = [p["name"].lower() for p in items]
    assert all("cemento" in n for n in names)


@pytest.mark.asyncio
async def test_search_no_results(client: AsyncClient, auth_headers: dict):
    await _seed_products(client, auth_headers)
    res = await client.get("/api/v1/products/search", params={"q": "xyznoexiste"})
    assert res.status_code == 200
    data = res.json()
    items = data if isinstance(data, list) else data.get("items", data)
    assert len(items) == 0


@pytest.mark.asyncio
async def test_search_price_range(client: AsyncClient, auth_headers: dict):
    await _seed_products(client, auth_headers)
    res = await client.get("/api/v1/products/search", params={
        "q": "cemento", "min_price": 30, "max_price": 40,
    })
    assert res.status_code == 200
    data = res.json()
    items = data if isinstance(data, list) else data.get("items", data)
    assert all(30 <= p["cost"] <= 40 for p in items)
