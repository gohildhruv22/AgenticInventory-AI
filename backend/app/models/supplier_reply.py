"""SupplierReply — inbound parsed mail from a supplier.

See specs/004-supplier-delivery-eta-agent/data-model.md §1.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Iterable

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.database import Base
from app.models._types import JSONType, UUIDType

# Allowed processing_status transitions (data-model §1).
_ALLOWED_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "new": frozenset({"parsed", "ignored", "failed"}),
    "parsed": frozenset({"applied", "in_review", "failed"}),
    "in_review": frozenset({"applied", "ignored"}),
    # terminal:
    "applied": frozenset(),
    "ignored": frozenset(),
    "failed": frozenset(),
}

_VALID_STATUSES: frozenset[str] = frozenset(_ALLOWED_STATUS_TRANSITIONS.keys())


class SupplierReply(Base):
    __tablename__ = "supplier_replies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    message_id: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    from_address: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(998), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    body_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    raw_headers: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    matched_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("supplier_orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    matched_delivery_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("deliveries.id", ondelete="SET NULL"),
        nullable=True,
    )
    processing_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="new", index=True
    )
    agent_response: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_supplier_replies_status_created",
            "processing_status",
            "created_at",
        ),
        Index("ix_supplier_replies_matched_delivery", "matched_delivery_id"),
    )

    # --- validation ----------------------------------------------------------

    @validates("processing_status")
    def _validate_processing_status(self, _key: str, new_value: str) -> str:
        if new_value not in _VALID_STATUSES:
            raise ValueError(
                f"SupplierReply.processing_status: unknown value {new_value!r}; "
                f"expected one of {sorted(_VALID_STATUSES)}"
            )
        # First assignment (instance not yet persisted with a prior value): allow any.
        current = getattr(self, "processing_status", None)
        if current is None or current == new_value:
            return new_value
        allowed: Iterable[str] = _ALLOWED_STATUS_TRANSITIONS.get(current, frozenset())
        if new_value not in allowed:
            raise ValueError(
                f"SupplierReply.processing_status: illegal transition "
                f"{current!r} -> {new_value!r}"
            )
        return new_value
