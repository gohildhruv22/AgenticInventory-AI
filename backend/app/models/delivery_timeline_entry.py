"""DeliveryTimelineEntry — append-only log of events for a delivery.

See specs/004-supplier-delivery-eta-agent/data-model.md §2.

Append-only invariant: no UPDATE or DELETE is permitted on this table by
application code. The service layer is the enforcement point — see
``backend/app/services/eta_review_service.py`` (T035) for the gate.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models._types import UUIDType


# Valid event_type values (data-model §2). Kept as a tuple so callers can
# import and use it for runtime guards without touching the validator decorator.
VALID_EVENT_TYPES: tuple[str, ...] = (
    "eta_confirmed",
    "eta_revised",
    "acknowledged",
    "at_risk",
    "delivered",
    "manual_override",
    "note",
)

VALID_ACTOR_TYPES: tuple[str, ...] = ("agent", "admin", "simulator")


class DeliveryTimelineEntry(Base):
    __tablename__ = "delivery_timeline_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("deliveries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    actor_type: Mapped[str] = mapped_column(String(10), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    parsed_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    supplier_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_reply_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("supplier_replies.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_review_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("eta_review_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_delivery_timeline_delivery_occurred",
            "delivery_id",
            "occurred_at",
        ),
        Index("ix_delivery_timeline_source_reply", "source_reply_id"),
    )
