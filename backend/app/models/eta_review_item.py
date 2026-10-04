"""EtaReviewItem — admin review queue for low-confidence/unmatched supplier replies.

See specs/004-supplier-delivery-eta-agent/data-model.md §3.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.database import Base
from app.models._types import JSONType, UUIDType


VALID_INTENTS: tuple[str, ...] = (
    "confirm",
    "delay",
    "cancel",
    "acknowledge",
    "unclear",
)

VALID_RAISED_REASONS: tuple[str, ...] = (
    "low_confidence",
    "unmatched_order",
    "ambiguous_match",
    "negative_intent",
    "past_date",
    "non_english",
)

# Allowed resolution_state transitions (terminal once non-pending).
_ALLOWED_RESOLUTION_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"approved", "corrected", "dismissed"}),
    "approved": frozenset(),
    "corrected": frozenset(),
    "dismissed": frozenset(),
}

_VALID_RESOLUTIONS: frozenset[str] = frozenset(_ALLOWED_RESOLUTION_TRANSITIONS.keys())


class EtaReviewItem(Base):
    __tablename__ = "eta_review_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    supplier_reply_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("supplier_replies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    candidate_delivery_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("deliveries.id", ondelete="SET NULL"),
        nullable=True,
    )
    candidate_order_ids: Mapped[list] = mapped_column(
        JSONType, nullable=False, default=list
    )
    agent_intent: Mapped[str] = mapped_column(String(20), nullable=False)
    agent_parsed_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    agent_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    agent_reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    raised_reason: Mapped[str] = mapped_column(String(40), nullable=False)
    resolution_state: Mapped[str] = mapped_column(
        String(15), nullable=False, default="pending"
    )
    resolved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resolution_payload: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    raised_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_eta_review_state_raised",
            "resolution_state",
            "raised_at",
        ),
        Index("ix_eta_review_candidate_delivery", "candidate_delivery_id"),
    )

    # --- validation ----------------------------------------------------------

    @validates("resolution_state")
    def _validate_resolution_state(self, _key: str, new_value: str) -> str:
        if new_value not in _VALID_RESOLUTIONS:
            raise ValueError(
                f"EtaReviewItem.resolution_state: unknown value {new_value!r}; "
                f"expected one of {sorted(_VALID_RESOLUTIONS)}"
            )
        current = getattr(self, "resolution_state", None)
        if current is None or current == new_value:
            return new_value
        allowed: Iterable[str] = _ALLOWED_RESOLUTION_TRANSITIONS.get(
            current, frozenset()
        )
        if new_value not in allowed:
            raise ValueError(
                f"EtaReviewItem.resolution_state: illegal transition "
                f"{current!r} -> {new_value!r}"
            )
        return new_value
