from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from app.domain.schemas.dashboard import (
    DashboardDailyPoint,
    DashboardMetricsResponse,
    DashboardPaymentMetric,
    DashboardPeriodCounts,
    DashboardProductMetric,
)
from app.infrastructure.repositories.budget_repo import BudgetRepository


class DashboardUseCases:
    """Orquesta métricas de presupuestos en periodos UTC."""

    _DEFAULT_DAYS = 30
    _MAX_RANGE_DAYS = 366

    def __init__(self, budget_repo: BudgetRepository) -> None:
        self._budget_repo = budget_repo

    async def get_metrics(
        self,
        *,
        date_from: datetime | None,
        date_to: datetime | None,
        top_limit: int,
    ) -> DashboardMetricsResponse:
        now = datetime.now(timezone.utc)
        end = self._as_utc(date_to) if date_to else now
        start = self._as_utc(date_from) if date_from else datetime.combine(
            end.date() - timedelta(days=self._DEFAULT_DAYS - 1),
            time.min,
            tzinfo=timezone.utc,
        )
        if start > end:
            raise ValueError("El inicio del rango no puede ser posterior al final")
        if (end.date() - start.date()).days >= self._MAX_RANGE_DAYS:
            raise ValueError(f"El rango máximo permitido es de {self._MAX_RANGE_DAYS} días")

        today_start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
        tomorrow_start = today_start + timedelta(days=1)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)
        next_month = (
            month_start.replace(year=month_start.year + 1, month=1)
            if month_start.month == 12
            else month_start.replace(month=month_start.month + 1)
        )

        today_count = await self._budget_repo.count_created_between(today_start, tomorrow_start)
        week_count = await self._budget_repo.count_created_between(week_start, tomorrow_start)
        month_count = await self._budget_repo.count_created_between(month_start, next_month)
        raw_daily = await self._budget_repo.aggregate_daily_counts(start, end)
        raw_clients = await self._budget_repo.aggregate_client_frequency(start, end)
        raw_products = await self._budget_repo.aggregate_top_products(start, end, top_limit)
        raw_payments = await self._budget_repo.aggregate_payment_methods(start, end)

        daily_by_date = {str(row["_id"]): int(row["count"]) for row in raw_daily}
        daily_series: list[DashboardDailyPoint] = []
        current_date = start.date()
        while current_date <= end.date():
            iso_date = current_date.isoformat()
            daily_series.append(
                DashboardDailyPoint(date=iso_date, count=daily_by_date.get(iso_date, 0))
            )
            current_date += timedelta(days=1)

        return DashboardMetricsResponse(
            from_date=start,
            to_date=end,
            counts=DashboardPeriodCounts(
                today=today_count,
                current_week=week_count,
                current_month=month_count,
            ),
            daily_series=daily_series,
            unique_clients=len(raw_clients),
            recurrent_clients=sum(1 for row in raw_clients if int(row["count"]) > 1),
            top_products=[
                DashboardProductMetric(
                    sku=str(row["_id"]["sku"]),
                    name=str(row["_id"]["name"]),
                    quantity=int(row["quantity"]),
                    amount=round(float(row["amount"]), 2),
                )
                for row in raw_products
            ],
            payment_methods=[
                DashboardPaymentMetric(
                    payment_method=str(row["_id"] or "Sin especificar"),
                    count=int(row["count"]),
                )
                for row in raw_payments
            ],
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)