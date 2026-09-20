from __future__ import annotations

import pytest
from httpx import AsyncClient


def _client_payload(**overrides: str) -> dict[str, str]:
    payload = {
        "nombres": "Ana",
        "apellidos": "Rojas",
        "email": "ana@example.com",
        "documento": " ab 123 ",
        "compania": "Acme",
        "direccion": "Calle 1",
        "observaciones": "Cliente preferente",
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_clients_require_authentication(client: AsyncClient):
    assert (await client.get("/api/v1/clients/")).status_code == 401
    assert (await client.post("/api/v1/clients/", json={"nombres": "Ana"})).status_code == 401
    client_id = "000000000000000000000001"
    assert (await client.get(f"/api/v1/clients/{client_id}")).status_code == 401
    assert (
        await client.put(f"/api/v1/clients/{client_id}", json={"nombres": "Ana"})
    ).status_code == 401
    assert (await client.delete(f"/api/v1/clients/{client_id}")).status_code == 401


@pytest.mark.asyncio
async def test_client_crud_search_and_soft_delete(client: AsyncClient, auth_headers: dict):
    created = await client.post("/api/v1/clients/", json=_client_payload())
    assert created.status_code == 201
    client_data = created.json()
    assert client_data["documento"] == "AB123"
    assert client_data["is_active"] is True

    searched = await client.get("/api/v1/clients/?q=acme")
    assert searched.status_code == 200
    assert searched.json()["total"] == 1
    assert searched.json()["items"][0]["id"] == client_data["id"]

    updated = await client.put(
        f"/api/v1/clients/{client_data['id']}",
        json={"compania": "Nueva Compañía", "observaciones": "Actualizada"},
    )
    assert updated.status_code == 200
    assert updated.json()["compania"] == "Nueva Compañía"

    deleted = await client.delete(f"/api/v1/clients/{client_data['id']}")
    assert deleted.status_code == 204
    assert (await client.get("/api/v1/clients/")).json()["total"] == 0

    including_inactive = await client.get("/api/v1/clients/?active_only=false")
    assert including_inactive.json()["total"] == 1
    assert including_inactive.json()["items"][0]["is_active"] is False


@pytest.mark.asyncio
async def test_client_document_is_unique_after_normalization(
    client: AsyncClient,
    auth_headers: dict,
):
    first = await client.post("/api/v1/clients/", json=_client_payload())
    assert first.status_code == 201

    duplicate = await client.post(
        "/api/v1/clients/",
        json=_client_payload(nombres="Otra", documento="AB123"),
    )
    assert duplicate.status_code == 409


@pytest.mark.asyncio
async def test_multiple_clients_without_document_are_allowed(
    client: AsyncClient,
    auth_headers: dict,
):
    first = await client.post(
        "/api/v1/clients/",
        json={"nombres": "Ana", "documento": ""},
    )
    second = await client.post(
        "/api/v1/clients/",
        json={"nombres": "Beatriz", "documento": ""},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert (await client.get("/api/v1/clients/")).json()["total"] == 2


@pytest.mark.asyncio
async def test_client_document_can_be_cleared_when_other_empty_documents_exist(
    client: AsyncClient,
    auth_headers: dict,
):
    with_document = await client.post(
        "/api/v1/clients/",
        json={"nombres": "Ana", "documento": "A-1"},
    )
    without_document = await client.post(
        "/api/v1/clients/",
        json={"nombres": "Beatriz", "documento": ""},
    )
    assert with_document.status_code == 201
    assert without_document.status_code == 201

    updated = await client.put(
        f"/api/v1/clients/{with_document.json()['id']}",
        json={"documento": ""},
    )
    assert updated.status_code == 200
    assert updated.json()["documento"] == ""


@pytest.mark.asyncio
async def test_client_update_rejects_explicit_nulls(
    client: AsyncClient,
    auth_headers: dict,
):
    created = await client.post("/api/v1/clients/", json=_client_payload())
    assert created.status_code == 201

    for field in ("nombres", "documento", "compania"):
        response = await client.put(
            f"/api/v1/clients/{created.json()['id']}",
            json={field: None},
        )
        assert response.status_code == 422