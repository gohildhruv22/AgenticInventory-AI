import math
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.delivery import Delivery
from app.models.delivery_timeline_entry import (
    DeliveryTimelineEntry as TimelineEntryModel,
)
from app.models.user import User
from app.schemas.delivery import (
    DeliveryListResponse,
    DeliveryResponse,
    DeliveryTimelineEntry as TimelineEntrySchema,
    DeliveryTimelineResponse,
)
from app.services.delivery_service import list_timeline

router = APIRouter(prefix="/deliveries", tags=["deliveries"])


# Time-driven stage progression — no supplier confirmation required.
# Stages advance proportionally to (now - ordered_at) / lead_time.
_AUTO_STAGE_BUCKETS: list[tuple[float, str]] = [
    (0.15, "ordered"),     # first 15% of lead time
    (0.40, "confirmed"),   # 15-40%
    (0.65, "shipped"),     # 40-65%
    (1.00, "in_transit"),  # 65-100%
]


def _auto_advance_stage(delivery: Delivery) -> None:
    """Mutate ``delivery.current_stage`` based on elapsed time vs expected
    delivery date. Safe to call on every read — only writes happen in the
    list/get endpoints which already commit on response.

    The simulation_config flag ``auto_advance`` opts a delivery in. Manually
    tracked deliveries (e.g. from supplier email replies) leave the flag
    unset and keep their existing stage.
    """
    if delivery.current_stage == "delivered" or delivery.current_stage == "at_risk":
        return
    cfg = delivery.simulation_config or {}
    if not cfg.get("auto_advance"):
        # Legacy/seeded deliveries: still let them progress to "delivered"
        # if the expected date has passed (so the UI is always meaningful).
        if delivery.expected_delivery_at and delivery.actual_delivery_at is None:
            now = datetime.now(timezone.utc)
            expected = delivery.expected_delivery_at
            if expected.tzinfo is None:
                expected = expected.replace(tzinfo=timezone.utc)
            if now >= expected and delivery.current_stage != "delivered":
                delivery.current_stage = "delivered"
                delivery.actual_delivery_at = now
        return

    if not delivery.expected_delivery_at:
        return

    now = datetime.now(timezone.utc)
    ordered_at_iso = cfg.get("ordered_at") or (
        delivery.created_at.isoformat() if delivery.created_at else None
    )
    if not ordered_at_iso:
        return
    try:
        ordered_at = datetime.fromisoformat(ordered_at_iso.replace("Z", "+00:00"))
    except ValueError:
        return
    if ordered_at.tzinfo is None:
        ordered_at = ordered_at.replace(tzinfo=timezone.utc)

    expected = delivery.expected_delivery_at
    if expected.tzinfo is None:
        expected = expected.replace(tzinfo=timezone.utc)

    total_seconds = (expected - ordered_at).total_seconds()
    if total_seconds <= 0:
        return

    elapsed_seconds = (now - ordered_at).total_seconds()
    progress = max(0.0, min(1.0, elapsed_seconds / total_seconds))

    # Past expected → delivered.
    if now >= expected:
        if delivery.current_stage != "delivered":
            delivery.current_stage = "delivered"
            delivery.actual_delivery_at = now
        return

    target_stage = "ordered"
    for threshold, stage in _AUTO_STAGE_BUCKETS:
        if progress <= threshold:
            target_stage = stage
            break

    if target_stage != delivery.current_stage:
        delivery.current_stage = target_stage
        # Append a stage_history entry for the new transition.
        history = list(delivery.stage_history or [])
        history.append(
            {
                "stage": target_stage,
                "at": now.isoformat(),
                "note": f"Auto-advanced (progress {progress:.0%})",
            }
        )
        delivery.stage_history = history


async def _latest_timeline_map(
    db: AsyncSession, delivery_ids: list[UUID]
) -> dict[UUID, TimelineEntryModel]:
    """Return ``{delivery_id: most_recent_timeline_entry}`` in a single
    round-trip. Uses an aggregate sub-select + self-join (SQLite-friendly).
    """
    if not delivery_ids:
        return {}

    max_q = (
        select(
            TimelineEntryModel.delivery_id.label("did"),
            func.max(TimelineEntryModel.occurred_at).label("max_at"),
        )
        .where(TimelineEntryModel.delivery_id.in_(delivery_ids))
        .group_by(TimelineEntryModel.delivery_id)
        .subquery()
    )
    stmt = select(TimelineEntryModel).join(
        max_q,
        (TimelineEntryModel.delivery_id == max_q.c.did)
        & (TimelineEntryModel.occurred_at == max_q.c.max_at),
    )
    rows = (await db.execute(stmt)).scalars().all()
    out: dict[UUID, TimelineEntryModel] = {}
    for row in rows:
        prev = out.get(row.delivery_id)
        # Deterministic tie-break when multiple rows share occurred_at.
        if prev is None or row.created_at > prev.created_at:
            out[row.delivery_id] = row
    return out


def _hydrate_response(
    delivery: Delivery,
    latest_entry: TimelineEntryModel | None,
) -> DeliveryResponse:
    return DeliveryResponse.model_validate(delivery).model_copy(
        update={
            "has_pending_review": bool(delivery.has_pending_review),
            "latest_timeline_entry": (
                TimelineEntrySchema.model_validate(latest_entry)
                if latest_entry is not None
                else None
            ),
        }
    )


@router.get("", response_model=DeliveryListResponse)
async def list_deliveries(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    stage: str | None = None,
    order_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = select(Delivery)

    if stage:
        query = query.where(Delivery.current_stage == stage)
    if order_id:
        query = query.where(Delivery.order_id == order_id)

    query = query.order_by(Delivery.created_at.desc())

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    deliveries = result.scalars().all()

    # Time-driven auto-advance per delivery before serializing.
    for d in deliveries:
        _auto_advance_stage(d)
    await db.commit()

    # Re-apply the stage filter post-advance so a query like
    # ?stage=in_transit still returns the right rows after recompute.
    if stage:
        deliveries = [d for d in deliveries if d.current_stage == stage]

    latest_map = await _latest_timeline_map(db, [d.id for d in deliveries])
    return DeliveryListResponse(
        deliveries=[_hydrate_response(d, latest_map.get(d.id)) for d in deliveries],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.get("/{delivery_id}/timeline", response_model=DeliveryTimelineResponse)
async def get_delivery_timeline(
    delivery_id: UUID,
    since: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> DeliveryTimelineResponse:
    """T036 — return the append-only timeline for one delivery.

    404 when the delivery does not exist; 200 with an ordered list otherwise.
    """
    exists = (
        await db.execute(select(Delivery.id).where(Delivery.id == delivery_id))
    ).scalar_one_or_none()
    if exists is None:
        raise NotFoundError("Delivery not found")
    return await list_timeline(db, delivery_id=delivery_id, since=since, limit=limit)


@router.get("/{delivery_id}", response_model=DeliveryResponse)
async def get_delivery(
    delivery_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Delivery).where(Delivery.id == delivery_id))
    delivery = result.scalar_one_or_none()
    if not delivery:
        raise NotFoundError("Delivery not found")

    _auto_advance_stage(delivery)
    await db.commit()

    latest_q = (
        select(TimelineEntryModel)
        .where(TimelineEntryModel.delivery_id == delivery.id)
        .order_by(
            desc(TimelineEntryModel.occurred_at),
            desc(TimelineEntryModel.created_at),
        )
        .limit(1)
    )
    latest = (await db.execute(latest_q)).scalar_one_or_none()
    return _hydrate_response(delivery, latest)


@router.delete("/{delivery_id}", status_code=204)
async def delete_delivery(
    delivery_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Permanently remove a delivery from the tracking board.

    Associated ``delivery_timeline_entries`` rows cascade automatically via
    the ``ON DELETE CASCADE`` foreign key defined on the model.
    """
    result = await db.execute(select(Delivery).where(Delivery.id == delivery_id))
    delivery = result.scalar_one_or_none()
    if not delivery:
        raise NotFoundError("Delivery not found")
    await db.delete(delivery)
    await db.commit()
    return None
