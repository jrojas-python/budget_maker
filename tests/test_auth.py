import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_ok(client: AsyncClient):
    from app.api.dependencies import get_auth_use_cases
    await get_auth_use_cases().seed_superadmin()

    res = await client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "admin1234",
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_fail(client: AsyncClient):
    res = await client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "wrongpassword",
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me_without_token(client: AsyncClient):
    res = await client.get("/api/v1/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me_with_token(client: AsyncClient, auth_headers: dict):
    res = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "admin"
    assert data["is_active"] is True
