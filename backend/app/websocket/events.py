"""Typed WebSocket event publishers for feature 004.

Defines the three new event types introduced by the Supplier Delivery ETA
Agent — see
``specs/004-supplier-delivery-eta-agent/contracts/websocket-events.md`` for
the wire contract.

All publishers MUST be ordered correctly by their caller:
  - ``eta_review.raised``  → published BEFORE ``delivery.timeline.appended``
    for the ``acknowledged`` / ``at_risk`` entry written by the same ingestor
    cycle.
  - ``eta_review.resolved`` → published AFTER ``delivery.timeline.appended``
    for the resolution entry, so the timeline is consistent the moment the
    review toast/inbox refresh fires.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.websocket.manager import ws_manager

logger = logging.getLogger("agenticinventory.websocket.events")


# Event names — exported so other modules and tests can import the constants
# rather than re-typing the wire strings.
EVENT_DELIVERY_TIMELINE_APPENDED = "delivery.timeline.appended"
EVENT_ETA_REVIEW_RAISED = "eta_review.raised"
EVENT_ETA_REVIEW_RESOLVED = "eta_review.resolved"

# Default broadcast room. The existing dispatcher uses a single "general"
# room; feature 004 reuses it so no client-side routing change is required.
_DEFAULT_ROOM = "general"


def _envelope(data: dict[str, Any]) -> dict[str, Any]:
    """Wrap a payload with the standard envelope timestamp.

    The ConnectionManager adds the `event` and `data` keys itself when it
    serialises, so this helper only attaches the ISO timestamp that the
    contract requires next to every event.
    """
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **data,
    }


def _coerce_uuid(value: UUID | str | None) -> str | None:
    if value is None:
        return None
    return str(value)


async def publish_timeline_appended(
    *,
    delivery_id: UUID | str,
    entry: dict[str, Any],
    delivery_summary: dict[str, Any] | None = None,
    room: str = _DEFAULT_ROOM,
) -> None:
    """Publish ``delivery.timeline.appended``.

    Called by the service layer immediately after a
    ``DeliveryTimelineEntry`` row is committed (regardless of source —
    agent, admin, simulator, or manual override).
    """
    payload = _envelope(
        {
            "delivery_id": _coerce_uuid(delivery_id),
            "entry": entry,
            "delivery_summary": delivery_summary,
        }
    )
    logger.debug(
        "ws publish %s delivery_id=%s entry_id=%s",
        EVENT_DELIVERY_TIMELINE_APPENDED,
        delivery_id,
        entry.get("id"),
    )
    await ws_manager.broadcast(room, EVENT_DELIVERY_TIMELINE_APPENDED, payload)


async def publish_eta_review_raised(
    *,
    review: dict[str, Any],
    candidate_delivery_id: UUID | str | None,
    room: str = _DEFAULT_ROOM,
) -> None:
    """Publish ``eta_review.raised``.

    Called by the ingestor when a new ``EtaReviewItem`` row is committed.
    MUST be called BEFORE the corresponding
    :func:`publish_timeline_appended` call for the same ingestor cycle.
    """
    payload = _envelope(
        {
            "review": review,
            "candidate_delivery_id": _coerce_uuid(candidate_delivery_id),
        }
    )
    logger.debug(
        "ws publish %s review_id=%s candidate_delivery_id=%s",
        EVENT_ETA_REVIEW_RAISED,
        review.get("id"),
        candidate_delivery_id,
    )
    await ws_manager.broadcast(room, EVENT_ETA_REVIEW_RAISED, payload)


async def publish_eta_review_resolved(
    *,
    review: dict[str, Any],
    delivery_id: UUID | str | None,
    delivery_summary: dict[str, Any] | None = None,
    room: str = _DEFAULT_ROOM,
) -> None:
    """Publish ``eta_review.resolved``.

    Called by the eta_review service when an admin approves, corrects, or
    dismisses a review item. MUST be called AFTER the matching
    :func:`publish_timeline_appended` call (when one is produced).
    """
    payload = _envelope(
        {
            "review": review,
            "delivery_id": _coerce_uuid(delivery_id),
            "delivery_summary": delivery_summary,
        }
    )
    logger.debug(
        "ws publish %s review_id=%s delivery_id=%s",
        EVENT_ETA_REVIEW_RESOLVED,
        review.get("id"),
        delivery_id,
    )
    await ws_manager.broadcast(room, EVENT_ETA_REVIEW_RESOLVED, payload)


__all__ = [
    "EVENT_DELIVERY_TIMELINE_APPENDED",
    "EVENT_ETA_REVIEW_RAISED",
    "EVENT_ETA_REVIEW_RESOLVED",
    "publish_timeline_appended",
    "publish_eta_review_raised",
    "publish_eta_review_resolved",
]
