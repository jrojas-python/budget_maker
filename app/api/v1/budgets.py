from fastapi import APIRouter, Depends, HTTPException

from app.application.use_cases.budget_use_cases import BudgetUseCases
from app.api.dependencies import get_budget_use_cases
from app.domain.schemas.budget import BudgetCreate, BudgetResponse

router = APIRouter(prefix="/api/v1/budgets", tags=["Presupuestos"])


@router.get("/", response_model=list[BudgetResponse])
async def list_budgets(uc: BudgetUseCases = Depends(get_budget_use_cases)):
    budgets = await uc._budget_repo.get_all()
    return [
        BudgetResponse(
            code=b.code, uuid=b.uuid, client_info=b.client_info,
            items=b.items, subtotal=b.subtotal, tax_percent=b.tax_percent,
            tax_amount=b.tax_amount, total=b.total, created_at=b.created_at,
        )
        for b in budgets
    ]


@router.post("/", response_model=BudgetResponse, status_code=201)
async def create_budget(body: BudgetCreate, uc: BudgetUseCases = Depends(get_budget_use_cases)):
    try:
        budget = await uc.create_budget(body)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return BudgetResponse(
        code=budget.code, uuid=budget.uuid, client_info=budget.client_info,
        items=budget.items, subtotal=budget.subtotal, tax_percent=budget.tax_percent,
        tax_amount=budget.tax_amount, total=budget.total, created_at=budget.created_at,
    )


@router.get("/{uuid}", response_model=BudgetResponse)
async def get_budget(uuid: str, uc: BudgetUseCases = Depends(get_budget_use_cases)):
    budget = await uc.get_by_uuid(uuid)
    if not budget:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    return BudgetResponse(
        code=budget.code, uuid=budget.uuid, client_info=budget.client_info,
        items=budget.items, subtotal=budget.subtotal, tax_percent=budget.tax_percent,
        tax_amount=budget.tax_amount, total=budget.total, created_at=budget.created_at,
    )
