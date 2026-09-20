from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DashboardPeriodCounts(BaseModel):
    today: int
    current_week: int
    current_month: int


class DashboardDailyPoint(BaseModel):
    date: str
    count: int


class DashboardProductMetric(BaseModel):
    sku: str
    name: str
    quantity: int
    amount: float


class DashboardPaymentMetric(BaseModel):
    payment_method: str
    count: int


class DashboardMetricsResponse(BaseModel):
    from_date: datetime
    to_date: datetime
    counts: DashboardPeriodCounts
    daily_series: list[DashboardDailyPoint]
    unique_clients: int
    recurrent_clients: int
    top_products: list[DashboardProductMetric]
    payment_methods: list[DashboardPaymentMetric]