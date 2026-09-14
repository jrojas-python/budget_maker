from typing import AsyncGenerator

import pytest_asyncio
from beanie import init_beanie
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from app.domain.models.budget import Budget
from app.domain.models.category import Category
from app.domain.models.global_config import GlobalConfig
from app.domain.models.product import Product
from app.domain.models.user import User
from settings.config import Settings, TEST_MONGO_DB_NAME, ensure_safe_test_mongo_uri

TEST_SETTINGS = Settings()
TEST_DB_NAME = TEST_MONGO_DB_NAME
TEST_MONGO_URI = ensure_safe_test_mongo_uri(TEST_SETTINGS.test_mongo_uri, expected_db_name=TEST_DB_NAME)


@pytest_asyncio.fixture
async def _init_db():
    """Inicializa la base de datos de test por caso de prueba."""
    client = AsyncIOMotorClient(TEST_MONGO_URI)
    try:
        db = client[TEST_DB_NAME]
        await init_beanie(
            database=db,
            document_models=[GlobalConfig, Product, Budget, User, Category],
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


@pytest_asyncio.fixture
async def client(_init_db) -> AsyncGenerator[AsyncClient, None]:
    """Cliente HTTP de test con la app FastAPI."""
    from main import app
    from app.api.dependencies import get_config_use_cases

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

    res = await client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "admin1234",
    })
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest_asyncio.fixture
def auth_headers(auth_token: str) -> dict:
    return {"Authorization": f"Bearer {auth_token}"}
