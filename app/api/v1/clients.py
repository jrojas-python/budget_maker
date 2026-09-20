from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_client_use_cases, get_current_user
from app.application.use_cases.client_use_cases import ClientUseCases
from app.domain.models.client import Client
from app.domain.models.user import User
from app.domain.schemas.client import ClientCreate, ClientResponse, ClientUpdate
from app.domain.schemas.search import PaginatedResponse

router = APIRouter(prefix="/api/v1/clients", tags=["Clientes"])


def _to_response(client: Client) -> ClientResponse:
    return ClientResponse(id=str(client.id), **client.model_dump(exclude={"id"}))


@router.get("/", response_model=PaginatedResponse[ClientResponse])
async def list_clients(
    q: str | None = None,
    active_only: bool = True,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_user),
    uc: ClientUseCases = Depends(get_client_use_cases),
):
    items, total = await uc.search(
        q=q,
        active_only=active_only,
        page=page,
        limit=limit,
    )
    return PaginatedResponse[ClientResponse].build(
        items=[_to_response(client) for client in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("/", response_model=ClientResponse, status_code=201)
async def create_client(
    body: ClientCreate,
    _: User = Depends(get_current_user),
    uc: ClientUseCases = Depends(get_client_use_cases),
):
    try:
        return _to_response(await uc.create(body))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: str,
    _: User = Depends(get_current_user),
    uc: ClientUseCases = Depends(get_client_use_cases),
):
    client = await uc.get_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return _to_response(client)


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: str,
    body: ClientUpdate,
    _: User = Depends(get_current_user),
    uc: ClientUseCases = Depends(get_client_use_cases),
):
    try:
        client = await uc.update(client_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return _to_response(client)


@router.delete("/{client_id}", status_code=204)
async def delete_client(
    client_id: str,
    _: User = Depends(get_current_user),
    uc: ClientUseCases = Depends(get_client_use_cases),
):
    if not await uc.delete(client_id):
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
