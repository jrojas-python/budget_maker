from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient

from app.api.dependencies import get_budget_use_cases

_FULL = {
    "company_name": "Mi Empresa SAC",
    "company_phone": "+51 999 888 777",
    "company_address": "Av. Principal 123",
    "company_ruc": "12345678901",
    "show_company_info": True,
    "company_info_position": "footer",
}


async def _create_budget(client: AsyncClient, auth_headers: dict) -> dict:
    res = await client.post(
        "/api/v1/products/",
        json={"name": "Producto", "sku": "CMP-001", "cost": 100.0, "unit": "unidad"},
        headers=auth_headers,
    )
    assert res.status_code == 201
    created = await client.post(
        "/api/v1/budgets/",
        json={
            "client_info": {"nombres": "Ana", "documento": "123", "vendedor": "Luis"},
            "items": [{"sku": "CMP-001", "quantity": 1}],
        },
    )
    assert created.status_code == 201
    return created.json()


async def _set_company(client: AsyncClient, auth_headers: dict, **fields) -> dict:
    res = await client.put("/api/v1/config/company", json=fields, headers=auth_headers)
    assert res.status_code == 200
    return res.json()


@pytest.mark.asyncio
async def test_get_company_info_defaults_public(client: AsyncClient):
    res = await client.get("/api/v1/config/company")
    assert res.status_code == 200
    data = res.json()
    assert data["show_company_info"] is False
    assert data["company_info_position"] == "footer"
    assert data["company_name"] == ""


@pytest.mark.asyncio
async def test_put_company_info_requires_auth(client: AsyncClient):
    res = await client.put("/api/v1/config/company", json={"company_name": "X"})
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_put_company_info_partial_update_and_strip(client: AsyncClient, auth_headers: dict):
    await _set_company(client, auth_headers, **_FULL)
    data = await _set_company(client, auth_headers, company_phone="  555  ")
    assert data["company_phone"] == "555"
    assert data["company_name"] == "Mi Empresa SAC"
    assert data["company_ruc"] == "12345678901"
    assert (await client.get("/api/v1/config/company")).json() == data


@pytest.mark.asyncio
async def test_put_company_info_invalid_position(client: AsyncClient, auth_headers: dict):
    res = await client.put(
        "/api/v1/config/company", json={"company_info_position": "sidebar"}, headers=auth_headers
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_web_view_shows_only_filled_fields(client: AsyncClient, auth_headers: dict):
    budget = await _create_budget(client, auth_headers)
    await _set_company(client, auth_headers, **{**_FULL, "company_phone": "", "company_address": ""})

    html = (await client.get(f"/presupuesto/{budget['uuid']}")).text
    assert "budget-footer" in html
    assert "Mi Empresa SAC" in html
    assert "12345678901" in html
    assert "Tel:" not in html
    assert "Dirección:</strong> Av." not in html


@pytest.mark.asyncio
async def test_web_view_hidden_when_disabled(client: AsyncClient, auth_headers: dict):
    budget = await _create_budget(client, auth_headers)
    await _set_company(client, auth_headers, **{**_FULL, "show_company_info": False})
    html = (await client.get(f"/presupuesto/{budget['uuid']}")).text
    assert "Mi Empresa SAC" not in html
    assert "budget-footer" not in html


@pytest.mark.asyncio
async def test_web_header_position_and_pdf_forces_footer(client: AsyncClient, auth_headers: dict):
    budget = await _create_budget(client, auth_headers)
    await _set_company(client, auth_headers, **{**_FULL, "company_info_position": "header"})

    html = (await client.get(f"/presupuesto/{budget['uuid']}")).text
    assert "company-info-header" in html
    assert "budget-footer" not in html

    uc = get_budget_use_cases()
    model = await uc.get_by_uuid(budget["uuid"])
    pdf_ctx = await uc.build_budget_render_context(model, for_pdf=True)
    assert pdf_ctx["company_info"]["position"] == "footer"

    pdf = await client.get(f"/presupuesto/{budget['uuid']}/pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_whatsapp_text_appends_company_block(client: AsyncClient, auth_headers: dict):
    budget = await _create_budget(client, auth_headers)
    await _set_company(client, auth_headers, **{**_FULL, "company_address": ""})

    res = await client.get(f"/api/v1/budgets/{budget['uuid']}/whatsapp-share")
    text = parse_qs(urlparse(res.json()["whatsapp_url"]).query)["text"][0]
    lines = text.splitlines()
    assert lines[-3:] == ["Compañía: Mi Empresa SAC", "Tel: +51 999 888 777", "RUC: 12345678901"]
    assert "Dirección" not in text

    await _set_company(client, auth_headers, show_company_info=False)
    res = await client.get(f"/api/v1/budgets/{budget['uuid']}/whatsapp-share")
    text = parse_qs(urlparse(res.json()["whatsapp_url"]).query)["text"][0]
    assert "RUC" not in text
