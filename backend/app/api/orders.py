"""Order API routes — create supplier orders from approved decisions."""

from __future__ import annotations

import math

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.supplier_order import SupplierOrder
from app.models.user import User
from app.schemas.order import CreateOrderRequest, OrderListResponse, OrderResponse
from app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=OrderListResponse)
async def list_orders(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List supplier orders with pagination."""
    query = select(SupplierOrder)
    if status:
        query = query.where(SupplierOrder.email_status == status)
    query = query.order_by(SupplierOrder.created_at.desc())

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    orders = result.scalars().all()

    return OrderListResponse(
        orders=[OrderResponse.model_validate(o) for o in orders],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get a single supplier order."""
    svc = OrderService(db)
    order = await svc.get_order(order_id)
    if not order:
        raise NotFoundError("Order not found")
    return order


async def _create_order_background(
    decision_id: str,
    db_url: str,
):
    """Background task: create order + send emails outside request lifecycle."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as db:
        settings = get_settings()
        svc = OrderService(db)
        await svc.create_order_from_decision(
            decision_id=decision_id,
            admin_email=settings.ADMIN_NOTIFICATION_EMAIL,
        )
        await db.commit()
    await engine.dispose()


@router.post("", response_model=dict)
async def create_order(
    body: CreateOrderRequest,
    background_tasks: BackgroundTasks,
    _user: User = Depends(get_current_user),
):
    """Create a supplier order from an approved decision (runs in background)."""
    settings = get_settings()
    background_tasks.add_task(
        _create_order_background,
        decision_id=body.decision_id,
        db_url=settings.DATABASE_URL,
    )
    return {"status": "accepted", "decision_id": body.decision_id, "message": "Order creation initiated"}
