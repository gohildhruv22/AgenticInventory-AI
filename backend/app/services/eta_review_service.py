"""ETA review service — creates and serialises `EtaReviewItem` rows.

Currently exposes:
  - :func:`raise_review_item` — called by the ingestor when an extraction
    is *not* eligible for auto-apply (low confidence, ambiguous match,
    cancel intent, past date, non-English …) — see FR-011.
  - :func:`serialise_review_summary` — builds the wire payload consumed by
    the WS dispatcher and the REST list endpoint (US3 / T044).

Constitution III: every newly raised review item also writes a single
``delivery_timeline_entries`` row (``acknowledged`` or ``at_risk``) so the
delivery's timeline reflects the supplier's signal even before an admin
resolves the review. The append-only invariant holds.
"""
from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.delivery import Delivery
from app.models.delivery_timeline_entry import DeliveryTimelineEntry
from app.models.eta_review_item import VALID_INTENTS, VALID_RAISED_REASONS, EtaReviewItem
from app.models.supplier_reply import SupplierReply
from app.schemas.eta_review import (
    EtaExtraction,
    EtaReviewCorrectRequest,
    EtaReviewDetailResponse,
    EtaReviewDismissRequest,
    EtaReviewListResponse,
    EtaReviewResolutionPayload,
    EtaReviewSummary,
    SupplierReplyEmbedded,
)
from app.services.delivery_service import (
    append_timeline_entry,
    apply_eta_update,
    serialise_delivery_summary,
)

logger = logging.getLogger("agenticinventory.services.eta_review")


# Mapping from extraction intent → timeline event_type when raising a review.
# - Negative signals (cancel/delay/past-date) flag the delivery as at_risk.
# - Everything else gets a generic "acknowledged" marker so the timeline
#   shows the supplier responded even though the agent isn't sure.
_INTENT_TO_REVIEW_EVENT: dict[str, str] = {
    "cancel": "at_risk",
    "delay": "at_risk",
    "confirm": "acknowledged",
    "acknowledge": "acknowledged",
    "unclear": "acknowledged",
}

_AT_RISK_REASONS: frozenset[str] = frozenset({"negative_intent", "past_date"})


async def raise_review_item(
    session: AsyncSession,
    *,
    reply: SupplierReply,
    extraction: EtaExtraction,
    raised_reason: str,
    candidate_delivery: Delivery | None,
    candidate_order_ids: list[uuid.UUID] | None = None,
) -> tuple[EtaReviewItem, DeliveryTimelineEntry | None]:
    """Insert a new ``eta_review_items`` row and (optionally) append a
    timeline entry on the candidate delivery.

    Pre-conditions:
      - ``reply.processing_status == 'parsed'`` (caller already wrote the
        reply row with extraction metadata stashed in ``agent_response``);
      - The caller will set the reply's status to ``'in_review'`` after
        commit — we just return the inserted review row.

    Returns ``(review, timeline_entry_or_None)``. ``timeline_entry`` is
    ``None`` when no candidate delivery was matched (FR-014: unmatched
    replies still raise a review item but produce no timeline write).

    Caller is responsible for committing the session and firing the
    ``eta_review.raised`` WS event AFTER commit (publisher MUST fire
    BEFORE the timeline publisher per the WS contract).
    """
    if raised_reason not in VALID_RAISED_REASONS:
        raise ValueError(
            f"raise_review_item: unknown raised_reason {raised_reason!r}; "
            f"expected one of {VALID_RAISED_REASONS}"
        )
    if extraction.intent not in VALID_INTENTS:
        raise ValueError(
            f"raise_review_item: unknown intent {extraction.intent!r}; "
            f"expected one of {VALID_INTENTS}"
        )

    review = EtaReviewItem(
        supplier_reply_id=reply.id,
        candidate_delivery_id=candidate_delivery.id if candidate_delivery else None,
        candidate_order_ids=[str(x) for x in (candidate_order_ids or [])],
        agent_intent=extraction.intent,
        agent_parsed_date=extraction.parsed_date,
        agent_confidence=Decimal(str(float(extraction.confidence))),
        agent_reasoning=extraction.reasoning[:2000],
        raised_reason=raised_reason,
        resolution_state="pending",
    )
    session.add(review)
    await session.flush()  # populate review.id for the FK below

    timeline_entry: DeliveryTimelineEntry | None = None
    if candidate_delivery is not None and candidate_delivery.current_stage != "delivered":
        event_type = _INTENT_TO_REVIEW_EVENT.get(extraction.intent, "acknowledged")
        if raised_reason in _AT_RISK_REASONS:
            event_type = "at_risk"

        timeline_entry = await append_timeline_entry(
            session,
            delivery_id=candidate_delivery.id,
            event_type=event_type,
            occurred_at=datetime.now(timezone.utc),
            actor_type="agent",
            actor_id="delivery_eta_agent",
            parsed_date=extraction.parsed_date,
            confidence=float(extraction.confidence),
            supplier_excerpt=extraction.excerpt[:1000],
            source_reply_id=reply.id,
            source_review_id=review.id,
        )

        # Flip the delivery's "needs admin attention" flag.
        await session.execute(
            update(Delivery)
            .where(Delivery.id == candidate_delivery.id)
            .values(has_pending_review=True)
        )
        # Keep the in-memory object in sync so the caller's serialise step
        # sees the flag.
        candidate_delivery.has_pending_review = True

    logger.info(
        "raise_review_item: review_id=%s reason=%s intent=%s confidence=%.2f "
        "candidate_delivery_id=%s",
        review.id,
        raised_reason,
        extraction.intent,
        float(extraction.confidence),
        candidate_delivery.id if candidate_delivery else None,
    )
    return review, timeline_entry


def serialise_review_summary(
    *, review: EtaReviewItem, reply: SupplierReply
) -> dict:
    """Build the wire payload required by ``EtaReviewSummary``.

    ``EtaReviewSummary`` flattens supplier reply fields into the review
    object, so we can't use ``model_validate(review)`` directly.
    """
    excerpt = (reply.body_excerpt or "")[:400]
    summary = EtaReviewSummary(
        id=review.id,
        raised_at=review.raised_at,
        raised_reason=review.raised_reason,  # type: ignore[arg-type]
        agent_intent=review.agent_intent,  # type: ignore[arg-type]
        agent_parsed_date=review.agent_parsed_date,
        agent_confidence=float(review.agent_confidence),
        resolution_state=review.resolution_state,  # type: ignore[arg-type]
        candidate_delivery_id=review.candidate_delivery_id,
        supplier_from=reply.from_address,
        supplier_reply_excerpt=excerpt,
    )
    return summary.model_dump(mode="json")


# ---------------------------------------------------------------------------
# T047 — Review queue read + terminal resolution actions.
# ---------------------------------------------------------------------------


_TERMINAL_STATES: frozenset[str] = frozenset({"approved", "corrected", "dismissed"})


def _build_detail_response(
    *, review: EtaReviewItem, reply: SupplierReply
) -> EtaReviewDetailResponse:
    """Compose the `EtaReviewDetailResponse` pydantic object for a review."""
    excerpt = (reply.body_excerpt or "")[:400]
    return EtaReviewDetailResponse(
        id=review.id,
        raised_at=review.raised_at,
        raised_reason=review.raised_reason,  # type: ignore[arg-type]
        agent_intent=review.agent_intent,  # type: ignore[arg-type]
        agent_parsed_date=review.agent_parsed_date,
        agent_confidence=float(review.agent_confidence),
        resolution_state=review.resolution_state,  # type: ignore[arg-type]
        candidate_delivery_id=review.candidate_delivery_id,
        supplier_from=reply.from_address,
        supplier_reply_excerpt=excerpt,
        agent_reasoning=review.agent_reasoning,
        candidate_order_ids=[
            uuid.UUID(x) for x in (review.candidate_order_ids or [])
        ],
        supplier_reply=SupplierReplyEmbedded.model_validate(reply),
        resolved_by=review.resolved_by,
        resolved_at=review.resolved_at,
        resolution_payload=(
            EtaReviewResolutionPayload.model_validate(review.resolution_payload)
            if review.resolution_payload
            else None
        ),
    )


def serialise_review_detail(
    *, review: EtaReviewItem, reply: SupplierReply
) -> dict:
    """JSON-serialisable wire payload for `EtaReviewDetailResponse`."""
    return _build_detail_response(review=review, reply=reply).model_dump(
        mode="json"
    )


async def _load_reply(session: AsyncSession, reply_id: uuid.UUID) -> SupplierReply:
    reply = await session.get(SupplierReply, reply_id)
    if reply is None:
        # The reply FK is NOT NULL with CASCADE — this should never happen,
        # but failing loudly beats returning a half-populated response.
        raise NotFoundError("Supplier reply not found")
    return reply


async def _load_review(
    session: AsyncSession, review_id: uuid.UUID
) -> EtaReviewItem:
    review = await session.get(EtaReviewItem, review_id)
    if review is None:
        raise NotFoundError("Review item not found")
    return review


async def _count_other_pending(
    session: AsyncSession, *, delivery_id: uuid.UUID, exclude_review_id: uuid.UUID
) -> int:
    stmt = (
        select(func.count())
        .select_from(EtaReviewItem)
        .where(
            EtaReviewItem.candidate_delivery_id == delivery_id,
            EtaReviewItem.resolution_state == "pending",
            EtaReviewItem.id != exclude_review_id,
        )
    )
    return int((await session.execute(stmt)).scalar() or 0)


async def _recompute_has_pending_review(
    session: AsyncSession,
    *,
    delivery: Delivery,
    exclude_review_id: uuid.UUID,
) -> None:
    """If no other pending reviews reference the delivery, flip the flag off."""
    remaining = await _count_other_pending(
        session, delivery_id=delivery.id, exclude_review_id=exclude_review_id
    )
    if remaining == 0 and delivery.has_pending_review:
        delivery.has_pending_review = False
        await session.execute(
            update(Delivery)
            .where(Delivery.id == delivery.id)
            .values(has_pending_review=False)
        )


def _ensure_pending(review: EtaReviewItem) -> None:
    if review.resolution_state in _TERMINAL_STATES:
        raise ConflictError(
            f"Review {review.id} is already {review.resolution_state}"
        )


async def list_reviews(
    session: AsyncSession,
    *,
    state: str = "pending",
    page: int = 1,
    per_page: int = 25,
) -> EtaReviewListResponse:
    """Return a paginated list of reviews filtered by ``state``.

    ``state == 'all'`` returns rows in any state; otherwise filters
    exactly. Results are ordered newest-first by ``raised_at``.
    """
    base = select(EtaReviewItem)
    if state != "all":
        base = base.where(EtaReviewItem.resolution_state == state)
    base = base.order_by(EtaReviewItem.raised_at.desc())

    total = int(
        (
            await session.execute(
                select(func.count()).select_from(base.subquery())
            )
        ).scalar()
        or 0
    )
    rows = (
        (
            await session.execute(
                base.offset((page - 1) * per_page).limit(per_page)
            )
        )
        .scalars()
        .all()
    )

    items: list[EtaReviewSummary] = []
    for review in rows:
        reply = await _load_reply(session, review.supplier_reply_id)
        items.append(
            EtaReviewSummary(
                id=review.id,
                raised_at=review.raised_at,
                raised_reason=review.raised_reason,  # type: ignore[arg-type]
                agent_intent=review.agent_intent,  # type: ignore[arg-type]
                agent_parsed_date=review.agent_parsed_date,
                agent_confidence=float(review.agent_confidence),
                resolution_state=review.resolution_state,  # type: ignore[arg-type]
                candidate_delivery_id=review.candidate_delivery_id,
                supplier_from=reply.from_address,
                supplier_reply_excerpt=(reply.body_excerpt or "")[:400],
            )
        )

    return EtaReviewListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


async def get_review(
    session: AsyncSession, *, review_id: uuid.UUID
) -> EtaReviewDetailResponse:
    review = await _load_review(session, review_id)
    reply = await _load_reply(session, review.supplier_reply_id)
    return _build_detail_response(review=review, reply=reply)


async def _resolve_with_extraction(
    session: AsyncSession,
    *,
    review: EtaReviewItem,
    reply: SupplierReply,
    delivery: Delivery,
    extraction: EtaExtraction,
    admin_id: str,
    new_state: str,
    resolution_payload: dict | None,
) -> tuple[EtaReviewDetailResponse, DeliveryTimelineEntry, Delivery]:
    """Shared body for approve/correct: mutate the delivery via
    :func:`apply_eta_update`, mark the review terminal, recompute the
    pending flag. Returns (detail, timeline_entry, delivery)."""
    entry = await apply_eta_update(
        session, delivery=delivery, extraction=extraction, reply=reply
    )
    # Stamp the timeline entry with this review id so the audit trail joins.
    entry.source_review_id = review.id

    review.resolution_state = new_state
    review.resolved_by = admin_id
    review.resolved_at = datetime.now(timezone.utc)
    review.resolution_payload = resolution_payload

    await _recompute_has_pending_review(
        session, delivery=delivery, exclude_review_id=review.id
    )
    await session.flush()
    logger.info(
        "eta_review.resolve(%s): review_id=%s delivery_id=%s supplier_reply_id=%s "
        "admin_id=%s intent=%s",
        new_state,
        review.id,
        delivery.id,
        reply.id,
        admin_id,
        extraction.intent,
    )
    return (
        _build_detail_response(review=review, reply=reply),
        entry,
        delivery,
    )


async def approve(
    session: AsyncSession, *, review_id: uuid.UUID, admin_id: str
) -> tuple[EtaReviewDetailResponse, DeliveryTimelineEntry | None, Delivery | None]:
    """Approve the agent's parse exactly as proposed.

    Returns ``(detail, entry, delivery)``. ``entry`` is ``None`` for
    intents that do not mutate the delivery (``acknowledge``); it is
    illegal for intents the auto-applier rejects (``cancel``/``unclear``)
    — those raise ``ValidationError`` so the admin must correct or dismiss.
    """
    review = await _load_review(session, review_id)
    _ensure_pending(review)
    reply = await _load_reply(session, review.supplier_reply_id)

    if review.agent_intent in ("cancel", "unclear"):
        raise ValidationError(
            "Cannot approve a 'cancel' or 'unclear' review — "
            "use correct or dismiss instead."
        )
    if review.candidate_delivery_id is None:
        raise ValidationError(
            "Cannot approve a review with no candidate delivery — "
            "use correct to choose a delivery."
        )
    if review.agent_intent in ("confirm", "delay") and review.agent_parsed_date is None:
        raise ValidationError(
            "Cannot approve: agent did not extract a parsed_date for a "
            "confirm/delay intent."
        )

    delivery = await session.get(Delivery, review.candidate_delivery_id)
    if delivery is None:
        raise NotFoundError("Candidate delivery no longer exists")

    extraction = EtaExtraction(
        intent=review.agent_intent,  # type: ignore[arg-type]
        parsed_date=review.agent_parsed_date,
        confidence=float(review.agent_confidence),
        excerpt=(reply.body_excerpt or "")[:1000],
        reasoning=review.agent_reasoning[:2000],
    )
    detail, entry, _ = await _resolve_with_extraction(
        session,
        review=review,
        reply=reply,
        delivery=delivery,
        extraction=extraction,
        admin_id=admin_id,
        new_state="approved",
        resolution_payload=None,
    )
    return detail, entry, delivery


async def correct(
    session: AsyncSession,
    *,
    review_id: uuid.UUID,
    payload: EtaReviewCorrectRequest,
    admin_id: str,
) -> tuple[EtaReviewDetailResponse, DeliveryTimelineEntry | None, Delivery | None]:
    """Override the agent's parse with admin-supplied values."""
    review = await _load_review(session, review_id)
    _ensure_pending(review)
    reply = await _load_reply(session, review.supplier_reply_id)

    # Reject past dates (FR-013: admins also can't pick a stale date).
    parsed = payload.parsed_date
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if parsed < datetime.now(timezone.utc):
        raise ValidationError("parsed_date must not be in the past")

    delivery = await session.get(Delivery, payload.delivery_id)
    if delivery is None:
        raise ValidationError("Unknown delivery_id")

    if payload.intent in ("cancel",):
        # The auto-applier does not support 'cancel' — mark dismissed-with-note
        # path would be appropriate. We reject here so the admin uses dismiss.
        raise ValidationError(
            "Use dismiss for 'cancel' intent — the system does not auto-cancel deliveries."
        )

    extraction = EtaExtraction(
        intent=payload.intent,
        parsed_date=parsed,
        confidence=float(review.agent_confidence),
        excerpt=(reply.body_excerpt or "")[:1000],
        reasoning=(
            payload.note or review.agent_reasoning or "Admin correction"
        )[:2000],
    )
    resolution_payload = {
        "delivery_id": str(payload.delivery_id),
        "parsed_date": parsed.isoformat(),
        "intent": payload.intent,
    }
    detail, entry, _ = await _resolve_with_extraction(
        session,
        review=review,
        reply=reply,
        delivery=delivery,
        extraction=extraction,
        admin_id=admin_id,
        new_state="corrected",
        resolution_payload=resolution_payload,
    )
    return detail, entry, delivery


async def dismiss(
    session: AsyncSession,
    *,
    review_id: uuid.UUID,
    payload: EtaReviewDismissRequest,
    admin_id: str,
) -> tuple[EtaReviewDetailResponse, DeliveryTimelineEntry | None, Delivery | None]:
    """Dismiss the review without changing the delivery.

    No ``delivery.timeline.appended`` event fires (the dismissal does not
    represent a supplier signal). If the dismissed review was attached to a
    delivery, ``has_pending_review`` is recomputed.
    """
    review = await _load_review(session, review_id)
    _ensure_pending(review)
    reply = await _load_reply(session, review.supplier_reply_id)

    review.resolution_state = "dismissed"
    review.resolved_by = admin_id
    review.resolved_at = datetime.now(timezone.utc)
    review.resolution_payload = (
        {"note": payload.note} if payload and payload.note else None
    )

    delivery: Delivery | None = None
    if review.candidate_delivery_id is not None:
        delivery = await session.get(Delivery, review.candidate_delivery_id)
        if delivery is not None:
            await _recompute_has_pending_review(
                session, delivery=delivery, exclude_review_id=review.id
            )

    await session.flush()
    logger.info(
        "eta_review.resolve(dismissed): review_id=%s delivery_id=%s supplier_reply_id=%s "
        "admin_id=%s",
        review.id,
        delivery.id if delivery is not None else None,
        reply.id,
        admin_id,
    )
    return _build_detail_response(review=review, reply=reply), None, delivery
