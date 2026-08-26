import pytest
from httpx import AsyncClient
from app.domain.models.global_config import GlobalConfig


@pytest.mark.asyncio
async def test_get_global_config_seeded(client: AsyncClient):
    res = await client.get("/api/v1/config/global")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data["tax_rate"], (int, float))
    assert isinstance(data["link_ttl_minutes"], int)
    assert isinstance(data["show_product_photos_in_pdf"], bool)


@pytest.mark.asyncio
async def test_update_global_config_valid_payload(client: AsyncClient, auth_headers: dict):
    payload = {
        "tax_rate": 17.5,
        "link_ttl_minutes": 45,
        "show_product_photos_in_pdf": False,
    }
    res = await client.put("/api/v1/config/global", json=payload, headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == payload

    legacy_tax = await client.get("/api/v1/config/porcentaje_impuesto")
    assert legacy_tax.status_code == 200
    assert legacy_tax.json()["value"] == payload["tax_rate"]

    typed_tax = await client.get("/api/v1/config/tax_rate")
    assert typed_tax.status_code == 200
    assert typed_tax.json()["value"] == payload["tax_rate"]


@pytest.mark.asyncio
async def test_update_global_config_validation_error(client: AsyncClient, auth_headers: dict):
    res = await client.put(
        "/api/v1/config/global",
        json={"tax_rate": 120, "link_ttl_minutes": 0, "show_product_photos_in_pdf": True},
        headers=auth_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_get_global_config_uses_legacy_values_when_typed_document_is_missing(client: AsyncClient):
    collection = GlobalConfig.get_motor_collection()
    await collection.delete_many({})
    await collection.insert_many(
        [
            {"key": "porcentaje_impuesto", "value": 12.5, "description": "Legacy impuesto"},
            {"key": "tiempo_expiracion_link_minutos", "value": 60, "description": "Legacy ttl"},
            {"key": "show_product_photos_in_pdf", "value": False, "description": "Legacy fotos"},
        ]
    )

    res = await client.get("/api/v1/config/global")
    assert res.status_code == 200
    data = res.json()
    assert data["tax_rate"] == 12.5
    assert data["link_ttl_minutes"] == 60
    assert data["show_product_photos_in_pdf"] is False


@pytest.mark.asyncio
async def test_legacy_boolean_string_is_coerced_correctly(client: AsyncClient, auth_headers: dict):
    res = await client.put(
        "/api/v1/config/show_product_photos_in_pdf",
        json={"value": "false", "description": "Bandera fotos"},
        headers=auth_headers,
    )
    assert res.status_code == 200

    global_cfg = await client.get("/api/v1/config/global")
    assert global_cfg.status_code == 200
    assert global_cfg.json()["show_product_photos_in_pdf"] is False
