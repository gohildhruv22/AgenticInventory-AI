from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Mirrors specs/004-supplier-delivery-eta-agent/contracts/deliveries-timeline.openapi.yaml
EventType = Literal[
    "eta_confirmed",
    "eta_revised",
    "acknowledged",
    "at_risk",
    "delivered",
    "manual_override",
    "note",
]
ActorType = Literal["agent", "admin", "simulator"]


class DeliveryTimelineEntry(BaseModel):
    """A single append-only event on a delivery's timeline."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    delivery_id: UUID
    event_type: EventType
    occurred_at: datetime
    actor_type: ActorType
    actor_id: str | None = None
    parsed_date: datetime | None = None
    confidence: Decimal | None = Field(default=None, ge=0, le=100)
    supplier_excerpt: str | None = Field(default=None, max_length=1000)
    source_reply_id: UUID | None = None
    source_review_id: UUID | None = None
    note: str | None = None
    created_at: datetime


class DeliveryTimelineResponse(BaseModel):
    """Envelope for GET /deliveries/{id}/timeline."""

    delivery_id: UUID
    entries: list[DeliveryTimelineEntry]


class DeliveryResponse(BaseModel):
    id: UUID
    order_id: UUID
    current_stage: str
    stage_history: list[dict[str, Any]]
    expected_delivery_at: datetime | None
    actual_delivery_at: datetime | None
    items_received: list[dict[str, Any]] | dict[str, Any] | None
    # Feature 004 additions (see contracts/deliveries-timeline.openapi.yaml).
    has_pending_review: bool = False
    latest_timeline_entry: DeliveryTimelineEntry | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeliveryListResponse(BaseModel):
    deliveries: list[DeliveryResponse]
    total: int
    page: int
    per_page: int
    pages: int
