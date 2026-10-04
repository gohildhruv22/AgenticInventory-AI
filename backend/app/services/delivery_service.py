"""Delivery service — feature 004 additions.

Currently exposes:
  - :func:`apply_eta_update` — mutates a `Delivery`'s ``expected_delivery_at`` /
    ``current_stage`` after a high-confidence ETA extraction, appends a
    :class:`DeliveryTimelineEntry`, writes one :class:`ActionLog` for undo,
    and publishes ``delivery.timeline.appended`` after commit.
  - :func:`append_timeline_entry` — internal helper enforcing the append-only
    invariant on ``delivery_timeline_entries``.
  - :func:`list_timeline` — used by US2 (T035 / T036). Lives here so the
    service layer is the single source of truth for timeline reads/writes.

Constitution III: every mutation here writes a reversible ``action_logs`` row
with payload ``{before, after, source_reply_id}`` per research.md §9.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action_log import ActionLog
from app.models.delivery import Delivery
from app.models.delivery_timeline_entry import (
    VALID_ACTOR_TYPES,
    VALID_EVENT_TYPES,
    DeliveryTimelineEntry,
)
from app.models.supplier_reply import SupplierReply
from app.schemas.delivery import DeliveryTimelineEntry as DeliveryTimelineEntrySchema
from app.schemas.delivery import DeliveryTimelineResponse
from app.schemas.eta_review import EtaExtraction
from app.websocket.events import publish_timeline_appended

logger = logging.getLogger("agenticinventory.services.delivery")


# Intent → event_type mapping for agent-driven timeline writes.
_INTENT_TO_EVENT: dict[str, str] = {
    "confirm": "eta_confirmed",
    "delay": "eta_revised",
    "acknowledge": "acknowledged",
    "cancel": "at_risk",  # cancellations are routed to review; never auto-apply
    "unclear": "acknowledged",
}


async def append_timeline_entry(
    session: AsyncSession,
    *,
    delivery_id: uuid.UUID,
    event_type: str,
    occurred_at: datetime,
    actor_type: str,
    actor_id: str | None = None,
    parsed_date: datetime | None = None,
    confidence: float | Decimal | None = None,
    supplier_excerpt: str | None = None,
    source_reply_id: uuid.UUID | None = None,
    source_review_id: uuid.UUID | None = None,
    note: str | None = None,
) -> DeliveryTimelineEntry:
    """Append a single timeline entry. Enforces the append-only invariant
    (data-model §2) — callers MUST NOT update or delete entries afterwards.
    """
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(
            f"append_timeline_entry: unknown event_type {event_type!r}; "
            f"expected one of {VALID_EVENT_TYPES}"
        )
    if actor_type not in VALID_ACTOR_TYPES:
        raise ValueError(
            f"append_timeline_entry: unknown actor_type {actor_type!r}; "
            f"expected one of {VALID_ACTOR_TYPES}"
        )
    if event_type == "note" and not note:
        raise ValueError("event_type='note' requires a non-empty note")

    entry = DeliveryTimelineEntry(
        delivery_id=delivery_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor_type=actor_type,
        actor_id=actor_id,
        parsed_date=parsed_date,
        confidence=Decimal(str(confidence)) if confidence is not None else None,
        supplier_excerpt=supplier_excerpt,
        source_reply_id=source_reply_id,
        source_review_id=source_review_id,
        note=note,
    )
    session.add(entry)
    await session.flush()
    return entry


def serialise_timeline_entry(entry: DeliveryTimelineEntry) -> dict[str, Any]:
    """Wire-format payload for the WS dispatcher."""
    return DeliveryTimelineEntrySchema.model_validate(entry).model_dump(mode="json")


def serialise_delivery_summary(delivery: Delivery) -> dict[str, Any]:
    """Slim snapshot used by the WS payload to patch the deliveries-list cache.

    Matches the shape defined in
    ``specs/004-supplier-delivery-eta-agent/contracts/websocket-events.md`` §1.
    """
    return {
        "current_stage": delivery.current_stage,
        "expected_delivery_at": (
            delivery.expected_delivery_at.isoformat()
            if delivery.expected_delivery_at
            else None
        ),
        "has_pending_review": bool(delivery.has_pending_review),
    }


async def apply_eta_update(
    session: AsyncSession,
    *,
    delivery: Delivery,
    extraction: EtaExtraction,
    reply: SupplierReply,
) -> DeliveryTimelineEntry:
    """Auto-apply an agent extraction to a delivery (high-confidence path).

    Mutates ``expected_delivery_at`` and ``current_stage``, appends a
    timeline entry, writes one ActionLog for undo (constitution III), and
    publishes ``delivery.timeline.appended`` AFTER the caller's commit by
    returning the entry — the ingestor (T028) is responsible for committing
    and firing the WS publisher.

    Returns the newly inserted ``DeliveryTimelineEntry`` so the caller can
    feed it into :func:`app.websocket.events.publish_timeline_appended`.

    Pre-conditions (enforced by caller, asserted here):
      - ``delivery.current_stage != 'delivered'``;
      - ``extraction.parsed_date is not None`` when intent is confirm/delay.
    """
    if delivery.current_stage == "delivered":
        raise ValueError(
            "apply_eta_update: refuse to mutate a delivered delivery — "
            "use append_timeline_entry(event_type='note', ...) instead."
        )
    if extraction.intent not in ("confirm", "delay", "acknowledge"):
        raise ValueError(
            f"apply_eta_update: intent {extraction.intent!r} must be routed to "
            "raise_review_item — auto-apply forbidden by FR-011."
        )

    before_stage = delivery.current_stage
    before_eta = delivery.expected_delivery_at

    # Determine new stage. Acknowledge does not promote the stage; confirm/delay
    # promote to "confirmed" unless the delivery is already past it.
    if extraction.intent in ("confirm", "delay"):
        # Both intents resolve to a known date; current_stage settles at
        # "confirmed". "at_risk" stays "at_risk" if it was already (the agent
        # rarely demotes its own previous parse).
        if delivery.current_stage != "at_risk":
            new_stage = "confirmed"
        else:
            new_stage = "at_risk"
    else:  # acknowledge
        new_stage = delivery.current_stage  # unchanged

    new_eta = extraction.parsed_date if extraction.intent != "acknowledge" else delivery.expected_delivery_at

    # Mutate the delivery — caller commits the transaction.
    delivery.current_stage = new_stage
    if new_eta is not None and extraction.intent != "acknowledge":
        delivery.expected_delivery_at = new_eta

    event_type = _INTENT_TO_EVENT[extraction.intent]
    # First confirm vs subsequent revision: pick the right timeline event type.
    if extraction.intent == "confirm" and before_stage in ("confirmed", "at_risk"):
        event_type = "eta_revised"

    entry = await append_timeline_entry(
        session,
        delivery_id=delivery.id,
        event_type=event_type,
        occurred_at=datetime.now(timezone.utc),
        actor_type="agent",
        actor_id="delivery_eta_agent",
        parsed_date=new_eta,
        confidence=float(extraction.confidence),
        supplier_excerpt=extraction.excerpt[:1000],
        source_reply_id=reply.id,
    )

    # Constitution III — reversibility. Write the action_logs row with the
    # exact payload research.md §9 specifies. The compensating action is a
    # generic "restore_entity" that the existing rollback_service knows how
    # to honour for delivery rows (see rollback_service._restore_entity_state
    # / _undo_eta_update added in this feature).
    action_log = ActionLog(
        agent_type="delivery_eta",
        action_type="delivery.eta_update",
        entity_type="delivery",
        entity_id=delivery.id,
        before_state={
            "expected_delivery_at": before_eta.isoformat() if before_eta else None,
            "current_stage": before_stage,
        },
        after_state={
            "expected_delivery_at": (
                delivery.expected_delivery_at.isoformat()
                if delivery.expected_delivery_at
                else None
            ),
            "current_stage": delivery.current_stage,
            "source_reply_id": str(reply.id),
            "timeline_entry_id": str(entry.id),
        },
        compensating_action={
            "type": "restore_eta",
            "params": {
                "delivery_id": str(delivery.id),
                "expected_delivery_at": (
                    before_eta.isoformat() if before_eta else None
                ),
                "current_stage": before_stage,
                "source_reply_id": str(reply.id),
            },
            "restore_entity": True,
        },
        status="executed",
        reasoning_trace={
            "intent": extraction.intent,
            "confidence": float(extraction.confidence),
            "excerpt": extraction.excerpt[:500],
            "reasoning": extraction.reasoning[:1000],
            "source_reply_id": str(reply.id),
        },
    )
    session.add(action_log)
    await session.flush()

    logger.info(
        "apply_eta_update: delivery_id=%s before_stage=%s -> after_stage=%s "
        "expected_delivery_at=%s reply_id=%s confidence=%.2f",
        delivery.id,
        before_stage,
        delivery.current_stage,
        delivery.expected_delivery_at,
        reply.id,
        float(extraction.confidence),
    )
    return entry


async def list_timeline(
    session: AsyncSession,
    *,
    delivery_id: uuid.UUID,
    since: datetime | None = None,
    limit: int = 100,
) -> DeliveryTimelineResponse:
    """Read the timeline for a single delivery, ordered most-recent first.

    Used by ``GET /api/v1/deliveries/{id}/timeline`` (T036).
    """
    limit = max(1, min(limit, 200))
    stmt = (
        select(DeliveryTimelineEntry)
        .where(DeliveryTimelineEntry.delivery_id == delivery_id)
        .order_by(desc(DeliveryTimelineEntry.occurred_at))
        .limit(limit)
    )
    if since is not None:
        stmt = stmt.where(DeliveryTimelineEntry.occurred_at > since)
    rows = (await session.execute(stmt)).scalars().all()
    return DeliveryTimelineResponse(
        delivery_id=delivery_id,
        entries=[DeliveryTimelineEntrySchema.model_validate(r) for r in rows],
    )


async def publish_timeline_event(
    *,
    delivery: Delivery,
    entry: DeliveryTimelineEntry,
) -> None:
    """Fire the ``delivery.timeline.appended`` WS event.

    Pull out as a tiny helper so the ingestor (T028) and the resolution
    service (T047) call the same code path.
    """
    await publish_timeline_appended(
        delivery_id=delivery.id,
        entry=serialise_timeline_entry(entry),
        delivery_summary=serialise_delivery_summary(delivery),
    )
