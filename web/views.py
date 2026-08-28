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
PROJECT_ROOT_BASE_URL = Path(__file__).resolve().parents[1].as_uri() + "/"


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

    render_context = await uc.build_budget_render_context(budget, for_pdf=False)
    public_budget_url = str(request.url_for("view_budget", uuid=budget.uuid))
    whatsapp_url = await uc.generate_whatsapp_share_url(
        budget=budget,
        public_budget_url=public_budget_url,
        site_title=render_context["site_title"],
    )
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

    pdf_bytes = uc.generate_pdf(html_content, base_url=PROJECT_ROOT_BASE_URL)
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={budget.code}.pdf"},
    )
