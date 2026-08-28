from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from io import BytesIO
from pathlib import Path
from fastapi import Request
from pydantic import UUID4

from app.application.use_cases.budget_use_cases import BudgetUseCases
from app.api.dependencies import get_budget_use_cases
from app.domain.models.budget import Budget, BudgetIdentifierCollisionError
from app.domain.schemas.budget import BudgetCreate, BudgetResponse, BudgetWhatsappShareResponse

router = APIRouter(prefix="/api/v1/budgets", tags=["Presupuestos"])
templates = Jinja2Templates(directory="web/templates")
PROJECT_ROOT_BASE_URL = Path(__file__).resolve().parents[3].as_uri() + "/"


@router.get("/", response_model=list[BudgetResponse])
async def list_budgets(uc: BudgetUseCases = Depends(get_budget_use_cases)):
    budgets = await uc._budget_repo.get_all()
    return [
        BudgetResponse(
            code=b.code, uuid=b.uuid, client_info=b.client_info,
            items=b.items, subtotal=b.subtotal, tax_percent=b.tax_percent,
            tax_amount=b.tax_amount, total=b.total, payment_method=b.payment_method,
            link_ttl_minutes=b.link_ttl_minutes, created_at=b.created_at,
            expires_at=b.expires_at,
        )
        for b in budgets
    ]


@router.post("/", response_model=BudgetResponse, status_code=201)
async def create_budget(
    body: BudgetCreate,
    uc: BudgetUseCases = Depends(get_budget_use_cases),
):
    try:
        budget = await uc.create_budget(body)
    except BudgetIdentifierCollisionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return BudgetResponse(
        code=budget.code, uuid=budget.uuid, client_info=budget.client_info,
        items=budget.items, subtotal=budget.subtotal, tax_percent=budget.tax_percent,
        tax_amount=budget.tax_amount, total=budget.total, payment_method=budget.payment_method,
        link_ttl_minutes=budget.link_ttl_minutes, created_at=budget.created_at,
        expires_at=budget.expires_at,
    )


@router.get("/{uuid}", response_model=BudgetResponse)
async def get_budget(uuid: UUID4, uc: BudgetUseCases = Depends(get_budget_use_cases)):
    budget = await _get_active_budget_or_raise(uuid, uc)
    return BudgetResponse(
        code=budget.code, uuid=budget.uuid, client_info=budget.client_info,
        items=budget.items, subtotal=budget.subtotal, tax_percent=budget.tax_percent,
        tax_amount=budget.tax_amount, total=budget.total, payment_method=budget.payment_method,
        link_ttl_minutes=budget.link_ttl_minutes, created_at=budget.created_at,
        expires_at=budget.expires_at,
    )


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
