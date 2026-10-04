import math

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.agent_decision import AgentDecision
from app.models.user import User
from app.schemas.agent import AgentDecisionResponse, DecisionListResponse
from app.services.decision_service import DecisionService
from app.services.rollback_service import (
    AlreadyRolledBackError,
    CannotUndoError,
    RollbackService,
)

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.get("", response_model=DecisionListResponse)
async def list_decisions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    agent_type: str | None = None,
    status: str | None = None,
    item_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = select(AgentDecision)

    if agent_type:
        query = query.where(AgentDecision.agent_type == agent_type)
    if status:
        query = query.where(AgentDecision.status == status)
    if item_id:
        query = query.where(AgentDecision.inventory_item_id == item_id)

    query = query.order_by(AgentDecision.created_at.desc())

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    decisions = result.scalars().all()

    return DecisionListResponse(
        decisions=[AgentDecisionResponse.model_validate(d) for d in decisions],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.get("/{decision_id}", response_model=AgentDecisionResponse)
async def get_decision(
    decision_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(AgentDecision).where(AgentDecision.id == decision_id))
    decision = result.scalar_one_or_none()
    if not decision:
        raise NotFoundError("Decision not found")
    return decision


class EvaluateForecastRequest(BaseModel):
    forecast_id: str
    auto_approve_confidence: float | None = None
    max_order_value: float | None = None
    min_confidence_to_flag: float | None = None


@router.post("/evaluate", response_model=AgentDecisionResponse)
async def evaluate_forecast(
    body: EvaluateForecastRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Evaluate a forecast via the Decision Manager Agent."""
    thresholds = {}
    if body.auto_approve_confidence is not None:
        thresholds["auto_approve_confidence"] = body.auto_approve_confidence
    if body.max_order_value is not None:
        thresholds["max_order_value"] = body.max_order_value
    if body.min_confidence_to_flag is not None:
        thresholds["min_confidence_to_flag"] = body.min_confidence_to_flag

    svc = DecisionService(db)
    decision = await svc.evaluate_forecast(body.forecast_id, thresholds or None)
    return decision


@router.post("/{decision_id}/approve", response_model=AgentDecisionResponse)
async def approve_decision(
    decision_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Manually approve a flagged decision."""
    svc = DecisionService(db)
    decision = await svc.approve_flagged(decision_id)
    return decision


@router.get("/pending/list", response_model=list[AgentDecisionResponse])
async def list_pending_decisions(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List all flagged decisions awaiting human review."""
    svc = DecisionService(db)
    decisions = await svc.get_pending_decisions()
    return [AgentDecisionResponse.model_validate(d) for d in decisions]


@router.post("/{decision_id}/undo")
async def undo_decision(
    decision_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Initiate undo/rollback for a decision.

    Reverses all actions associated with the decision in reverse-chronological
    order: cancels deliveries, sends cancellation emails, restores inventory.
    Progress is streamed via WebSocket rollback:progress events.
    """
    svc = RollbackService(db)
    try:
        result = await svc.undo_decision(decision_id)
    except AlreadyRolledBackError:
        raise HTTPException(status_code=422, detail="Action already rolled back")
    except CannotUndoError as e:
        raise HTTPException(status_code=409, detail=str(e), headers={"X-Reason": e.reason})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return result


@router.get("/{decision_id}/rollback-trail")
async def get_rollback_trail(
    decision_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get the audit trail of rolled-back actions for a decision."""
    svc = RollbackService(db)
    trail = await svc.get_rollback_audit_trail(decision_id)
    return {"decision_id": decision_id, "actions": trail}


@router.delete("/{decision_id}", status_code=204)
async def delete_decision(
    decision_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Permanently remove a decision from the feed.

    This is a UI-driven dismissal — useful for clearing out stale demo
    decisions. The associated ``SupplierOrder`` row (if any) keeps its
    ``decision_id`` reference because no real FK constraint exists in the
    model; this matches existing behaviour for orphaned audit data.
    """
    result = await db.execute(
        select(AgentDecision).where(AgentDecision.id == decision_id)
    )
    decision = result.scalar_one_or_none()
    if not decision:
        raise NotFoundError("Decision not found")
    await db.delete(decision)
    await db.commit()
    return None
