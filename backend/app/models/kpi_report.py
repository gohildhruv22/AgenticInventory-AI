import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, func
from app.models._types import JSONType, UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class KPIReport(Base):
    __tablename__ = "kpi_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    order_volume: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_spend: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    forecast_accuracy: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    avg_confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    decisions_approved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    decisions_flagged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    decisions_rolled_back: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deliveries_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deliveries_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    supplier_performance: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    agent_activity: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    email_delivery_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    cost_savings_estimate: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    email_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_recipients: Mapped[dict] = mapped_column(JSONType, nullable=False, default=list)
    report_data: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
