from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import UUID

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


@pytest.mark.asyncio
@pytest.mark.parametrize("quantity", [0, -1])
async def test_budget_rejects_non_positive_quantity(
    client: AsyncClient,
    auth_headers: dict,
    quantity: int,
):
    payload = _budget_payload()
    payload["items"][0]["quantity"] = quantity

    response = await client.post("/api/v1/budgets/", json=payload)

    assert response.status_code == 422


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
async def test_create_budget_rejects_unknown_sku(client: AsyncClient, auth_headers: dict):
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
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/budgets/no-es-uuid",
        "/api/v1/budgets/no-es-uuid/pdf",
        "/api/v1/budgets/no-es-uuid/whatsapp-share",
        "/presupuesto/no-es-uuid",
        "/presupuesto/no-es-uuid/pdf",
    ],
)
async def test_public_budget_routes_reject_malformed_uuid(client: AsyncClient, path: str):
    """Las rutas públicas de presupuesto rechazan UUID malformado con 422."""
    res = await client.get(path)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_malformed_uuid_fails_before_repository_lookup(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """UUID malformado debe fallar en validación de ruta antes de consultar repositorio."""
    from app.application.use_cases.budget_use_cases import BudgetUseCases

    async def _should_not_be_called(_self: BudgetUseCases, _uuid: str):
        raise AssertionError("No debe ejecutarse lookup de repositorio para UUID inválido")

    monkeypatch.setattr(BudgetUseCases, "get_by_uuid", _should_not_be_called)
    res = await client.get("/api/v1/budgets/no-es-uuid")
    assert res.status_code == 422


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

    expired = await client.get("/api/v1/budgets/?is_expired=true")
    active = await client.get("/api/v1/budgets/?is_expired=false")
    assert budget_data["uuid"] in {item["uuid"] for item in expired.json()["items"]}
    assert budget_data["uuid"] not in {item["uuid"] for item in active.json()["items"]}
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
    response_data = res.json()
    uuids = [budget["uuid"] for budget in response_data["items"]]
    assert budget_data["uuid"] in uuids
    expired_entry = next(
        budget for budget in response_data["items"] if budget["uuid"] == budget_data["uuid"]
    )
    assert expired_entry["expires_at"] is not None
    assert expired_entry["is_expired"] is True


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

    expired = await client.get("/api/v1/budgets/?is_expired=true")
    active = await client.get("/api/v1/budgets/?is_expired=false")
    assert budget_data["uuid"] in {item["uuid"] for item in expired.json()["items"]}
    assert budget_data["uuid"] not in {item["uuid"] for item in active.json()["items"]}


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
    res = await client.get("/api/v1/budgets/550e8400-e29b-41d4-a716-446655440000/pdf")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_budget_returns_404_when_budget_not_found(client: AsyncClient):
    res = await client.get("/api/v1/budgets/550e8400-e29b-41d4-a716-446655440000")
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
    res = await client.get("/api/v1/budgets/550e8400-e29b-41d4-a716-446655440000/whatsapp-share")
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
async def test_create_budget_retries_when_code_collides(client: AsyncClient, auth_headers: dict, monkeypatch: pytest.MonkeyPatch):
    """Ante colisión de code, la creación reintenta con nuevo código."""
    from app.application.use_cases.budget_use_cases import BudgetUseCases

    await _create_product(client, auth_headers)
    first = await client.post("/api/v1/budgets/", json=_budget_payload())
    assert first.status_code == 201
    first_code = first.json()["code"]
    retry_code = f"{first_code[:-4]}ZZZZ"
    if retry_code == first_code:
        retry_code = f"{first_code[:-4]}YYYY"
    generated_codes = iter([first_code, retry_code])

    def _fake_generate_code(self: BudgetUseCases) -> str:
        return next(generated_codes)

    monkeypatch.setattr(BudgetUseCases, "_generate_code", _fake_generate_code)

    second = await client.post("/api/v1/budgets/", json=_budget_payload())
    assert second.status_code == 201
    assert second.json()["code"] == retry_code


@pytest.mark.asyncio
async def test_create_budget_fails_when_code_retries_are_exhausted(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    """Si colisiona code en todos los intentos, la API responde 409 explícito."""
    from app.application.use_cases.budget_use_cases import BudgetUseCases

    await _create_product(client, auth_headers)
    first = await client.post("/api/v1/budgets/", json=_budget_payload())
    assert first.status_code == 201
    first_code = first.json()["code"]

    monkeypatch.setattr(BudgetUseCases, "_generate_code", lambda _self: first_code)

    second = await client.post("/api/v1/budgets/", json=_budget_payload())
    assert second.status_code == 409
    assert "code" in second.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_budget_fails_explicitly_on_uuid_collision(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    """Ante colisión de uuid, la API falla explícitamente con HTTP 409."""
    from app.application.use_cases.budget_use_cases import BudgetUseCases
    import app.application.use_cases.budget_use_cases as budget_uc_module

    await _create_product(client, auth_headers)
    first = await client.post("/api/v1/budgets/", json=_budget_payload())
    assert first.status_code == 201
    first_budget = first.json()

    calls = {"count": 0}

    def _counted_code(_self: BudgetUseCases) -> str:
        calls["count"] += 1
        return "BM-20990101-UU11"

    monkeypatch.setattr(budget_uc_module, "uuid4", lambda: UUID(first_budget["uuid"]))
    monkeypatch.setattr(BudgetUseCases, "_generate_code", _counted_code)

    second = await client.post("/api/v1/budgets/", json=_budget_payload())
    assert second.status_code == 409
    assert "uuid" in second.json()["detail"].lower()
    assert calls["count"] == 1


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
async def test_html_and_pdf_render_all_client_fields(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.api.dependencies import _pdf_service

    await _create_product(client, auth_headers)
    payload = _budget_payload()
    payload["client_info"].update(
        {
            "email": "ana@example.com",
            "compania": "Empresa Cliente",
            "observaciones": "Entregar en recepción",
        }
    )
    created = await client.post("/api/v1/budgets/", json=payload)
    assert created.status_code == 201
    budget_uuid = created.json()["uuid"]

    web_response = await client.get(f"/presupuesto/{budget_uuid}")
    assert web_response.status_code == 200
    expected_values = (
        "Ana",
        "Rojas",
        "ana@example.com",
        "12345678",
        "Empresa Cliente",
        "Calle 1",
        "Entregar en recepción",
    )
    assert all(value in web_response.text for value in expected_values)

    captured: dict[str, str] = {}

    def _fake_pdf(html_content: str, base_url: str | None = None) -> bytes:
        captured["html"] = html_content
        return b"%PDF-1.4 prueba"

    monkeypatch.setattr(_pdf_service, "generate_from_html", _fake_pdf)
    pdf_response = await client.get(f"/api/v1/budgets/{budget_uuid}/pdf")
    assert pdf_response.status_code == 200
    assert all(value in captured["html"] for value in expected_values)


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


@pytest.mark.asyncio
async def test_pdf_uses_remote_supabase_assets_without_local_fallback(
    client: AsyncClient,
    auth_headers: dict,
    fake_storage_service,
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

    logo_url = fake_storage_service.store_branding_object("site_logo.png")
    update_logo = await client.put(
        "/api/v1/config/site_logo",
        json={"value": logo_url, "description": "Logo remoto"},
        headers=auth_headers,
    )
    assert update_logo.status_code == 200

    uc = get_budget_use_cases()
    product = await uc._product_repo.get_by_sku("BGT-001")
    assert product is not None
    product_url = fake_storage_service.store_product_object(f"{product.id}/budget-remote.png")
    product.images = [product_url]
    await product.save()

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
    assert logo_url in captured["html"]
    assert product_url in captured["html"]
    assert captured["base_url"].startswith("file://")


@pytest.mark.asyncio
async def test_pdf_generation_error_with_remote_assets_is_propagated(
    client: AsyncClient,
    auth_headers: dict,
    fake_storage_service,
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

    logo_url = fake_storage_service.store_branding_object("site_logo.png")
    await client.put(
        "/api/v1/config/site_logo",
        json={"value": logo_url, "description": "Logo remoto"},
        headers=auth_headers,
    )

    uc = get_budget_use_cases()
    product = await uc._product_repo.get_by_sku("BGT-001")
    assert product is not None
    product.images = [fake_storage_service.store_product_object(f"{product.id}/budget-remote.png")]
    await product.save()

    created = await client.post("/api/v1/budgets/", json=_budget_payload())
    budget_uuid = created.json()["uuid"]

    def _failing_pdf(html_content: str, base_url: str | None = None) -> bytes:
        raise RuntimeError("pdf unavailable")

    monkeypatch.setattr(_pdf_service, "generate_from_html", _failing_pdf)

    with pytest.raises(RuntimeError, match="pdf unavailable"):
        await client.get(f"/api/v1/budgets/{budget_uuid}/pdf")


@pytest.mark.asyncio
async def test_pdf_ignores_external_and_loopback_asset_urls(
    client: AsyncClient,
    auth_headers: dict,
):
    from app.api.dependencies import get_budget_use_cases

    await _create_product(client, auth_headers)
    uc = get_budget_use_cases()
    product = await uc._product_repo.get_by_sku("BGT-001")
    assert product is not None

    for external_url in (
        "https://cdn.example.com/product.png",
        "http://127.0.0.1:8000/internal.png",
        "http://[::1",
    ):
        product.images = [external_url]
        await product.save()
        assert await uc._resolve_product_image(product.sku, for_pdf=True) is None
        assert uc._resolve_branding_asset(external_url, for_pdf=True) is None


@pytest.mark.asyncio
async def test_budget_public_listing_and_private_operations_require_authentication(
    client: AsyncClient,
    auth_headers: dict,
):
    listed = await client.get("/api/v1/budgets/")
    assert listed.status_code == 200
    assert listed.json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "limit": 20,
        "pages": 0,
    }
    await _create_product(client, auth_headers)
    client.headers.pop("Authorization")
    created = await client.post("/api/v1/budgets/", json=_budget_payload())
    assert created.status_code == 201
    test_uuid = "550e8400-e29b-41d4-a716-446655440000"
    assert (await client.get(f"/api/v1/budgets/{test_uuid}/admin")).status_code == 401
    assert (await client.put(f"/api/v1/budgets/{test_uuid}", json={})).status_code == 401
    assert (await client.delete(f"/api/v1/budgets/{test_uuid}")).status_code == 401


@pytest.mark.asyncio
async def test_budget_with_only_name_does_not_create_client(
    client: AsyncClient,
    auth_headers: dict,
):
    from app.domain.models.client import Client

    await _create_product(client, auth_headers)
    payload = _budget_payload()
    payload["client_info"] = {"nombres": "Cliente sin documento"}

    created = await client.post("/api/v1/budgets/", json=payload)
    assert created.status_code == 201
    budget = created.json()
    assert budget["client_info"]["apellidos"] == ""
    assert budget["client_info"]["compania"] == ""
    assert await Client.find_all().count() == 0

    admin = await client.get(f"/api/v1/budgets/{budget['uuid']}/admin")
    assert admin.status_code == 200
    assert admin.json()["client_id"] is None
    html = await client.get(f"/presupuesto/{budget['uuid']}")
    assert html.status_code == 200
    assert "Cliente sin documento" in html.text


@pytest.mark.asyncio
async def test_budget_upserts_client_by_document_and_keeps_old_snapshot(
    client: AsyncClient,
    auth_headers: dict,
):
    await _create_product(client, auth_headers)
    first_payload = _budget_payload()
    first_payload["client_info"]["compania"] = "Empresa Original"
    first = await client.post("/api/v1/budgets/", json=first_payload)
    assert first.status_code == 201
    first_budget = first.json()
    first_admin = await client.get(f"/api/v1/budgets/{first_budget['uuid']}/admin")
    client_id = first_admin.json()["client_id"]
    assert client_id is not None

    client_update = await client.put(
        f"/api/v1/clients/{client_id}",
        json={"compania": "Empresa Editada"},
    )
    assert client_update.status_code == 200
    old_snapshot = await client.get(f"/api/v1/budgets/{first_budget['uuid']}")
    assert old_snapshot.json()["client_info"]["compania"] == "Empresa Original"

    second_payload = _budget_payload()
    second_payload["client_info"].update(
        {"documento": " 1234 5678 ", "compania": "Empresa Más Reciente"}
    )
    second = await client.post("/api/v1/budgets/", json=second_payload)
    assert second.status_code == 201
    second_admin = await client.get(f"/api/v1/budgets/{second.json()['uuid']}/admin")
    assert second_admin.json()["client_id"] == client_id
    assert second.json()["client_info"]["compania"] == "Empresa Más Reciente"

    old_snapshot_again = await client.get(f"/api/v1/budgets/{first_budget['uuid']}")
    assert old_snapshot_again.json()["client_info"]["compania"] == "Empresa Original"


@pytest.mark.asyncio
async def test_sparse_budget_does_not_clear_existing_client_fields(
    client: AsyncClient,
    auth_headers: dict,
):
    await _create_product(client, auth_headers)
    first_payload = _budget_payload()
    first_payload["client_info"].update(
        {"email": "cliente@example.com", "compania": "Empresa Vigente"}
    )
    first = await client.post("/api/v1/budgets/", json=first_payload)
    assert first.status_code == 201

    sparse_payload = {
        "client_info": {"nombres": "Cliente", "documento": "12345678"},
        "items": [{"sku": "BGT-001", "quantity": 1}],
    }
    second = await client.post("/api/v1/budgets/", json=sparse_payload)

    assert second.status_code == 201
    assert second.json()["client_info"]["email"] == "cliente@example.com"
    assert second.json()["client_info"]["compania"] == "Empresa Vigente"


@pytest.mark.asyncio
async def test_update_budget_recalculates_and_preserves_identity_and_expiration(
    client: AsyncClient,
    auth_headers: dict,
):
    product = await _create_product(client, auth_headers)
    await client.put(
        "/api/v1/config/global",
        json={"tax_rate": 10, "link_ttl_minutes": 60, "show_product_photos_in_pdf": True},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/config/payment-methods",
        json={"name": "Transferencia"},
        headers=auth_headers,
    )
    created = await client.post("/api/v1/budgets/", json=_budget_payload())
    assert created.status_code == 201
    original = created.json()

    await client.put(
        f"/api/v1/products/{product['id']}",
        json={"cost": 200.0},
        headers=auth_headers,
    )
    await client.put(
        "/api/v1/config/global",
        json={"tax_rate": 20, "link_ttl_minutes": 5, "show_product_photos_in_pdf": True},
        headers=auth_headers,
    )
    updated = await client.put(
        f"/api/v1/budgets/{original['uuid']}",
        json={
            "items": [{"sku": "BGT-001", "quantity": 2}],
            "payment_method": "Transferencia",
            "client_info": {"compania": "Compañía Actualizada"},
        },
    )
    assert updated.status_code == 200
    result = updated.json()
    assert result["code"] == original["code"]
    assert result["uuid"] == original["uuid"]
    assert result["created_at"] == original["created_at"]
    assert result["expires_at"] == original["expires_at"]
    assert result["link_ttl_minutes"] == original["link_ttl_minutes"]
    assert result["subtotal"] == 400
    assert result["tax_percent"] == 20
    assert result["tax_amount"] == 80
    assert result["total"] == 480
    assert result["payment_method"] == "Transferencia"
    assert result["client_info"]["compania"] == "Compañía Actualizada"


@pytest.mark.asyncio
async def test_budget_admin_filters_paginates_and_deletes_physically(
    client: AsyncClient,
    auth_headers: dict,
):
    await _create_product(client, auth_headers)
    first = await client.post("/api/v1/budgets/", json=_budget_payload())
    second_payload = _budget_payload()
    second_payload["client_info"].update(
        {"nombres": "Beatriz", "documento": "999", "compania": "Beta"}
    )
    second = await client.post("/api/v1/budgets/", json=second_payload)
    assert first.status_code == second.status_code == 201

    client.headers.pop("Authorization")
    filtered = await client.get("/api/v1/budgets/?q=Beta&page=1&limit=1")
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["pages"] == 1
    assert filtered.json()["items"][0]["uuid"] == second.json()["uuid"]

    client_id = filtered.json()["items"][0]["client_id"]
    by_client = await client.get(f"/api/v1/budgets/?client_id={client_id}")
    assert by_client.status_code == 200
    assert by_client.json()["total"] == 1

    deleted = await client.delete(
        f"/api/v1/budgets/{second.json()['uuid']}",
        headers=auth_headers,
    )
    assert deleted.status_code == 204
    assert (
        await client.get(
            f"/api/v1/budgets/{second.json()['uuid']}/admin",
            headers=auth_headers,
        )
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/clients/{client_id}", headers=auth_headers)
    ).status_code == 200
