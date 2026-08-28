from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient


async def _create_product(client: AsyncClient, auth_headers: dict) -> dict:
    res = await client.post(
        "/api/v1/products/",
        json={"name": "Producto Presupuesto", "sku": "BGT-001", "cost": 100.0, "unit": "unidad"},
        headers=auth_headers,
    )
    assert res.status_code == 201
    return res.json()


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


async def _expire_budget(uuid: str) -> None:
    from app.api.dependencies import get_budget_use_cases

    uc = get_budget_use_cases()
    model = await uc.get_by_uuid(uuid)
    assert model is not None
    model.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    await model.save()


def _extract_whatsapp_text(whatsapp_url: str) -> str:
    parsed = urlparse(whatsapp_url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "wa.me"
    assert parsed.path == "/"
    text_param = parse_qs(parsed.query).get("text")
    assert text_param
    return text_param[0]


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

    first_config = await client.put(
        "/api/v1/config/global",
        json={"tax_rate": 10, "link_ttl_minutes": 15, "show_product_photos_in_pdf": True},
        headers=auth_headers,
    )
    assert first_config.status_code == 200
    first = await client.post("/api/v1/budgets/", json=_budget_payload())
    first_budget = first.json()

    second_config = await client.put(
        "/api/v1/config/global",
        json={"tax_rate": 20, "link_ttl_minutes": 1, "show_product_photos_in_pdf": False},
        headers=auth_headers,
    )
    assert second_config.status_code == 200
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


@pytest.mark.asyncio
async def test_existing_budget_not_recalculated_after_product_cost_change(client: AsyncClient, auth_headers: dict):
    """Cambiar costo en catálogo no altera montos de presupuestos ya emitidos."""
    product = await _create_product(client, auth_headers)

    update_config = await client.put(
        "/api/v1/config/global",
        json={"tax_rate": 10, "link_ttl_minutes": 30, "show_product_photos_in_pdf": True},
        headers=auth_headers,
    )
    assert update_config.status_code == 200

    first = await client.post("/api/v1/budgets/", json=_budget_payload())
    assert first.status_code == 201
    first_budget = first.json()

    update_product = await client.put(
        f"/api/v1/products/{product['id']}",
        json={"cost": 150.0},
        headers=auth_headers,
    )
    assert update_product.status_code == 200
    assert update_product.json()["cost"] == 150.0

    fetched_first = await client.get(f"/api/v1/budgets/{first_budget['uuid']}")
    assert fetched_first.status_code == 200
    fetched_first_data = fetched_first.json()
    first_item = fetched_first_data["items"][0]
    assert first_item["unit_cost"] == 100.0
    assert first_item["line_total"] == 100.0
    assert fetched_first_data["subtotal"] == 100.0
    assert fetched_first_data["tax_percent"] == 10
    assert fetched_first_data["tax_amount"] == 10.0
    assert fetched_first_data["total"] == 110.0

    second = await client.post("/api/v1/budgets/", json=_budget_payload())
    assert second.status_code == 201
    second_budget = second.json()
    second_item = second_budget["items"][0]
    assert second_item["unit_cost"] == 150.0
    assert second_item["line_total"] == 150.0
    assert second_budget["subtotal"] == 150.0
    assert second_budget["tax_amount"] == 15.0
    assert second_budget["total"] == 165.0


@pytest.mark.asyncio
async def test_create_budget_with_active_payment_method(client: AsyncClient, auth_headers: dict):
    """Crear presupuesto con método de pago activo lo persiste correctamente."""
    await _create_product(client, auth_headers)
    await client.post("/api/v1/config/payment-methods", json={"name": "Transferencia"}, headers=auth_headers)

    payload = _budget_payload()
    payload["payment_method"] = "Transferencia"
    payload["client_info"]["email"] = "cliente@test.com"

    res = await client.post("/api/v1/budgets/", json=payload)
    assert res.status_code == 201
    budget = res.json()
    assert budget["payment_method"] == "Transferencia"
    assert budget["client_info"]["email"] == "cliente@test.com"


@pytest.mark.asyncio
async def test_create_budget_rejects_inactive_payment_method(client: AsyncClient, auth_headers: dict):
    """Método de pago que no está activo retorna HTTP 422."""
    await _create_product(client, auth_headers)

    payload = _budget_payload()
    payload["payment_method"] = "Bitcoin"

    res = await client.post("/api/v1/budgets/", json=payload)
    assert res.status_code == 422
    assert "no disponible" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_budget_rejects_unknown_sku(client: AsyncClient):
    """SKU inexistente retorna HTTP 422 al crear presupuesto."""
    payload = _budget_payload()
    payload["items"] = [{"sku": "SKU-NO-EXISTE", "quantity": 1}]

    res = await client.post("/api/v1/budgets/", json=payload)
    assert res.status_code == 422
    assert "producto no encontrado" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_budget_without_payment_method(client: AsyncClient, auth_headers: dict):
    """Crear presupuesto sin método de pago mantiene compatibilidad."""
    await _create_product(client, auth_headers)

    res = await client.post("/api/v1/budgets/", json=_budget_payload())
    assert res.status_code == 201
    assert res.json()["payment_method"] is None


@pytest.mark.asyncio
async def test_create_budget_persists_expires_at(client: AsyncClient, auth_headers: dict):
    """Al crear presupuesto, expires_at se persiste como created_at + TTL."""
    await _create_product(client, auth_headers)
    update_global = await client.put(
        "/api/v1/config/global",
        json={"tax_rate": 10, "link_ttl_minutes": 60, "show_product_photos_in_pdf": True},
        headers=auth_headers,
    )
    assert update_global.status_code == 200

    res = await client.post("/api/v1/budgets/", json=_budget_payload())
    assert res.status_code == 201
    budget = res.json()
    assert budget["expires_at"] is not None
    created = datetime.fromisoformat(budget["created_at"])
    expires = datetime.fromisoformat(budget["expires_at"])
    diff_minutes = (expires - created).total_seconds() / 60
    assert abs(diff_minutes - 60) < 1


@pytest.mark.asyncio
async def test_get_active_budget_returns_200(client: AsyncClient, auth_headers: dict):
    """GET /{uuid} de presupuesto activo retorna 200."""
    await _create_product(client, auth_headers)
    created = await client.post("/api/v1/budgets/", json=_budget_payload())
    uuid = created.json()["uuid"]

    res = await client.get(f"/api/v1/budgets/{uuid}")
    assert res.status_code == 200
    assert res.json()["expires_at"] is not None


@pytest.mark.asyncio
async def test_get_expired_budget_returns_410(client: AsyncClient, auth_headers: dict):
    """GET /{uuid} de presupuesto expirado retorna HTTP 410."""
    from app.api.dependencies import get_budget_use_cases

    await _create_product(client, auth_headers)
    created = await client.post("/api/v1/budgets/", json=_budget_payload())
    budget_data = created.json()

    # Forzar expiración moviendo expires_at al pasado
    uc = get_budget_use_cases()
    model = await uc.get_by_uuid(budget_data["uuid"])
    assert model is not None
    model.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    await model.save()

    res = await client.get(f"/api/v1/budgets/{budget_data['uuid']}")
    assert res.status_code == 410
    assert "expirado" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_budgets_includes_expired(client: AsyncClient, auth_headers: dict):
    """GET / (listado admin) incluye presupuestos expirados."""
    from app.api.dependencies import get_budget_use_cases

    await _create_product(client, auth_headers)
    created = await client.post("/api/v1/budgets/", json=_budget_payload())
    budget_data = created.json()

    uc = get_budget_use_cases()
    model = await uc.get_by_uuid(budget_data["uuid"])
    assert model is not None
    model.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    await model.save()

    res = await client.get("/api/v1/budgets/")
    assert res.status_code == 200
    uuids = [b["uuid"] for b in res.json()]
    assert budget_data["uuid"] in uuids
    expired_entry = next(b for b in res.json() if b["uuid"] == budget_data["uuid"])
    assert expired_entry["expires_at"] is not None


@pytest.mark.asyncio
async def test_legacy_budget_without_expires_at_uses_fallback(client: AsyncClient, auth_headers: dict):
    """Presupuesto legacy sin expires_at usa created_at + link_ttl_minutes como fallback."""
    from app.api.dependencies import get_budget_use_cases

    await _create_product(client, auth_headers)
    created = await client.post("/api/v1/budgets/", json=_budget_payload())
    budget_data = created.json()

    # Simular presupuesto legacy: quitar expires_at y forzar expiración vía created_at
    uc = get_budget_use_cases()
    model = await uc.get_by_uuid(budget_data["uuid"])
    assert model is not None
    model.expires_at = None
    model.created_at = datetime.now(timezone.utc) - timedelta(minutes=model.link_ttl_minutes + 1)
    await model.save()

    res = await client.get(f"/api/v1/budgets/{budget_data['uuid']}")
    assert res.status_code == 410


@pytest.mark.asyncio
async def test_api_pdf_returns_200_for_active_budget(client: AsyncClient, auth_headers: dict):
    await _create_product(client, auth_headers)
    created = await client.post("/api/v1/budgets/", json=_budget_payload())
    budget_uuid = created.json()["uuid"]

    res = await client.get(f"/api/v1/budgets/{budget_uuid}/pdf")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/pdf")
    assert res.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_api_pdf_returns_404_when_budget_not_found(client: AsyncClient):
    res = await client.get("/api/v1/budgets/00000000-0000-0000-0000-000000000000/pdf")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_api_pdf_returns_410_when_budget_expired(client: AsyncClient, auth_headers: dict):
    await _create_product(client, auth_headers)
    created = await client.post("/api/v1/budgets/", json=_budget_payload())
    budget_uuid = created.json()["uuid"]
    await _expire_budget(budget_uuid)

    res = await client.get(f"/api/v1/budgets/{budget_uuid}/pdf")
    assert res.status_code == 410
    assert "expirado" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_web_pdf_returns_410_when_budget_expired(client: AsyncClient, auth_headers: dict):
    await _create_product(client, auth_headers)
    created = await client.post("/api/v1/budgets/", json=_budget_payload())
    budget_uuid = created.json()["uuid"]
    await _expire_budget(budget_uuid)

    res = await client.get(f"/presupuesto/{budget_uuid}/pdf")
    assert res.status_code == 410
    assert "expirado" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_web_budget_view_returns_html_for_active_budget(client: AsyncClient, auth_headers: dict):
    await _create_product(client, auth_headers)
    created = await client.post("/api/v1/budgets/", json=_budget_payload())
    budget = created.json()

    res = await client.get(f"/presupuesto/{budget['uuid']}")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert budget["code"] in res.text


@pytest.mark.asyncio
async def test_web_pdf_returns_200_for_active_budget(client: AsyncClient, auth_headers: dict):
    await _create_product(client, auth_headers)
    created = await client.post("/api/v1/budgets/", json=_budget_payload())
    budget_uuid = created.json()["uuid"]

    res = await client.get(f"/presupuesto/{budget_uuid}/pdf")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/pdf")
    assert res.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_whatsapp_share_uses_canonical_format(client: AsyncClient, auth_headers: dict):
    await _create_product(client, auth_headers)
    await client.put(
        "/api/v1/config/site_title",
        json={"value": "Compañía Ñandú", "description": "Nombre comercial"},
        headers=auth_headers,
    )
    created = await client.post("/api/v1/budgets/", json=_budget_payload())
    budget = created.json()

    res = await client.get(f"/api/v1/budgets/{budget['uuid']}/whatsapp-share")
    assert res.status_code == 200
    whatsapp_url = res.json()["whatsapp_url"]
    text = _extract_whatsapp_text(whatsapp_url)

    assert f"Empresa: Compañía Ñandú" in text
    assert f"Código: {budget['code']}" in text
    assert f"Total: ${budget['total']:.2f}" in text
    assert f"Link: http://test/presupuesto/{budget['uuid']}" in text


@pytest.mark.asyncio
async def test_whatsapp_share_returns_404_when_budget_not_found(client: AsyncClient):
    res = await client.get("/api/v1/budgets/00000000-0000-0000-0000-000000000000/whatsapp-share")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_whatsapp_share_returns_410_when_budget_expired(client: AsyncClient, auth_headers: dict):
    await _create_product(client, auth_headers)
    created = await client.post("/api/v1/budgets/", json=_budget_payload())
    budget_uuid = created.json()["uuid"]
    await _expire_budget(budget_uuid)

    res = await client.get(f"/api/v1/budgets/{budget_uuid}/whatsapp-share")
    assert res.status_code == 410
    assert "expirado" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_whatsapp_share_fallbacks_site_title(client: AsyncClient, auth_headers: dict):
    await _create_product(client, auth_headers)
    await client.put(
        "/api/v1/config/site_title",
        json={"value": "   ", "description": "Vacío para fallback"},
        headers=auth_headers,
    )
    created = await client.post("/api/v1/budgets/", json=_budget_payload())
    budget = created.json()

    res = await client.get(f"/api/v1/budgets/{budget['uuid']}/whatsapp-share")
    assert res.status_code == 200
    text = _extract_whatsapp_text(res.json()["whatsapp_url"])
    assert "Empresa: BUDGET MAKER" in text


@pytest.mark.asyncio
async def test_whatsapp_share_encodes_special_characters(client: AsyncClient, auth_headers: dict):
    await _create_product(client, auth_headers)
    await client.put(
        "/api/v1/config/site_title",
        json={"value": "Compañía Perú Ñ", "description": "Acentos"},
        headers=auth_headers,
    )
    payload = _budget_payload()
    payload["client_info"]["nombres"] = "José"
    created = await client.post("/api/v1/budgets/", json=payload)
    budget = created.json()

    res = await client.get(f"/api/v1/budgets/{budget['uuid']}/whatsapp-share")
    assert res.status_code == 200
    whatsapp_url = res.json()["whatsapp_url"]
    assert " " not in whatsapp_url
    assert "Compañía" not in whatsapp_url
    assert "Ñ" not in whatsapp_url
    text = _extract_whatsapp_text(whatsapp_url)
    assert "Compañía Perú Ñ" in text


@pytest.mark.asyncio
async def test_web_and_api_use_same_whatsapp_format(client: AsyncClient, auth_headers: dict):
    await _create_product(client, auth_headers)
    created = await client.post("/api/v1/budgets/", json=_budget_payload())
    budget = created.json()

    share_res = await client.get(f"/api/v1/budgets/{budget['uuid']}/whatsapp-share")
    assert share_res.status_code == 200
    whatsapp_url = share_res.json()["whatsapp_url"]

    web_res = await client.get(f"/presupuesto/{budget['uuid']}")
    assert web_res.status_code == 200
    assert f'href="{whatsapp_url}"' in web_res.text


@pytest.mark.asyncio
async def test_pdf_hides_photo_column_when_config_is_disabled(client: AsyncClient, auth_headers: dict, monkeypatch: pytest.MonkeyPatch):
    from app.api.dependencies import _pdf_service

    await _create_product(client, auth_headers)
    update_global = await client.put(
        "/api/v1/config/global",
        json={"tax_rate": 18, "link_ttl_minutes": 30, "show_product_photos_in_pdf": False},
        headers=auth_headers,
    )
    assert update_global.status_code == 200

    created = await client.post("/api/v1/budgets/", json=_budget_payload())
    budget_uuid = created.json()["uuid"]

    captured: dict[str, str] = {}

    def _fake_pdf(html_content: str, base_url: str | None = None) -> bytes:
        captured["html"] = html_content
        captured["base_url"] = base_url or ""
        return b"%PDF-1.4 prueba"

    monkeypatch.setattr(_pdf_service, "generate_from_html", _fake_pdf)

    res = await client.get(f"/api/v1/budgets/{budget_uuid}/pdf")
    assert res.status_code == 200
    assert "photo-column" not in captured["html"]
    assert "budget-item-photo" not in captured["html"]
    assert captured["base_url"].startswith("file://")


@pytest.mark.asyncio
async def test_pdf_shows_photo_and_server_side_branding_when_enabled(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.api.dependencies import _pdf_service, get_budget_use_cases

    await _create_product(client, auth_headers)
    update_global = await client.put(
        "/api/v1/config/global",
        json={"tax_rate": 18, "link_ttl_minutes": 30, "show_product_photos_in_pdf": True},
        headers=auth_headers,
    )
    assert update_global.status_code == 200

    update_title = await client.put(
        "/api/v1/config/site_title",
        json={"value": "Mi Empresa SRL", "description": "Título de prueba"},
        headers=auth_headers,
    )
    assert update_title.status_code == 200
    update_subtitle = await client.put(
        "/api/v1/config/site_subtitle",
        json={"value": "Cotizaciones profesionales", "description": "Subtítulo de prueba"},
        headers=auth_headers,
    )
    assert update_subtitle.status_code == 200
    logo_filename = "test-site-logo.png"
    logo_path = Path("uploads/branding") / logo_filename
    logo_path.parent.mkdir(parents=True, exist_ok=True)
    logo_path.write_bytes(b"fake-logo")
    update_logo = await client.put(
        "/api/v1/config/site_logo",
        json={"value": f"/uploads/branding/{logo_filename}", "description": "Logo de prueba"},
        headers=auth_headers,
    )
    assert update_logo.status_code == 200

    uc = get_budget_use_cases()
    product = await uc._product_repo.get_by_sku("BGT-001")
    assert product is not None
    image_filename = "test-budget-photo.png"
    image_path = Path("uploads/products") / image_filename
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"fake-image")
    product.images = [image_filename]
    await product.save()

    created = await client.post("/api/v1/budgets/", json=_budget_payload())
    budget_uuid = created.json()["uuid"]

    captured: dict[str, str] = {}

    def _fake_pdf(html_content: str, base_url: str | None = None) -> bytes:
        captured["html"] = html_content
        return b"%PDF-1.4 prueba"

    monkeypatch.setattr(_pdf_service, "generate_from_html", _fake_pdf)

    try:
        res = await client.get(f"/api/v1/budgets/{budget_uuid}/pdf")
        assert res.status_code == 200
        assert "photo-column" in captured["html"]
        assert "budget-item-photo" in captured["html"]
        assert "budget-letterhead-logo" in captured["html"]
        assert logo_filename in captured["html"]
        assert "Mi Empresa SRL" in captured["html"]
        assert "Cotizaciones profesionales" in captured["html"]
    finally:
        if image_path.exists():
            image_path.unlink()
        if logo_path.exists():
            logo_path.unlink()
