from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_current_user, get_dashboard_use_cases
from app.application.use_cases.dashboard_use_cases import DashboardUseCases
from app.domain.models.user import User
from app.domain.schemas.dashboard import DashboardMetricsResponse

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@router.get("/metrics", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics(
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    top_limit: int = Query(10, ge=1, le=50),
    _: User = Depends(get_current_user),
    uc: DashboardUseCases = Depends(get_dashboard_use_cases),
):
    try:
        return await uc.get_metrics(
            date_from=date_from,
            date_to=date_to,
            top_limit=top_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc