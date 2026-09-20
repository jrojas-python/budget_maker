from datetime import datetime
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from io import BytesIO
from pathlib import Path
from fastapi import Request
from pydantic import UUID4

from app.application.use_cases.budget_use_cases import BudgetUseCases
from app.api.dependencies import get_budget_use_cases, get_current_user
from app.domain.models.budget import Budget, BudgetIdentifierCollisionError
from app.domain.models.user import User
from app.domain.schemas.budget import (
    BudgetAdminResponse,
    BudgetCreate,
    BudgetResponse,
    BudgetSearchParams,
    BudgetUpdate,
    BudgetWhatsappShareResponse,
)
from app.domain.schemas.search import PaginatedResponse

router = APIRouter(prefix="/api/v1/budgets", tags=["Presupuestos"])
templates = Jinja2Templates(directory="web/templates")
PROJECT_ROOT_BASE_URL = Path(__file__).resolve().parents[3].as_uri() + "/"


def _to_public_response(budget: Budget) -> BudgetResponse:
    return BudgetResponse(**budget.model_dump(exclude={"id", "client_id"}))


async def _to_admin_response(budget: Budget, uc: BudgetUseCases) -> BudgetAdminResponse:
    return BudgetAdminResponse(
        id=str(budget.id),
        client_id=str(budget.client_id) if budget.client_id else None,
        is_expired=await uc.is_expired(budget),
        **budget.model_dump(exclude={"id", "client_id"}),
    )


@router.get("/", response_model=PaginatedResponse[BudgetAdminResponse])
async def list_budgets(
    q: str | None = None,
    client_id: str | None = None,
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    is_expired: bool | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_user),
    uc: BudgetUseCases = Depends(get_budget_use_cases),
):
    params = BudgetSearchParams(
        q=q,
        client_id=client_id,
        date_from=date_from,
        date_to=date_to,
        is_expired=is_expired,
        page=page,
        limit=limit,
    )
    try:
        budgets, total = await uc.search(params)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    items = [await _to_admin_response(budget, uc) for budget in budgets]
    return PaginatedResponse[BudgetAdminResponse](
        items=items,
        total=total,
        page=page,
        limit=limit,
        pages=ceil(total / limit) if limit else 0,
    )


@router.post("/", response_model=BudgetResponse, status_code=201)
async def create_budget(
    body: BudgetCreate,
    _: User = Depends(get_current_user),
    uc: BudgetUseCases = Depends(get_budget_use_cases),
):
    try:
        budget = await uc.create_budget(body)
    except BudgetIdentifierCollisionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _to_public_response(budget)


@router.get("/{uuid}/admin", response_model=BudgetAdminResponse)
async def get_budget_admin(
    uuid: UUID4,
    _: User = Depends(get_current_user),
    uc: BudgetUseCases = Depends(get_budget_use_cases),
):
    budget = await uc.get_by_uuid(str(uuid))
    if not budget:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    return await _to_admin_response(budget, uc)


@router.put("/{uuid}", response_model=BudgetAdminResponse)
async def update_budget(
    uuid: UUID4,
    body: BudgetUpdate,
    _: User = Depends(get_current_user),
    uc: BudgetUseCases = Depends(get_budget_use_cases),
):
    try:
        budget = await uc.update_budget(str(uuid), body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not budget:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    return await _to_admin_response(budget, uc)


@router.delete("/{uuid}", status_code=204)
async def delete_budget(
    uuid: UUID4,
    _: User = Depends(get_current_user),
    uc: BudgetUseCases = Depends(get_budget_use_cases),
):
    if not await uc.delete_budget(str(uuid)):
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")


@router.get("/{uuid}", response_model=BudgetResponse)
async def get_budget(uuid: UUID4, uc: BudgetUseCases = Depends(get_budget_use_cases)):
    budget = await _get_active_budget_or_raise(uuid, uc)
    return _to_public_response(budget)


@router.get("/{uuid}/pdf")
async def download_budget_pdf(
    uuid: UUID4,
    request: Request,
    uc: BudgetUseCases = Depends(get_budget_use_cases),
):
    budget = await _get_active_budget_or_raise(uuid, uc)
    pdf_context = await uc.build_budget_render_context(budget, for_pdf=True)
    html_content = templates.get_template("public/budget_view.html").render(
        request=request,
        **pdf_context,
    )
    pdf_bytes = uc.generate_pdf(
        html_content,
        base_url=PROJECT_ROOT_BASE_URL,
    )
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={budget.code}.pdf"},
    )


@router.get("/{uuid}/whatsapp-share", response_model=BudgetWhatsappShareResponse)
async def get_budget_whatsapp_share(
    uuid: UUID4,
    request: Request,
    uc: BudgetUseCases = Depends(get_budget_use_cases),
):
    budget = await _get_active_budget_or_raise(uuid, uc)
    public_budget_url = str(request.url_for("view_budget", uuid=budget.uuid))
    whatsapp_url = await uc.generate_whatsapp_share_url(
        budget=budget,
        public_budget_url=public_budget_url,
    )
    return BudgetWhatsappShareResponse(whatsapp_url=whatsapp_url)


async def _get_active_budget_or_raise(uuid: UUID4, uc: BudgetUseCases) -> Budget:
    budget = await uc.get_by_uuid(str(uuid))
    if not budget:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    if await uc.is_expired(budget):
        raise HTTPException(status_code=410, detail="Presupuesto expirado")
    return budget
