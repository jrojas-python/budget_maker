import pytest
from httpx import AsyncClient


async def _seed_products(client: AsyncClient, auth_headers: dict):
    """Crea productos de prueba para búsquedas."""
    products = [
        {"name": "Cemento Portland", "sku": "CEM-001", "cost": 25.0, "unit": "bolsa", "tags": ["construccion", "gris"]},
        {"name": "Arena Fina", "sku": "ARE-001", "cost": 15.0, "unit": "m3", "tags": ["aridos", "construccion"]},
        {"name": "Cemento Blanco", "sku": "CEM-002", "cost": 35.0, "unit": "bolsa", "tags": ["construccion", "blanco"]},
        {"name": "Ladrillo Rojo", "sku": "LAD-001", "cost": 0.50, "unit": "unidad", "tags": ["mamposteria"]},
        {"name": "Piedra Chancada", "sku": "PIE-001", "cost": 20.0, "unit": "m3", "tags": ["aridos"]},
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


@pytest.mark.asyncio
async def test_search_partial_name(client: AsyncClient, auth_headers: dict):
    """Búsqueda parcial por subcadena en nombre."""
    await _seed_products(client, auth_headers)
    res = await client.get("/api/v1/products/search", params={"q": "cem"})
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) >= 2
    assert all("cem" in p["name"].lower() for p in items)


@pytest.mark.asyncio
async def test_search_partial_sku(client: AsyncClient, auth_headers: dict):
    """Búsqueda parcial por subcadena en SKU."""
    await _seed_products(client, auth_headers)
    res = await client.get("/api/v1/products/search", params={"q": "CEM-0"})
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) >= 2
    assert all("CEM-0" in p["sku"] for p in items)


@pytest.mark.asyncio
async def test_search_partial_tag(client: AsyncClient, auth_headers: dict):
    """Búsqueda parcial que coincide con tags."""
    await _seed_products(client, auth_headers)
    res = await client.get("/api/v1/products/search", params={"q": "construc"})
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) >= 2


@pytest.mark.asyncio
async def test_search_tags_filter_or(client: AsyncClient, auth_headers: dict):
    """Filtrado por múltiples tags con lógica OR."""
    await _seed_products(client, auth_headers)
    res = await client.get("/api/v1/products/search", params={"tags": ["mamposteria", "aridos"]})
    assert res.status_code == 200
    items = res.json()["items"]
    skus = {p["sku"] for p in items}
    assert "LAD-001" in skus
    assert "PIE-001" in skus


@pytest.mark.asyncio
async def test_search_combined_q_and_tags(client: AsyncClient, auth_headers: dict):
    """Combinación de q parcial + filtro tags (AND)."""
    await _seed_products(client, auth_headers)
    res = await client.get("/api/v1/products/search", params={"q": "cemento", "tags": ["gris"]})
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["sku"] == "CEM-001"


@pytest.mark.asyncio
async def test_search_regex_metachar_escaped(client: AsyncClient, auth_headers: dict):
    """Metacaracteres de regex se escapan sin error."""
    await _seed_products(client, auth_headers)
    res = await client.get("/api/v1/products/search", params={"q": "c++"})
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 0
