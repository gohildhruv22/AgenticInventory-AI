import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from app.models._types import JSONType, UUIDType
from sqlalchemy.orm import Mapped, mapped_column


from app.database import Base


class Delivery(Base):
    __tablename__ = "deliveries"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUIDType(as_uuid=True), nullable=False, unique=True, index=True)
    # current_stage: legacy values {"ordered", "pending", "in_transit", "delivered"} are
    # joined by feature 004 values {"confirmed", "at_risk"} produced by the ETA agent
    # and admin overrides (see specs/004-supplier-delivery-eta-agent/data-model.md §4).
    current_stage: Mapped[str] = mapped_column(String(30), nullable=False, default="ordered", index=True)
    stage_history: Mapped[dict] = mapped_column(JSONType, nullable=False, default=list)
    expected_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    items_received: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    simulation_config: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    # Feature 004: materialised flag synchronised by the eta_review service.
    has_pending_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0", index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
