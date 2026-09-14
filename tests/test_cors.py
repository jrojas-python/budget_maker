from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from main import app
from settings.config import DEFAULT_CORS_ALLOWED_ORIGIN, Settings


@pytest.fixture
def _init_db() -> None:
    """Evita iniciar MongoDB en estas pruebas aisladas de middleware."""


@pytest.fixture(autouse=True)
def _clean_collections() -> None:
    """Evita la limpieza de MongoDB en estas pruebas aisladas."""


@pytest.mark.asyncio
async def test_cors_allows_vercel_production_preflight() -> None:
    transport = ASGITransport(app=app)
    headers = {
        "Origin": DEFAULT_CORS_ALLOWED_ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    }

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        preflight_response = await client.options("/api/v1/budgets/", headers=headers)
        simple_response = await client.get(
            "/docs",
            headers={"Origin": DEFAULT_CORS_ALLOWED_ORIGIN},
        )

    assert preflight_response.status_code == 200
    assert preflight_response.headers["access-control-allow-origin"] == DEFAULT_CORS_ALLOWED_ORIGIN
    assert "POST" in preflight_response.headers["access-control-allow-methods"]
    assert "authorization" in preflight_response.headers["access-control-allow-headers"].lower()
    assert "content-type" in preflight_response.headers["access-control-allow-headers"].lower()
    assert simple_response.status_code == 200
    assert simple_response.headers["access-control-allow-origin"] == DEFAULT_CORS_ALLOWED_ORIGIN


@pytest.mark.asyncio
async def test_cors_does_not_allow_unconfigured_origin() -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/docs",
            headers={"Origin": "https://sitio-no-autorizado.example"},
        )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


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


def test_settings_rejects_cors_wildcards() -> None:
    with pytest.raises(ValidationError, match="no permite patrones comodín"):
        Settings(_env_file=None, cors_allowed_origins="https://*.vercel.app")
