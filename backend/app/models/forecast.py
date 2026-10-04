import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Integer, Numeric, String, Text, func
from app.models._types import JSONType, UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(UUIDType(as_uuid=True), nullable=False, index=True)
    predicted_demand: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    suggested_order_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    trends_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    trend_direction: Mapped[str | None] = mapped_column(String(20), nullable=True)
    news_sentiment: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    weather_impact: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    holiday_proximity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    holiday_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    staleness_flags: Mapped[dict] = mapped_column(JSONType, nullable=False, default=list)
    raw_signals: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    __table_args__ = (
        Index("ix_forecast_item_date", "inventory_item_id", created_at.desc()),
    )
