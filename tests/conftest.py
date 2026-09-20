from __future__ import annotations

from typing import AsyncGenerator, Generator
from urllib.parse import quote, unquote, urlsplit
from uuid import uuid4

import pytest
import pytest_asyncio
from beanie import init_beanie
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from app.domain.models.budget import Budget
from app.domain.models.category import Category
from app.domain.models.client import Client
from app.domain.models.global_config import GlobalConfig
from app.domain.models.product import Product
from app.domain.models.user import User
from app.infrastructure.services.image_service import ImageService
from app.infrastructure.services.supabase_storage_service import (
    SupabaseStorageOperationError,
    SupabaseStorageReferenceError,
)
from settings.config import Settings, TEST_MONGO_DB_NAME, ensure_safe_test_mongo_uri

TEST_SETTINGS = Settings()
TEST_DB_NAME = TEST_MONGO_DB_NAME
TEST_MONGO_URI = ensure_safe_test_mongo_uri(
    TEST_SETTINGS.test_mongo_uri,
    expected_db_name=TEST_DB_NAME,
)


class FakeSupabaseStorageService:
    """Fake in-memory de Supabase Storage para pruebas aisladas."""

    public_root = "https://fake-project.supabase.co/storage/v1/object/public"
    products_bucket = "products"
    media_bucket = "media"
    branding_prefix = "branding"

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.deleted_references: list[str] = []
        self.fail_delete_references: set[str] = set()
        self.fail_product_upload = False
        self.fail_branding_upload = False

    async def upload_product_image(
        self,
        *,
        content: bytes,
        product_id: str,
        original_filename: str,
        content_type: str,
    ) -> str:
        if self.fail_product_upload:
            raise SupabaseStorageOperationError("Fallo fake subiendo imagen de producto")
        ext = self._extension_from_filename(original_filename)
        object_path = f"{product_id}/{uuid4().hex}{ext}"
        self.objects[(self.products_bucket, object_path)] = content
        return self._public_url(self.products_bucket, object_path)

    async def delete_product_image(
        self,
        reference: str,
        expected_product_id: str | None = None,
    ) -> None:
        if expected_product_id:
            _, object_path = self._extract(reference, expected_bucket=self.products_bucket)
            if not object_path.startswith(f"{expected_product_id}/"):
                raise SupabaseStorageReferenceError("Producto fake inesperado")
        await self._delete_reference(reference, expected_bucket=self.products_bucket)

    async def upload_branding_asset(
        self,
        *,
        key: str,
        content: bytes,
        original_filename: str,
        content_type: str,
    ) -> str:
        if self.fail_branding_upload:
            raise SupabaseStorageOperationError("Fallo fake subiendo branding")
        ext = self._extension_from_filename(original_filename)
        object_path = f"{self.branding_prefix}/{key}-{uuid4().hex}{ext}"
        self.objects[(self.media_bucket, object_path)] = content
        return self._public_url(self.media_bucket, object_path)

    async def delete_branding_asset(
        self,
        reference: str,
        expected_key: str | None = None,
    ) -> None:
        if expected_key:
            _, object_path = self._extract(
                reference,
                expected_bucket=self.media_bucket,
                expected_prefix=self.branding_prefix,
            )
            filename = object_path.rsplit("/", maxsplit=1)[-1]
            if not (
                filename.startswith(f"{expected_key}-")
                or filename.startswith(f"{expected_key}.")
            ):
                raise SupabaseStorageReferenceError("Clave fake inesperada")
        await self._delete_reference(
            reference,
            expected_bucket=self.media_bucket,
            expected_prefix=self.branding_prefix,
        )

    def is_product_public_url(self, reference: str) -> bool:
        return self._try_extract(reference, expected_bucket=self.products_bucket) is not None

    def is_branding_public_url(self, reference: str) -> bool:
        return (
            self._try_extract(
                reference,
                expected_bucket=self.media_bucket,
                expected_prefix=self.branding_prefix,
            )
            is not None
        )

    def store_product_object(self, object_path: str, content: bytes = b"fake-product") -> str:
        self.objects[(self.products_bucket, object_path)] = content
        return self._public_url(self.products_bucket, object_path)

    def store_branding_object(self, filename: str, content: bytes = b"fake-branding") -> str:
        object_path = f"{self.branding_prefix}/{filename}"
        self.objects[(self.media_bucket, object_path)] = content
        return self._public_url(self.media_bucket, object_path)

    def has_reference(self, reference: str) -> bool:
        extracted = self._try_extract(reference)
        if not extracted:
            return False
        bucket_name, object_path = extracted
        return (bucket_name, object_path) in self.objects

    async def _delete_reference(
        self,
        reference: str,
        *,
        expected_bucket: str,
        expected_prefix: str | None = None,
    ) -> None:
        if reference in self.fail_delete_references:
            raise SupabaseStorageOperationError("Fallo fake eliminando objeto")
        extracted = self._extract(
            reference,
            expected_bucket=expected_bucket,
            expected_prefix=expected_prefix,
        )
        self.objects.pop(extracted, None)
        self.deleted_references.append(reference)

    def _extract(
        self,
        reference: str,
        *,
        expected_bucket: str | None = None,
        expected_prefix: str | None = None,
    ) -> tuple[str, str]:
        parsed = urlsplit(reference)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            raise SupabaseStorageReferenceError("Referencia fake inválida")
        prefix = "/storage/v1/object/public/"
        path = unquote(parsed.path)
        if not path.startswith(prefix):
            raise SupabaseStorageReferenceError("Referencia fake inválida")
        remainder = path[len(prefix):]
        bucket_name, _, object_path = remainder.partition("/")
        if not bucket_name or not object_path:
            raise SupabaseStorageReferenceError("Referencia fake inválida")
        if expected_bucket and bucket_name != expected_bucket:
            raise SupabaseStorageReferenceError("Bucket fake inesperado")
        if expected_prefix:
            normalized_prefix = expected_prefix.strip("/")
            if object_path != normalized_prefix and not object_path.startswith(f"{normalized_prefix}/"):
                raise SupabaseStorageReferenceError("Prefijo fake inesperado")
        return bucket_name, object_path

    def _try_extract(
        self,
        reference: str,
        *,
        expected_bucket: str | None = None,
        expected_prefix: str | None = None,
    ) -> tuple[str, str] | None:
        try:
            return self._extract(
                reference,
                expected_bucket=expected_bucket,
                expected_prefix=expected_prefix,
            )
        except (SupabaseStorageReferenceError, ValueError):
            return None

    def _public_url(self, bucket_name: str, object_path: str) -> str:
        return f"{self.public_root}/{bucket_name}/{quote(object_path, safe='/')}"

    def _extension_from_filename(self, original_filename: str) -> str:
        suffix = original_filename.rsplit(".", maxsplit=1)
        if len(suffix) == 2 and suffix[1]:
            return f".{suffix[1].lower()}"
        return ".png"


@pytest_asyncio.fixture
async def _init_db():
    """Inicializa la base de datos de test por caso de prueba."""
    client = AsyncIOMotorClient(TEST_MONGO_URI)
    try:
        db = client[TEST_DB_NAME]
        await init_beanie(
            database=db,
            document_models=[GlobalConfig, Product, Budget, User, Category, Client],
        )
        yield db
    finally:
        await client.drop_database(TEST_DB_NAME)
        client.close()


@pytest_asyncio.fixture(autouse=True)
async def _clean_collections(_init_db):
    """Limpia todas las colecciones antes de cada test."""
    db = _init_db
    for name in await db.list_collection_names():
        await db[name].delete_many({})


@pytest.fixture(autouse=True)
def fake_storage_service(monkeypatch) -> Generator[FakeSupabaseStorageService, None, None]:
    """Inyecta un fake de Storage para evitar llamadas reales a Supabase."""
    from app.api import dependencies as dependencies_module

    fake_storage = FakeSupabaseStorageService()
    monkeypatch.setattr(dependencies_module, "_supabase_storage_service", fake_storage)
    monkeypatch.setattr(
        dependencies_module,
        "_image_service",
        ImageService(storage_service=fake_storage),
    )
    yield fake_storage


@pytest_asyncio.fixture
async def client(_init_db) -> AsyncGenerator[AsyncClient, None]:
    """Cliente HTTP de test con la app FastAPI."""
    from app.api.dependencies import get_config_use_cases
    from main import app

    await get_config_use_cases().seed_defaults()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_token(client: AsyncClient) -> str:
    """Crea el superadmin y retorna un token JWT válido."""
    from app.api.dependencies import get_auth_use_cases

    uc = get_auth_use_cases()
    await uc.seed_superadmin()

    res = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin1234"},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.fixture
def auth_headers(client: AsyncClient, auth_token: str) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {auth_token}"}
    client.headers.update(headers)
    return headers
