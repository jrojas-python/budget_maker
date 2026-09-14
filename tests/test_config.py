from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.api import dependencies as dependencies_module
from app.api.dependencies import get_auth_use_cases, get_config_use_cases
from app.domain.models.budget import Budget
from app.domain.models.category import Category
from app.domain.models.global_config import GlobalConfig
from app.domain.models.product import Product
from app.domain.models.user import User
from settings.config import settings

_SUPABASE_BRANDING_PREFIX = (
    "https://fake-project.supabase.co/storage/v1/object/public/media/branding/"
)


@pytest.mark.asyncio
async def test_get_global_config_seeded(client: AsyncClient):
    res = await client.get("/api/v1/config/global")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data["tax_rate"], (int, float))
    assert isinstance(data["link_ttl_minutes"], int)
    assert isinstance(data["show_product_photos_in_pdf"], bool)


@pytest.mark.asyncio
async def test_init_beanie_and_seeds_are_idempotent_on_empty_database(_init_db):
    config_uc = get_config_use_cases()
    auth_uc = get_auth_use_cases()

    await config_uc.seed_defaults()
    await auth_uc.seed_superadmin()
    await config_uc.seed_defaults()
    await auth_uc.seed_superadmin()

    assert await GlobalConfig.find_all().count() == 1
    assert await User.find(User.username == settings.default_admin_username).count() == 1

    global_config = await GlobalConfig.find_one(GlobalConfig.singleton_key == "global")
    assert global_config is not None
    assert global_config.extra_settings["site_title"] == "BUDGET MAKER"
    assert global_config.extra_settings["site_subtitle"] == "Catálogo de Productos POP"

    global_indexes = await GlobalConfig.get_motor_collection().index_information()
    product_indexes = await Product.get_motor_collection().index_information()
    budget_indexes = await Budget.get_motor_collection().index_information()
    user_indexes = await User.get_motor_collection().index_information()
    category_indexes = await Category.get_motor_collection().index_information()

    assert any(
        info.get("unique") and info.get("key") == [("singleton_key", 1)]
        for info in global_indexes.values()
    )
    assert product_indexes["sku_1"]["unique"] is True
    assert budget_indexes["uq_budget_code"]["unique"] is True
    assert budget_indexes["uq_budget_uuid"]["unique"] is True
    assert user_indexes["username_1"]["unique"] is True
    assert user_indexes["email_1"]["unique"] is True
    assert category_indexes["slug_1"]["unique"] is True


@pytest.mark.asyncio
async def test_update_global_config_valid_payload(client: AsyncClient, auth_headers: dict[str, str]):
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
async def test_update_global_config_validation_error(client: AsyncClient, auth_headers: dict[str, str]):
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
async def test_legacy_boolean_string_is_coerced_correctly(client: AsyncClient, auth_headers: dict[str, str]):
    res = await client.put(
        "/api/v1/config/show_product_photos_in_pdf",
        json={"value": "false", "description": "Bandera fotos"},
        headers=auth_headers,
    )
    assert res.status_code == 200

    global_cfg = await client.get("/api/v1/config/global")
    assert global_cfg.status_code == 200
    assert global_cfg.json()["show_product_photos_in_pdf"] is False


@pytest.mark.asyncio
async def test_payment_methods_crud_happy_path(client: AsyncClient, auth_headers: dict[str, str]):
    initial = await client.get("/api/v1/config/payment-methods")
    assert initial.status_code == 200
    assert initial.json() == {"payment_methods": []}

    created = await client.post(
        "/api/v1/config/payment-methods",
        json={"name": " Transferencia "},
        headers=auth_headers,
    )
    assert created.status_code == 200
    assert created.json() == {"payment_methods": ["Transferencia"]}

    listed = await client.get("/api/v1/config/payment-methods")
    assert listed.status_code == 200
    assert listed.json() == {"payment_methods": ["Transferencia"]}

    removed = await client.delete("/api/v1/config/payment-methods/transferencia", headers=auth_headers)
    assert removed.status_code == 200
    assert removed.json() == {"payment_methods": []}


@pytest.mark.asyncio
async def test_payment_method_duplicate_or_empty_returns_422(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    created = await client.post(
        "/api/v1/config/payment-methods",
        json={"name": "Efectivo"},
        headers=auth_headers,
    )
    assert created.status_code == 200

    duplicate = await client.post(
        "/api/v1/config/payment-methods",
        json={"name": " efectivo "},
        headers=auth_headers,
    )
    assert duplicate.status_code == 422

    empty = await client.post(
        "/api/v1/config/payment-methods",
        json={"name": "   "},
        headers=auth_headers,
    )
    assert empty.status_code == 422

    listed = await client.get("/api/v1/config/payment-methods")
    assert listed.status_code == 200
    assert listed.json() == {"payment_methods": ["Efectivo"]}


@pytest.mark.asyncio
async def test_remove_payment_method_not_found_returns_404(client: AsyncClient, auth_headers: dict[str, str]):
    res = await client.delete("/api/v1/config/payment-methods/no-existe", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_upload_logo_explicit_endpoint_accepts_png_and_persists(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_storage_service: Any,
):
    res = await client.post(
        "/api/v1/config/logo",
        files={"file": ("logo.png", b"fake-png-bytes", "image/png")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["key"] == "site_logo"
    assert body["value"] == f"{_SUPABASE_BRANDING_PREFIX}site_logo.png"
    assert fake_storage_service.has_reference(body["value"])


@pytest.mark.asyncio
async def test_upload_logo_explicit_endpoint_accepts_jpg(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_storage_service: Any,
):
    res = await client.post(
        "/api/v1/config/logo",
        files={"file": ("logo.jpg", b"fake-jpg-bytes", "image/jpg")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["key"] == "site_logo"
    assert body["value"] == f"{_SUPABASE_BRANDING_PREFIX}site_logo.jpg"
    assert fake_storage_service.has_reference(body["value"])


@pytest.mark.asyncio
async def test_upload_logo_invalid_format_returns_400_and_keeps_previous_value(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_storage_service: Any,
):
    previous_url = fake_storage_service.store_branding_object("site_logo.png")
    seed = await client.put(
        "/api/v1/config/site_logo",
        json={"value": previous_url, "description": "Logo"},
        headers=auth_headers,
    )
    assert seed.status_code == 200

    res = await client.post(
        "/api/v1/config/logo",
        files={"file": ("logo.webp", b"fake-webp-bytes", "image/webp")},
        headers=auth_headers,
    )
    assert res.status_code == 400

    current = await client.get("/api/v1/config/site_logo")
    assert current.status_code == 200
    assert current.json()["value"] == previous_url
    assert fake_storage_service.has_reference(previous_url)


@pytest.mark.asyncio
async def test_upload_branding_legacy_icon_endpoint_still_works(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_storage_service: Any,
):
    res = await client.post(
        "/api/v1/config/branding/site_icon",
        files={"file": ("icon.webp", b"fake-webp-bytes", "image/webp")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["key"] == "site_icon"
    assert body["value"] == f"{_SUPABASE_BRANDING_PREFIX}site_icon.webp"
    assert fake_storage_service.has_reference(body["value"])


@pytest.mark.asyncio
async def test_upload_logo_replaces_previous_extension_and_cleans_old_object(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_storage_service: Any,
):
    previous_url = fake_storage_service.store_branding_object("site_logo.jpg")
    seed = await client.put(
        "/api/v1/config/site_logo",
        json={"value": previous_url, "description": "Logo previo"},
        headers=auth_headers,
    )
    assert seed.status_code == 200

    res = await client.post(
        "/api/v1/config/logo",
        files={"file": ("logo.png", b"new-logo", "image/png")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["value"] == f"{_SUPABASE_BRANDING_PREFIX}site_logo.png"
    assert fake_storage_service.has_reference(body["value"])
    assert not fake_storage_service.has_reference(previous_url)


@pytest.mark.asyncio
async def test_upload_logo_rolls_back_when_persistence_fails(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_storage_service: Any,
    monkeypatch: pytest.MonkeyPatch,
):
    previous_url = fake_storage_service.store_branding_object("site_logo.jpg")
    seed = await client.put(
        "/api/v1/config/site_logo",
        json={"value": previous_url, "description": "Logo previo"},
        headers=auth_headers,
    )
    assert seed.status_code == 200

    original_set_value = dependencies_module._config_repo.set_value

    async def failing_set_value(key: str, value, description: str = ""):
        if key == "site_logo" and value == f"{_SUPABASE_BRANDING_PREFIX}site_logo.png":
            raise RuntimeError("mongo config fail")
        return await original_set_value(key, value, description)

    monkeypatch.setattr(dependencies_module._config_repo, "set_value", failing_set_value)

    with pytest.raises(RuntimeError, match="mongo config fail"):
        await client.post(
            "/api/v1/config/logo",
            files={"file": ("logo.png", b"new-logo", "image/png")},
            headers=auth_headers,
        )

    current = await client.get("/api/v1/config/site_logo")
    assert current.status_code == 200
    assert current.json()["value"] == previous_url
    assert fake_storage_service.has_reference(previous_url)
    assert not fake_storage_service.has_reference(f"{_SUPABASE_BRANDING_PREFIX}site_logo.png")


@pytest.mark.asyncio
async def test_upload_logo_restores_previous_value_when_cleanup_of_old_asset_fails(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_storage_service: Any,
    monkeypatch: pytest.MonkeyPatch,
):
    previous_url = fake_storage_service.store_branding_object("site_logo.jpg")
    seed = await client.put(
        "/api/v1/config/site_logo",
        json={"value": previous_url, "description": "Logo previo"},
        headers=auth_headers,
    )
    assert seed.status_code == 200

    original_delete = dependencies_module._image_service.delete_branding_image

    async def failing_previous_delete(reference: str) -> None:
        if reference == previous_url:
            raise RuntimeError("cleanup previous failed")
        await original_delete(reference)

    monkeypatch.setattr(
        dependencies_module._image_service,
        "delete_branding_image",
        failing_previous_delete,
    )

    with pytest.raises(RuntimeError, match="cleanup previous failed"):
        await client.post(
            "/api/v1/config/logo",
            files={"file": ("logo.png", b"new-logo", "image/png")},
            headers=auth_headers,
        )

    current = await client.get("/api/v1/config/site_logo")
    assert current.status_code == 200
    assert current.json()["value"] == previous_url
    assert fake_storage_service.has_reference(previous_url)
    assert not fake_storage_service.has_reference(f"{_SUPABASE_BRANDING_PREFIX}site_logo.png")


@pytest.mark.asyncio
async def test_delete_branding_remote_clears_config_and_deletes_object(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_storage_service: Any,
):
    previous_url = fake_storage_service.store_branding_object("site_logo.png")
    seed = await client.put(
        "/api/v1/config/site_logo",
        json={"value": previous_url, "description": "Logo remoto"},
        headers=auth_headers,
    )
    assert seed.status_code == 200

    res = await client.delete("/api/v1/config/branding/site_logo", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["value"] == ""
    assert not fake_storage_service.has_reference(previous_url)


@pytest.mark.asyncio
async def test_delete_branding_legacy_path_removes_local_file_and_clears_value(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    legacy_filename = "legacy-site-logo-test.png"
    legacy_path = Path(settings.branding_dir) / legacy_filename
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_bytes(b"legacy-logo")

    seed = await client.put(
        "/api/v1/config/site_logo",
        json={"value": f"/uploads/branding/{legacy_filename}", "description": "Logo legacy"},
        headers=auth_headers,
    )
    assert seed.status_code == 200

    try:
        res = await client.delete("/api/v1/config/branding/site_logo", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["value"] == ""
        assert not legacy_path.exists()
    finally:
        if legacy_path.exists():
            legacy_path.unlink()


@pytest.mark.asyncio
async def test_delete_branding_restores_value_when_remote_delete_fails(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_storage_service: Any,
):
    previous_url = fake_storage_service.store_branding_object("site_logo.png")
    fake_storage_service.fail_delete_references.add(previous_url)

    seed = await client.put(
        "/api/v1/config/site_logo",
        json={"value": previous_url, "description": "Logo remoto"},
        headers=auth_headers,
    )
    assert seed.status_code == 200

    res = await client.delete("/api/v1/config/branding/site_logo", headers=auth_headers)
    assert res.status_code == 502

    current = await client.get("/api/v1/config/site_logo")
    assert current.status_code == 200
    assert current.json()["value"] == previous_url
    assert fake_storage_service.has_reference(previous_url)
