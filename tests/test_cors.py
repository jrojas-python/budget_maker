from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from main import create_app
from settings.config import DEFAULT_CORS_ALLOWED_ORIGIN, Settings


@pytest.fixture
def _init_db() -> None:
    """Evita iniciar MongoDB en estas pruebas aisladas de middleware."""


@pytest.fixture(autouse=True)
def _clean_collections() -> None:
    """Evita la limpieza de MongoDB en estas pruebas aisladas."""


@pytest.fixture
def cors_app():
    """Crea una aplicación con una política CORS independiente del entorno."""
    app_settings = Settings(
        _env_file=None,
        cors_allowed_origins=DEFAULT_CORS_ALLOWED_ORIGIN,
    )
    return create_app(app_settings)


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS"])
async def test_cors_allows_required_api_methods(method: str, cors_app) -> None:
    transport = ASGITransport(app=cors_app)
    headers = {
        "Origin": "https://budget-maker-frontend.vercel.app",
        "Access-Control-Request-Method": method,
        "Access-Control-Request-Headers": "authorization,content-type",
    }

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        preflight_response = await client.options("/api/v1/budgets/", headers=headers)

    assert preflight_response.status_code == 200
    assert preflight_response.headers["access-control-allow-origin"] == (
        "https://budget-maker-frontend.vercel.app"
    )
    assert method in preflight_response.headers["access-control-allow-methods"]
    assert "authorization" in preflight_response.headers["access-control-allow-headers"].lower()
    assert "content-type" in preflight_response.headers["access-control-allow-headers"].lower()
    assert preflight_response.headers["vary"] == "Origin"


@pytest.mark.asyncio
async def test_cors_allows_vercel_production_simple_request(cors_app) -> None:
    transport = ASGITransport(app=cors_app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        simple_response = await client.get(
            "/docs",
            headers={"Origin": "https://budget-maker-frontend.vercel.app"},
        )

    assert simple_response.status_code == 200
    assert simple_response.headers["access-control-allow-origin"] == (
        "https://budget-maker-frontend.vercel.app"
    )
    assert "access-control-allow-credentials" not in simple_response.headers
    assert simple_response.headers["access-control-expose-headers"] == "Content-Disposition"


@pytest.mark.asyncio
async def test_cors_does_not_allow_unconfigured_origin(cors_app) -> None:
    transport = ASGITransport(app=cors_app)
    origin = "https://sitio-no-autorizado.example"

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        simple_response = await client.get(
            "/docs",
            headers={"Origin": origin},
        )
        preflight_response = await client.options(
            "/api/v1/budgets/",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

    assert simple_response.status_code == 200
    assert "access-control-allow-origin" not in simple_response.headers
    assert preflight_response.status_code == 400
    assert "access-control-allow-origin" not in preflight_response.headers


def test_settings_normalizes_cors_allowed_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        (
            " https://budget-maker-frontend.vercel.app/, "
            "https://admin.example.com///, ,https://admin.example.com "
        ),
    )
    configured_settings = Settings(_env_file=None)

    assert configured_settings.cors_allowed_origins == [
        "https://budget-maker-frontend.vercel.app",
        "https://admin.example.com",
    ]


def test_settings_uses_exact_production_origin_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    configured_settings = Settings(_env_file=None)

    assert DEFAULT_CORS_ALLOWED_ORIGIN == (
        "https://budget-maker-frontend.vercel.app,http://localhost:3000,http://localhost:3001"
    )
    assert configured_settings.cors_allowed_origins == [
        "https://budget-maker-frontend.vercel.app",
        "http://localhost:3000",
        "http://localhost:3001",
    ]


@pytest.mark.asyncio
async def test_cors_allows_each_configured_origin() -> None:
    configured_settings = Settings(
        _env_file=None,
        cors_allowed_origins=(
            "https://budget-maker-frontend.vercel.app, "
            "https://admin.example.com/"
        ),
    )
    configured_app = create_app(configured_settings)
    transport = ASGITransport(app=configured_app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for origin in configured_settings.cors_allowed_origins:
            response = await client.options(
                "/api/v1/budgets/",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                },
            )

            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == origin


@pytest.mark.asyncio
async def test_legacy_mounts_support_independent_storage_directories(tmp_path) -> None:
    product_dir = tmp_path / "product-assets"
    branding_dir = tmp_path / "branding-assets"
    product_dir.mkdir()
    branding_dir.mkdir()
    (product_dir / "product.png").write_bytes(b"product")
    (branding_dir / "logo.png").write_bytes(b"logo")

    configured_settings = Settings(
        _env_file=None,
        upload_dir=str(product_dir),
        branding_dir=str(branding_dir),
    )
    configured_app = create_app(configured_settings)
    transport = ASGITransport(app=configured_app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        product_response = await client.get("/uploads/products/product.png")
        branding_response = await client.get("/uploads/branding/logo.png")

    assert product_response.status_code == 200
    assert product_response.content == b"product"
    assert branding_response.status_code == 200
    assert branding_response.content == b"logo"


def test_settings_rejects_empty_cors_allowed_origins() -> None:
    with pytest.raises(ValidationError, match="requiere al menos un origen"):
        Settings(_env_file=None, cors_allowed_origins=" , , ")


def test_settings_rejects_cors_wildcards() -> None:
    with pytest.raises(ValidationError, match="no permite patrones comodín"):
        Settings(_env_file=None, cors_allowed_origins="https://*.vercel.app")


@pytest.mark.parametrize(
    "invalid_origin",
    [
        "null",
        "budget-maker-frontend.vercel.app",
        "https://usuario:clave@example.com",
        "https://example.com/api",
        "https://example.com?tenant=1",
        "https://example.com#fragment",
    ],
)
def test_settings_rejects_invalid_cors_origins(invalid_origin: str) -> None:
    with pytest.raises(ValidationError, match="solo esquema, host y puerto"):
        Settings(_env_file=None, cors_allowed_origins=invalid_origin)


def test_settings_canonicalizes_cors_origin() -> None:
    configured_settings = Settings(
        _env_file=None,
        cors_allowed_origins="HTTPS://BUDGET-MAKER-FRONTEND.VERCEL.APP:443/",
    )

    assert configured_settings.cors_allowed_origins == [
        "https://budget-maker-frontend.vercel.app"
    ]
