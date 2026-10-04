from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class KPIReportResponse(BaseModel):
    id: UUID
    report_date: date
    order_volume: int
    total_spend: Decimal
    forecast_accuracy: Decimal | None
    avg_confidence_score: Decimal | None
    decisions_approved: int
    decisions_flagged: int
    decisions_rolled_back: int
    deliveries_completed: int
    deliveries_failed: int
    supplier_performance: dict[str, Any]
    agent_activity: dict[str, Any]
    email_delivery_rate: Decimal | None
    cost_savings_estimate: Decimal | None
    email_sent: bool
    email_sent_at: datetime | None = None
    email_recipients: list[str] | dict[str, Any] = []
    report_data: dict[str, Any] = {}
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    reports: list[KPIReportResponse]
    total: int
    page: int
    per_page: int
    pages: int


class DashboardMetrics(BaseModel):
    order_volume: int = 0
    total_spend: Decimal = Decimal("0")
    forecast_accuracy: float | None = None
    avg_confidence: float | None = None
    decisions_approved: int = 0
    decisions_flagged: int = 0
    active_deliveries: int = 0
    low_stock_count: int = 0
