from __future__ import annotations

import io
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
from httpx import AsyncClient

from app.api import dependencies as dependencies_module
from app.domain.models.category import Category
from app.domain.models.product import Product
from app.infrastructure.services.image_service import ImageService
from app.infrastructure.services import supabase_storage_service as supabase_storage_module
from app.infrastructure.services.supabase_storage_service import SupabaseStorageService
from settings.config import Settings, settings

_SUPABASE_PRODUCTS_PREFIX = (
    "https://fake-project.supabase.co/storage/v1/object/public/products/"
)


def _make_png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
        b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
        b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _make_storage_settings() -> Settings:
    return Settings(
        _env_file=None,
        mongo_uri=settings.mongo_uri,
        mongo_db_name=settings.mongo_db_name,
        test_mongo_uri=settings.test_mongo_uri,
        supabase_url="https://budget-maker-tests.supabase.co",
        supabase_secret_key="",
    )


@pytest.mark.asyncio
async def test_create_product_requires_auth(client: AsyncClient):
    res = await client.post(
        "/api/v1/products/",
        json={"name": "Test", "sku": "T-001", "cost": 10.0},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_crud_product(client: AsyncClient, auth_headers: dict[str, str]):
    res = await client.post(
        "/api/v1/products/",
        json={
            "name": "Cemento Portland",
            "sku": "CEM-001",
            "cost": 25.50,
            "unit": "bolsa",
            "currency": "USD",
        },
        headers=auth_headers,
    )
    assert res.status_code == 201
    product = res.json()
    assert product["name"] == "Cemento Portland"
    assert product["sku"] == "CEM-001"
    assert product["image_urls"] == []
    assert product["tags"] == []
    product_id = product["id"]

    res = await client.get("/api/v1/products/")
    assert res.status_code == 200

    res = await client.get(f"/api/v1/products/{product_id}")
    assert res.status_code == 200
    assert res.json()["sku"] == "CEM-001"

    res = await client.put(
        f"/api/v1/products/{product_id}",
        json={"name": "Cemento Portland Tipo I", "sku": "CEM-001", "cost": 27.00},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["cost"] == 27.00

    res = await client.delete(f"/api/v1/products/{product_id}", headers=auth_headers)
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_create_product_normalizes_tags(client: AsyncClient, auth_headers: dict[str, str]):
    res = await client.post(
        "/api/v1/products/",
        json={
            "name": "Perfil Metálico",
            "sku": "TAG-001",
            "cost": 12.5,
            "tags": ["Metal", " industrial ", "METAL", "  "],
        },
        headers=auth_headers,
    )
    assert res.status_code == 201
    assert res.json()["tags"] == ["metal", "industrial"]


@pytest.mark.asyncio
async def test_create_product_rejects_more_than_fifteen_tags(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    res = await client.post(
        "/api/v1/products/",
        json={
            "name": "Perfil Saturado",
            "sku": "TAG-002",
            "cost": 8.0,
            "tags": [f"tag-{index}" for index in range(16)],
        },
        headers=auth_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_upload_product_images_supports_multiple_files(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    res = await client.post(
        "/api/v1/products/",
        json={"name": "Producto Img", "sku": "IMG-001", "cost": 10.0},
        headers=auth_headers,
    )
    product_id = res.json()["id"]

    res = await client.post(
        f"/api/v1/products/{product_id}/image",
        files={"file": ("test.png", io.BytesIO(_make_png_bytes()), "image/png")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    first_upload = res.json()
    assert len(first_upload["image_urls"]) == 1
    assert first_upload["image_urls"][0].startswith(_SUPABASE_PRODUCTS_PREFIX)

    res = await client.post(
        f"/api/v1/products/{product_id}/image",
        files={"file": ("second.png", io.BytesIO(_make_png_bytes()), "image/png")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert len(res.json()["image_urls"]) == 2
    assert all(url.startswith(_SUPABASE_PRODUCTS_PREFIX) for url in res.json()["image_urls"])


@pytest.mark.asyncio
async def test_upload_tenth_image_succeeds(client: AsyncClient, auth_headers: dict[str, str]):
    product = Product(
        name="Producto nueve",
        sku="IMG-009",
        cost=10.0,
        images=[f"img_{index}.png" for index in range(9)],
    )
    await product.insert()

    res = await client.post(
        f"/api/v1/products/{product.id}/image",
        files={"file": ("tenth.png", io.BytesIO(_make_png_bytes()), "image/png")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert len(res.json()["image_urls"]) == 10
    assert any(url.startswith(_SUPABASE_PRODUCTS_PREFIX) for url in res.json()["image_urls"])


@pytest.mark.asyncio
async def test_upload_image_rejects_when_limit_reached(client: AsyncClient, auth_headers: dict[str, str]):
    product = Product(
        name="Producto límite",
        sku="IMG-010",
        cost=10.0,
        images=[f"img_{index}.png" for index in range(10)],
    )
    await product.insert()

    res = await client.post(
        f"/api/v1/products/{product.id}/image",
        files={"file": ("overflow.png", io.BytesIO(_make_png_bytes()), "image/png")},
        headers=auth_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_upload_image_rejects_invalid_format(client: AsyncClient, auth_headers: dict[str, str]):
    res = await client.post(
        "/api/v1/products/",
        json={"name": "Producto Inválido", "sku": "IMG-011", "cost": 10.0},
        headers=auth_headers,
    )
    product_id = res.json()["id"]

    res = await client.post(
        f"/api/v1/products/{product_id}/image",
        files={"file": ("bad.gif", io.BytesIO(b"GIF89a"), "image/gif")},
        headers=auth_headers,
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_delete_specific_image_removes_only_requested_file(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_storage_service: Any,
):
    res = await client.post(
        "/api/v1/products/",
        json={"name": "Producto Eliminar", "sku": "IMG-012", "cost": 10.0},
        headers=auth_headers,
    )
    product_id = res.json()["id"]

    first_upload = await client.post(
        f"/api/v1/products/{product_id}/image",
        files={"file": ("first.png", io.BytesIO(_make_png_bytes()), "image/png")},
        headers=auth_headers,
    )
    second_upload = await client.post(
        f"/api/v1/products/{product_id}/image",
        files={"file": ("second.png", io.BytesIO(_make_png_bytes()), "image/png")},
        headers=auth_headers,
    )
    assert first_upload.status_code == 200
    assert second_upload.status_code == 200
    image_urls = second_upload.json()["image_urls"]
    filename_to_delete = Path(urlsplit(image_urls[0]).path).name

    res = await client.delete(
        f"/api/v1/products/{product_id}/images/{filename_to_delete}",
        headers=auth_headers,
    )
    assert res.status_code == 200
    remaining_urls = res.json()["image_urls"]
    assert len(remaining_urls) == 1
    assert filename_to_delete not in remaining_urls[0]
    assert not fake_storage_service.has_reference(image_urls[0])
    assert fake_storage_service.has_reference(remaining_urls[0])


@pytest.mark.asyncio
async def test_delete_product_image_returns_404_when_missing(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    res = await client.post(
        "/api/v1/products/",
        json={"name": "Producto Sin Imagen", "sku": "IMG-013", "cost": 10.0},
        headers=auth_headers,
    )
    product_id = res.json()["id"]

    res = await client.delete(
        f"/api/v1/products/{product_id}/images/no-existe.png",
        headers=auth_headers,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_product_includes_image_urls_and_tags(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    res = await client.post(
        "/api/v1/products/",
        json={
            "name": "Producto Respuesta",
            "sku": "RESP-001",
            "cost": 18.0,
            "tags": ["Decoración", " interior "],
        },
        headers=auth_headers,
    )
    assert res.status_code == 201
    product = res.json()

    res = await client.get(f"/api/v1/products/{product['id']}")
    assert res.status_code == 200
    body = res.json()
    assert body["image_urls"] == []
    assert body["tags"] == ["decoración", "interior"]


@pytest.mark.asyncio
async def test_get_product_uses_legacy_image_filename_fallback(client: AsyncClient):
    product = Product(
        name="Producto Legacy",
        sku="LEG-001",
        cost=20.0,
        image_filename="legacy.png",
    )
    await product.insert()

    res = await client.get(f"/api/v1/products/{product.id}")
    assert res.status_code == 200
    assert res.json()["image_urls"] == ["http://test/uploads/products/legacy.png"]


@pytest.mark.asyncio
async def test_update_preserves_existing_tags(client: AsyncClient, auth_headers: dict[str, str]):
    res = await client.post(
        "/api/v1/products/",
        json={
            "name": "Producto Tags",
            "sku": "TAG-KEEP",
            "cost": 10.0,
            "tags": ["acero", "galvanizado"],
        },
        headers=auth_headers,
    )
    product_id = res.json()["id"]

    res = await client.put(
        f"/api/v1/products/{product_id}",
        json={"cost": 15.0},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["tags"] == ["acero", "galvanizado"]


@pytest.mark.asyncio
async def test_upload_image_to_legacy_product_migrates(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    product = Product(name="Legacy Upload", sku="LEG-UP", cost=10.0, image_filename="old.png")
    await product.insert()

    res = await client.post(
        f"/api/v1/products/{product.id}/image",
        files={"file": ("new.png", io.BytesIO(_make_png_bytes()), "image/png")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    image_urls = res.json()["image_urls"]
    assert len(image_urls) == 2
    assert "http://test/uploads/products/old.png" in image_urls
    assert any(url.startswith(_SUPABASE_PRODUCTS_PREFIX) for url in image_urls)

    updated = await Product.get(product.id)
    assert updated is not None
    assert updated.image_filename is None
    assert "old.png" in updated.images


@pytest.mark.asyncio
async def test_upload_image_rolls_back_storage_when_repository_update_fails(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_storage_service: Any,
    monkeypatch: pytest.MonkeyPatch,
):
    res = await client.post(
        "/api/v1/products/",
        json={"name": "Rollback", "sku": "RB-001", "cost": 10.0},
        headers=auth_headers,
    )
    product_id = res.json()["id"]

    original_update = dependencies_module._product_repo.update

    async def failing_update(doc_id: str, data: dict):
        if doc_id == product_id and any(
            str(value).startswith(_SUPABASE_PRODUCTS_PREFIX)
            for value in data.get("images", [])
        ):
            raise RuntimeError("mongo fail")
        return await original_update(doc_id, data)

    monkeypatch.setattr(dependencies_module._product_repo, "update", failing_update)

    with pytest.raises(RuntimeError, match="mongo fail"):
        await client.post(
            f"/api/v1/products/{product_id}/image",
            files={"file": ("rollback.png", io.BytesIO(_make_png_bytes()), "image/png")},
            headers=auth_headers,
        )

    product = await Product.get(product_id)
    assert product is not None
    assert product.images == []
    assert fake_storage_service.objects == {}


@pytest.mark.asyncio
async def test_delete_remote_image_does_not_touch_reference_from_other_product(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_storage_service: Any,
):
    own_url = fake_storage_service.store_product_object("product-a/own.png")
    other_url = fake_storage_service.store_product_object("product-b/other.png")

    own_product = Product(name="Producto A", sku="P-A", cost=10.0, images=[own_url])
    other_product = Product(name="Producto B", sku="P-B", cost=10.0, images=[other_url])
    await own_product.insert()
    await other_product.insert()

    other_filename = Path(urlsplit(other_url).path).name
    res = await client.delete(
        f"/api/v1/products/{own_product.id}/images/{other_filename}",
        headers=auth_headers,
    )

    assert res.status_code == 404
    assert fake_storage_service.has_reference(own_url)
    assert fake_storage_service.has_reference(other_url)


@pytest.mark.asyncio
async def test_delete_legacy_product_image_removes_local_reference_and_file(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    filename = "legacy-delete.png"
    legacy_path = Path(settings.upload_dir) / filename
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_bytes(b"legacy")

    product = Product(name="Legacy Delete", sku="LEG-DEL", cost=10.0, image_filename=filename)
    await product.insert()

    try:
        res = await client.delete(
            f"/api/v1/products/{product.id}/images/{filename}",
            headers=auth_headers,
        )
        assert res.status_code == 200
        assert res.json()["image_urls"] == []
        assert not legacy_path.exists()
    finally:
        if legacy_path.exists():
            legacy_path.unlink()


@pytest.mark.asyncio
async def test_delete_product_cascades_remote_and_legacy_images(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_storage_service: Any,
):
    legacy_filename = "legacy-product-delete.png"
    legacy_path = Path(settings.upload_dir) / legacy_filename
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_bytes(b"legacy-delete")

    remote_url = fake_storage_service.store_product_object("delete-product/remote.png")
    product = Product(
        name="Eliminar con assets",
        sku="DEL-ASSET-001",
        cost=10.0,
        images=[remote_url],
        image_filename=legacy_filename,
    )
    await product.insert()

    try:
        res = await client.delete(f"/api/v1/products/{product.id}", headers=auth_headers)
        assert res.status_code == 204
        assert await Product.get(product.id) is None
        assert not fake_storage_service.has_reference(remote_url)
        assert not legacy_path.exists()
    finally:
        if legacy_path.exists():
            legacy_path.unlink()


@pytest.mark.asyncio
async def test_delete_product_keeps_only_remaining_references_when_cleanup_fails(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_storage_service: Any,
):
    first_url = fake_storage_service.store_product_object("cleanup-fail/first.png")
    second_url = fake_storage_service.store_product_object("cleanup-fail/second.png")
    fake_storage_service.fail_delete_references.add(second_url)

    product = Product(
        name="Eliminar con rollback parcial",
        sku="DEL-ASSET-002",
        cost=10.0,
        images=[first_url, second_url],
    )
    await product.insert()

    res = await client.delete(f"/api/v1/products/{product.id}", headers=auth_headers)

    assert res.status_code == 502
    persisted = await Product.get(product.id)
    assert persisted is not None
    assert persisted.images == [second_url]
    assert persisted.image_filename is None
    assert not fake_storage_service.has_reference(first_url)
    assert fake_storage_service.has_reference(second_url)


@pytest.mark.asyncio
async def test_upload_image_requires_supabase_secret_for_writes(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    test_settings = _make_storage_settings()
    storage_service = SupabaseStorageService(test_settings)
    image_service = ImageService(storage_service=storage_service, app_settings=test_settings)
    monkeypatch.setattr(dependencies_module, "_supabase_storage_service", storage_service)
    monkeypatch.setattr(dependencies_module, "_image_service", image_service)

    res = await client.post(
        "/api/v1/products/",
        json={"name": "Sin secreto", "sku": "NO-SECRET", "cost": 10.0},
        headers=auth_headers,
    )
    product_id = res.json()["id"]

    res = await client.post(
        f"/api/v1/products/{product_id}/image",
        files={"file": ("secret.png", io.BytesIO(_make_png_bytes()), "image/png")},
        headers=auth_headers,
    )
    assert res.status_code == 503
    assert "SUPABASE_SECRET_KEY" in res.json()["detail"]


@pytest.mark.asyncio
async def test_supabase_storage_service_awaits_async_public_url(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeBucket:
        def __init__(self) -> None:
            self.awaited = False
            self.uploaded_paths: list[str] = []

        async def upload(self, path: str, content: bytes, options: dict[str, str]) -> None:
            self.uploaded_paths.append(path)

        async def get_public_url(self, path: str, options=None) -> str:
            self.awaited = True
            return f"https://cdn.example.com/{path}?signed=false"

    class FakeStorage:
        def __init__(self) -> None:
            self.bucket = FakeBucket()

        def from_(self, bucket_name: str) -> FakeBucket:
            assert bucket_name == "products"
            return self.bucket

    class FakeClient:
        def __init__(self) -> None:
            self.storage = FakeStorage()

    async def fake_factory(url: str, key: str) -> FakeClient:
        assert url == "https://budget-maker-tests.supabase.co"
        assert key == "service-secret"
        return FakeClient()

    monkeypatch.setattr(supabase_storage_module, "_load_async_client_factory", lambda: fake_factory)

    test_settings = Settings(
        _env_file=None,
        mongo_uri=settings.mongo_uri,
        mongo_db_name=settings.mongo_db_name,
        test_mongo_uri=settings.test_mongo_uri,
        supabase_url="https://budget-maker-tests.supabase.co",
        supabase_secret_key="service-secret",
    )
    service = SupabaseStorageService(test_settings)

    uploaded_url = await service.upload_product_image(
        content=b"image-bytes",
        product_id="prod-123",
        original_filename="photo.png",
        content_type="image/png",
    )

    assert uploaded_url.startswith("https://cdn.example.com/prod-123/")
    assert uploaded_url.endswith("?signed=false")
    assert service._client.storage.bucket.awaited is True
    assert service._client.storage.bucket.uploaded_paths[0].startswith("prod-123/")


@pytest.mark.asyncio
async def test_supabase_storage_service_deletes_encoded_public_urls(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeBucket:
        def __init__(self) -> None:
            self.removed_paths: list[list[str]] = []

        async def remove(self, paths: list[str]) -> None:
            self.removed_paths.append(paths)

    class FakeStorage:
        def __init__(self) -> None:
            self.bucket = FakeBucket()

        def from_(self, bucket_name: str) -> FakeBucket:
            assert bucket_name == "products"
            return self.bucket

    class FakeClient:
        def __init__(self) -> None:
            self.storage = FakeStorage()

    async def fake_factory(url: str, key: str) -> FakeClient:
        return FakeClient()

    monkeypatch.setattr(supabase_storage_module, "_load_async_client_factory", lambda: fake_factory)

    test_settings = Settings(
        _env_file=None,
        mongo_uri=settings.mongo_uri,
        mongo_db_name=settings.mongo_db_name,
        test_mongo_uri=settings.test_mongo_uri,
        supabase_url="https://budget-maker-tests.supabase.co",
        supabase_secret_key="service-secret",
    )
    service = SupabaseStorageService(test_settings)

    await service.delete_product_image(
        "https://budget-maker-tests.supabase.co/storage/v1/object/public/products/"
        "catalogo%20nuevo/imagen%201.png"
    )

    assert service._client.storage.bucket.removed_paths == [["catalogo nuevo/imagen 1.png"]]


@pytest.mark.asyncio
async def test_create_product_with_colors(client: AsyncClient, auth_headers: dict[str, str]):
    res = await client.post(
        "/api/v1/products/",
        json={
            "name": "Pintura Latex",
            "sku": "PIN-001",
            "cost": 45.00,
            "colors": [
                {"name": "Rojo", "hex": "#FF0000"},
                {"name": "Azul", "hex": "#0000FF"},
            ],
        },
        headers=auth_headers,
    )
    assert res.status_code == 201
    product = res.json()
    assert len(product["colors"]) == 2
    assert product["colors"][0]["name"] == "Rojo"
    assert product["colors"][0]["hex"] == "#FF0000"


@pytest.mark.asyncio
async def test_update_colors_endpoint(client: AsyncClient, auth_headers: dict[str, str]):
    res = await client.post(
        "/api/v1/products/",
        json={"name": "Barniz", "sku": "BAR-001", "cost": 30.00},
        headers=auth_headers,
    )
    product_id = res.json()["id"]

    res = await client.put(
        f"/api/v1/products/{product_id}/colors",
        json={
            "colors": [
                {"name": "Natural", "hex": "#D2B48C"},
                {"name": "Nogal", "hex": "#3B2F2F"},
                {"name": "Caoba", "hex": "#8B0000"},
            ]
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert len(res.json()["colors"]) == 3


@pytest.mark.asyncio
async def test_colors_max_six_validation(client: AsyncClient, auth_headers: dict[str, str]):
    colors = [{"name": f"Color{index}", "hex": f"#{'%02X' % (index * 40)}0000"} for index in range(7)]
    res = await client.post(
        "/api/v1/products/",
        json={"name": "Exceso", "sku": "EXC-001", "cost": 10.0, "colors": colors},
        headers=auth_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_invalid_hex_validation(client: AsyncClient, auth_headers: dict[str, str]):
    res = await client.post(
        "/api/v1/products/",
        json={
            "name": "Bad Hex",
            "sku": "HEX-001",
            "cost": 10.0,
            "colors": [{"name": "Malo", "hex": "NOTHEX"}],
        },
        headers=auth_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_product_rejects_invalid_category_ids(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    res = await client.post(
        "/api/v1/products/",
        json={
            "name": "Categoría inválida",
            "sku": "CAT-ERR-001",
            "cost": 10.0,
            "category_ids": ["no-es-objectid"],
        },
        headers=auth_headers,
    )

    assert res.status_code == 422
    assert "category_ids inválido" in res.json()["detail"]


@pytest.mark.asyncio
async def test_update_product_rejects_invalid_category_ids(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    created = await client.post(
        "/api/v1/products/",
        json={"name": "Producto base", "sku": "CAT-ERR-002", "cost": 10.0},
        headers=auth_headers,
    )
    product_id = created.json()["id"]

    res = await client.put(
        f"/api/v1/products/{product_id}",
        json={"category_ids": ["no-es-objectid"]},
        headers=auth_headers,
    )

    assert res.status_code == 422
    assert "category_ids inválido" in res.json()["detail"]


@pytest.mark.asyncio
async def test_search_products_rejects_invalid_category_id(client: AsyncClient):
    res = await client.get("/api/v1/products/search?category_id=no-es-objectid")

    assert res.status_code == 422
    assert "category_id inválido" in res.json()["detail"]


@pytest.mark.asyncio
async def test_search_products_filters_by_category_slug(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    category_a = await client.post(
        "/api/v1/categories/",
        json={"name": "Pisos"},
        headers=auth_headers,
    )
    category_b = await client.post(
        "/api/v1/categories/",
        json={"name": "Pinturas"},
        headers=auth_headers,
    )
    assert category_a.status_code == 201
    assert category_b.status_code == 201

    pisos_id = category_a.json()["id"]
    pinturas_id = category_b.json()["id"]

    await client.post(
        "/api/v1/products/",
        json={
            "name": "Porcelanato Pulido",
            "sku": "PISO-001",
            "cost": 25.0,
            "category_ids": [pisos_id],
        },
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/products/",
        json={
            "name": "Pintura Mate",
            "sku": "PINT-001",
            "cost": 15.0,
            "category_ids": [pinturas_id],
        },
        headers=auth_headers,
    )

    pisos = await client.get("/api/v1/products/search", params={"category_slug": "pisos"})
    assert pisos.status_code == 200
    assert [item["sku"] for item in pisos.json()["items"]] == ["PISO-001"]

    missing = await client.get("/api/v1/products/search", params={"category_slug": "no-existe"})
    assert missing.status_code == 200
    assert missing.json()["items"] == []
    assert missing.json()["total"] == 0


def _make_excel(rows: list[list]) -> bytes:
    """Helper para crear archivos Excel en memoria."""
    from openpyxl import Workbook

    workbook = Workbook()
    worksheet = workbook.active
    for row in rows:
        worksheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_import_excel_with_tags_normalizes(client: AsyncClient, auth_headers: dict[str, str]):
    excel_bytes = _make_excel(
        [
            ["nombre", "sku", "costo", "unidad", "moneda", "tags"],
            ["Tornillo Hex", "IMP-001", 5.0, "caja", "USD", "Metal, INDUSTRIAL, metal "],
            ["Tuerca M8", "IMP-002", 3.0, "bolsa", "USD", "metal, fijacion"],
        ]
    )
    res = await client.post(
        "/api/v1/products/import",
        files={
            "file": (
                "productos.xlsx",
                io.BytesIO(excel_bytes),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["created"] == 2

    res = await client.get("/api/v1/products/")
    products = {product["sku"]: product for product in res.json()}
    assert products["IMP-001"]["tags"] == ["metal", "industrial"]
    assert products["IMP-002"]["tags"] == ["metal", "fijacion"]


@pytest.mark.asyncio
async def test_import_excel_upsert_rewrites_tags(client: AsyncClient, auth_headers: dict[str, str]):
    excel1 = _make_excel(
        [
            ["nombre", "sku", "costo", "unidad", "moneda", "tags"],
            ["Producto X", "UPS-001", 10.0, "unidad", "USD", "original, viejo"],
        ]
    )
    await client.post(
        "/api/v1/products/import",
        files={
            "file": (
                "p.xlsx",
                io.BytesIO(excel1),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=auth_headers,
    )

    excel2 = _make_excel(
        [
            ["nombre", "sku", "costo", "unidad", "moneda", "tags"],
            ["Producto X", "UPS-001", 12.0, "unidad", "USD", "nuevo, actualizado"],
        ]
    )
    res = await client.post(
        "/api/v1/products/import",
        files={
            "file": (
                "p.xlsx",
                io.BytesIO(excel2),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=auth_headers,
    )
    assert res.json()["updated"] == 1

    res = await client.get("/api/v1/products/")
    products = {product["sku"]: product for product in res.json()}
    assert products["UPS-001"]["tags"] == ["nuevo", "actualizado"]


@pytest.mark.asyncio
async def test_import_excel_without_tags_column(client: AsyncClient, auth_headers: dict[str, str]):
    excel_bytes = _make_excel(
        [
            ["nombre", "sku", "costo", "unidad", "moneda"],
            ["Producto Simple", "NOTAG-001", 7.0, "unidad", "USD"],
        ]
    )
    res = await client.post(
        "/api/v1/products/import",
        files={
            "file": (
                "p.xlsx",
                io.BytesIO(excel_bytes),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["created"] == 1


@pytest.mark.asyncio
async def test_import_excel_truncates_excess_tags(client: AsyncClient, auth_headers: dict[str, str]):
    many_tags = ", ".join([f"tag-{index}" for index in range(20)])
    excel_bytes = _make_excel(
        [
            ["nombre", "sku", "costo", "unidad", "moneda", "tags"],
            ["Producto Exceso", "EXC-001", 5.0, "unidad", "USD", many_tags],
        ]
    )
    res = await client.post(
        "/api/v1/products/import",
        files={
            "file": (
                "p.xlsx",
                io.BytesIO(excel_bytes),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=auth_headers,
    )
    assert res.status_code == 200

    res = await client.get("/api/v1/products/")
    products = {product["sku"]: product for product in res.json()}
    assert len(products["EXC-001"]["tags"]) == 15
