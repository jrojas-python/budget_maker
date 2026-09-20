from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

import pytest
from httpx import AsyncClient


async def _create_product(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.post(
        "/api/v1/products/",
        json={"name": "Producto Métrica", "sku": "MET-001", "cost": 25.0, "unit": "unidad"},
        headers=auth_headers,
    )
    assert response.status_code == 201


def _payload(nombres: str, documento: str, quantity: int, payment_method: str | None) -> dict:
    return {
        "client_info": {"nombres": nombres, "documento": documento},
        "items": [{"sku": "MET-001", "quantity": quantity}],
        "payment_method": payment_method,
    }


@pytest.mark.asyncio
async def test_dashboard_requires_authentication(client: AsyncClient):
    response = await client.get("/api/v1/dashboard/metrics")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_metrics_cover_utc_series_clients_products_and_payments(
    client: AsyncClient,
    auth_headers: dict,
):
    from app.api.dependencies import get_budget_use_cases

    await _create_product(client, auth_headers)
    await client.post(
        "/api/v1/config/payment-methods",
        json={"name": "Efectivo"},
        headers=auth_headers,
    )

    first = await client.post(
        "/api/v1/budgets/",
        json=_payload("Ana", "A-1", 1, "Efectivo"),
    )
    second = await client.post(
        "/api/v1/budgets/",
        json=_payload("Ana Actualizada", "A-1", 2, None),
    )
    anonymous = await client.post(
        "/api/v1/budgets/",
        json=_payload("Sin documento", "", 1, None),
    )
    assert first.status_code == second.status_code == anonymous.status_code == 201

    now = datetime.now(timezone.utc)
    today_start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    uc = get_budget_use_cases()
    first_model = await uc.get_by_uuid(first.json()["uuid"])
    second_model = await uc.get_by_uuid(second.json()["uuid"])
    anonymous_model = await uc.get_by_uuid(anonymous.json()["uuid"])
    assert first_model and second_model and anonymous_model
    first_model.created_at = today_start + timedelta(hours=1)
    second_model.created_at = today_start - timedelta(days=2) + timedelta(hours=1)
    anonymous_model.created_at = today_start - timedelta(days=1) + timedelta(hours=1)
    await first_model.save()
    await second_model.save()
    await anonymous_model.save()

    date_from = today_start - timedelta(days=3)
    date_to = today_start + timedelta(hours=23)
    response = await client.get(
        "/api/v1/dashboard/metrics",
        params={"from": date_from.isoformat(), "to": date_to.isoformat(), "top_limit": 5},
    )
    assert response.status_code == 200
    metrics = response.json()
    assert metrics["counts"]["today"] == 1
    assert metrics["counts"]["current_week"] >= 1
    assert metrics["counts"]["current_month"] >= 1
    assert [point["count"] for point in metrics["daily_series"]] == [0, 1, 1, 1]
    assert metrics["unique_clients"] == 1
    assert metrics["recurrent_clients"] == 1
    assert metrics["top_products"][0] == {
        "sku": "MET-001",
        "name": "Producto Métrica",
        "quantity": 4,
        "amount": 100.0,
    }
    payment_counts = {
        row["payment_method"]: row["count"] for row in metrics["payment_methods"]
    }
    assert payment_counts == {"Sin especificar": 2, "Efectivo": 1}


@pytest.mark.asyncio
async def test_dashboard_rejects_invalid_or_unbounded_range(
    client: AsyncClient,
    auth_headers: dict,
):
    now = datetime.now(timezone.utc)
    reversed_range = await client.get(
        "/api/v1/dashboard/metrics",
        params={"from": now.isoformat(), "to": (now - timedelta(days=1)).isoformat()},
    )
    assert reversed_range.status_code == 422

    oversized_range = await client.get(
        "/api/v1/dashboard/metrics",
        params={
            "from": (now - timedelta(days=366)).isoformat(),
            "to": now.isoformat(),
        },
    )
    assert oversized_range.status_code == 422

    maximum_range = await client.get(
        "/api/v1/dashboard/metrics",
        params={
            "from": (now - timedelta(days=365)).isoformat(),
            "to": now.isoformat(),
        },
    )
    assert maximum_range.status_code == 200
    assert len(maximum_range.json()["daily_series"]) == 366