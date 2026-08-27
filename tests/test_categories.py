import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_category_requires_auth(client: AsyncClient):
    res = await client.post("/api/v1/categories/", json={"name": "Test"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_crud_category(client: AsyncClient, auth_headers: dict):
    # Create
    res = await client.post("/api/v1/categories/", json={
        "name": "Electrónica",
        "description": "Productos electrónicos",
    }, headers=auth_headers)
    assert res.status_code == 201
    cat = res.json()
    assert cat["name"] == "Electrónica"
    assert cat["slug"] == "electronica"
    assert cat["is_active"] is True
    cat_id = cat["id"]

    # List
    res = await client.get("/api/v1/categories/", headers=auth_headers)
    assert res.status_code == 200
    cats = res.json()
    assert len(cats) >= 1

    # Get
    res = await client.get(f"/api/v1/categories/{cat_id}", headers=auth_headers)
    assert res.status_code == 200

    # Update
    res = await client.put(f"/api/v1/categories/{cat_id}", json={
        "name": "Electrónica Pro",
        "description": "Actualizada",
    }, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["name"] == "Electrónica Pro"

    # Delete
    res = await client.delete(f"/api/v1/categories/{cat_id}", headers=auth_headers)
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_slug_auto_generated(client: AsyncClient, auth_headers: dict):
    res = await client.post("/api/v1/categories/", json={
        "name": "Materiales de Construcción",
    }, headers=auth_headers)
    assert res.status_code == 201
    assert res.json()["slug"] == "materiales-de-construccion"
