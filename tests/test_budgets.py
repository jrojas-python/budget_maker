from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient


async def _create_product(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.post(
        "/api/v1/products/",
        json={"name": "Producto Presupuesto", "sku": "BGT-001", "cost": 100.0, "unit": "unidad"},
        headers=auth_headers,
    )
    assert res.status_code == 201


def _budget_payload() -> dict:
    return {
        "client_info": {
            "nombres": "Ana",
            "apellidos": "Rojas",
            "documento": "12345678",
            "direccion": "Calle 1",
            "vendedor": "Luis",
        },
        "items": [{"sku": "BGT-001", "quantity": 1}],
    }


@pytest.mark.asyncio
async def test_new_budget_uses_updated_tax_and_ttl(client: AsyncClient, auth_headers: dict):
    await _create_product(client, auth_headers)

    res = await client.put(
        "/api/v1/config/global",
        json={"tax_rate": 10, "link_ttl_minutes": 15, "show_product_photos_in_pdf": True},
        headers=auth_headers,
    )
    assert res.status_code == 200

    created = await client.post("/api/v1/budgets/", json=_budget_payload())
    assert created.status_code == 201
    budget = created.json()
    assert budget["tax_percent"] == 10
    assert budget["tax_amount"] == 10
    assert budget["total"] == 110
    assert budget["link_ttl_minutes"] == 15


@pytest.mark.asyncio
async def test_existing_budget_not_recalculated_after_config_change(client: AsyncClient, auth_headers: dict):
    from app.api.dependencies import get_budget_use_cases

    await _create_product(client, auth_headers)

    await client.put(
        "/api/v1/config/global",
        json={"tax_rate": 10, "link_ttl_minutes": 15, "show_product_photos_in_pdf": True},
        headers=auth_headers,
    )
    first = await client.post("/api/v1/budgets/", json=_budget_payload())
    first_budget = first.json()

    await client.put(
        "/api/v1/config/global",
        json={"tax_rate": 20, "link_ttl_minutes": 1, "show_product_photos_in_pdf": False},
        headers=auth_headers,
    )
    second = await client.post("/api/v1/budgets/", json=_budget_payload())
    second_budget = second.json()

    assert first_budget["tax_percent"] == 10
    assert first_budget["total"] == 110
    assert second_budget["tax_percent"] == 20
    assert second_budget["total"] == 120

    fetched_first = await client.get(f"/api/v1/budgets/{first_budget['uuid']}")
    assert fetched_first.status_code == 200
    assert fetched_first.json()["tax_percent"] == 10
    assert fetched_first.json()["total"] == 110

    uc = get_budget_use_cases()
    first_model = await uc.get_by_uuid(first_budget["uuid"])
    assert first_model is not None
    first_model.created_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    await first_model.save()
    assert await uc.is_expired(first_model) is False
