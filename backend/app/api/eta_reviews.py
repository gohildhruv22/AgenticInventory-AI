"""T048 — REST router for the ETA Review Queue (US3).

Surfaces the five endpoints from
``specs/004-supplier-delivery-eta-agent/contracts/eta-reviews.openapi.yaml``
wired to :mod:`app.services.eta_review_service`.

All endpoints require the existing JWT admin-session dependency. WS events
(``eta_review.resolved`` and the preceding ``delivery.timeline.appended``
for approve/correct) are published from this router AFTER commit, per the
ordering guarantee in ``contracts/websocket-events.md`` §3.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.eta_review import (
    EtaReviewCorrectRequest,
    EtaReviewDetailResponse,
    EtaReviewDismissRequest,
    EtaReviewListResponse,
)
from app.services import eta_review_service
from app.services.delivery_service import (
    serialise_delivery_summary,
    serialise_timeline_entry,
)
from app.websocket.events import (
    publish_eta_review_resolved,
    publish_timeline_appended,
)

router = APIRouter(prefix="/eta-reviews", tags=["eta-reviews"])


@router.get("", response_model=EtaReviewListResponse)
async def list_eta_reviews(
    state: str = Query(
        default="pending",
        pattern="^(pending|approved|corrected|dismissed|all)$",
    ),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> EtaReviewListResponse:
    return await eta_review_service.list_reviews(
        db, state=state, page=page, per_page=per_page
    )


@router.get("/{review_id}", response_model=EtaReviewDetailResponse)
async def get_eta_review(
    review_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> EtaReviewDetailResponse:
    return await eta_review_service.get_review(db, review_id=review_id)


def _admin_id(user: User) -> str:
    return user.email or str(user.id)


@router.post("/{review_id}/approve", response_model=EtaReviewDetailResponse)
async def approve_eta_review(
    review_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EtaReviewDetailResponse:
    detail, entry, delivery = await eta_review_service.approve(
        db, review_id=review_id, admin_id=_admin_id(user)
    )
    await db.commit()
    # Ordering: timeline first, then resolution.
    if entry is not None and delivery is not None:
        await publish_timeline_appended(
            delivery_id=delivery.id,
            entry=serialise_timeline_entry(entry),
            delivery_summary=serialise_delivery_summary(delivery),
        )
    await publish_eta_review_resolved(
        review=detail.model_dump(mode="json"),
        delivery_id=delivery.id if delivery else None,
        delivery_summary=serialise_delivery_summary(delivery) if delivery else None,
    )
    return detail


@router.post("/{review_id}/correct", response_model=EtaReviewDetailResponse)
async def correct_eta_review(
    review_id: UUID,
    payload: EtaReviewCorrectRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EtaReviewDetailResponse:
    detail, entry, delivery = await eta_review_service.correct(
        db, review_id=review_id, payload=payload, admin_id=_admin_id(user)
    )
    await db.commit()
    if entry is not None and delivery is not None:
        await publish_timeline_appended(
            delivery_id=delivery.id,
            entry=serialise_timeline_entry(entry),
            delivery_summary=serialise_delivery_summary(delivery),
        )
    await publish_eta_review_resolved(
        review=detail.model_dump(mode="json"),
        delivery_id=delivery.id if delivery else None,
        delivery_summary=serialise_delivery_summary(delivery) if delivery else None,
    )
    return detail


@router.post("/{review_id}/dismiss", response_model=EtaReviewDetailResponse)
async def dismiss_eta_review(
    review_id: UUID,
    payload: EtaReviewDismissRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EtaReviewDetailResponse:
    detail, _entry, delivery = await eta_review_service.dismiss(
        db,
        review_id=review_id,
        payload=payload or EtaReviewDismissRequest(),
        admin_id=_admin_id(user),
    )
    await db.commit()
    await publish_eta_review_resolved(
        review=detail.model_dump(mode="json"),
        delivery_id=delivery.id if delivery else None,
        delivery_summary=serialise_delivery_summary(delivery) if delivery else None,
    )
    return detail
