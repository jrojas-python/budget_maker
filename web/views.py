import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from io import BytesIO
from pathlib import Path

from app.application.use_cases.budget_use_cases import BudgetUseCases
from app.api.dependencies import get_budget_use_cases

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Web - Presupuestos"])
templates = Jinja2Templates(directory="web/templates")


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("public/catalog.html", {"request": request})


@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login(request: Request):
    return templates.TemplateResponse("admin/login.html", {"request": request})


@router.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    return templates.TemplateResponse("admin/dashboard.html", {"request": request})


@router.get("/presupuesto/{uuid}", response_class=HTMLResponse)
async def view_budget(uuid: str, request: Request, uc: BudgetUseCases = Depends(get_budget_use_cases)):
    """Vista HTML del presupuesto con validación de expiración."""
    budget = await uc.get_by_uuid(uuid)
    if not budget:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    if await uc.is_expired(budget):
        return templates.TemplateResponse("public/budget_expired.html", {"request": request, "code": budget.code})

    whatsapp_url = uc.generate_whatsapp_text(budget)
    render_context = await uc.build_budget_render_context(budget, for_pdf=False)
    return templates.TemplateResponse(
        "public/budget_view.html",
        {
            "request": request,
            **render_context,
            "is_pdf": False,
            "whatsapp_url": whatsapp_url,
        },
    )


@router.get("/presupuesto/{uuid}/pdf")
async def download_budget_pdf(uuid: str, request: Request, uc: BudgetUseCases = Depends(get_budget_use_cases)):
    """Genera y descarga el PDF del presupuesto."""
    budget = await uc.get_by_uuid(uuid)
    if not budget:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    if await uc.is_expired(budget):
        raise HTTPException(status_code=410, detail="Presupuesto expirado")

    render_context = await uc.build_budget_render_context(budget, for_pdf=True)
    html_content = templates.get_template("public/budget_view.html").render(
        request=request,
        **render_context,
    )

    pdf_bytes = uc.generate_pdf(html_content, base_url=(Path.cwd().resolve().as_uri() + "/"))
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={budget.code}.pdf"},
    )
