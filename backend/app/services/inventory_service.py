import logging
import math
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_item import InventoryItem
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse,
    InventoryListResponse,
)
from app.core.exceptions import ConflictError, NotFoundError
from app.websocket.manager import ws_manager

logger = logging.getLogger("agenticinventory")


class InventoryService:
    """Service layer for inventory CRUD with stock change detection and WS broadcasting."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_items(
        self,
        page: int = 1,
        per_page: int = 50,
        category: str | None = None,
        status: str | None = None,
        search: str | None = None,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> InventoryListResponse:
        query = select(InventoryItem).where(InventoryItem.is_active == True)  # noqa: E712

        if category:
            query = query.where(InventoryItem.category == category)
        if search:
            pattern = f"%{search}%"
            query = query.where(
                InventoryItem.name.ilike(pattern) | InventoryItem.sku.ilike(pattern)
            )

        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        sort_col = getattr(InventoryItem, sort_by, InventoryItem.name)
        query = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        if status:
            items = [i for i in items if i.status == status]

        return InventoryListResponse(
            items=[InventoryItemResponse.model_validate(i) for i in items],
            total=total,
            page=page,
            per_page=per_page,
            pages=math.ceil(total / per_page) if total else 0,
        )

    async def get_item(self, item_id: str) -> InventoryItem:
        result = await self.db.execute(
            select(InventoryItem).where(InventoryItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            raise NotFoundError("Inventory item not found")
        return item

    async def create_item(self, data: InventoryItemCreate) -> InventoryItem:
        existing = await self.db.execute(
            select(InventoryItem).where(InventoryItem.sku == data.sku)
        )
        if existing.scalar_one_or_none():
            raise ConflictError("SKU already exists")

        item = InventoryItem(**data.model_dump())
        self.db.add(item)
        await self.db.flush()
        return item

    async def update_item(
        self, item_id: str, data: InventoryItemUpdate
    ) -> InventoryItem:
        item = await self.get_item(item_id)
        previous_stock = item.current_stock
        previous_status = item.status

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(item, field, value)
        await self.db.flush()

        # Detect stock level change and broadcast
        if item.current_stock != previous_stock or item.status != previous_status:
            await self._broadcast_stock_change(item, previous_stock)

        # Check threshold breach
        if item.status in ("low_stock", "out_of_stock") and previous_status == "normal":
            await self._broadcast_threshold_breach(item)

        return item

    async def delete_item(self, item_id: str) -> None:
        item = await self.get_item(item_id)
        item.is_active = False
        await self.db.flush()

    async def get_categories(self) -> list[str]:
        result = await self.db.execute(
            select(InventoryItem.category)
            .where(InventoryItem.is_active == True)  # noqa: E712
            .distinct()
            .order_by(InventoryItem.category)
        )
        return [row[0] for row in result.all()]

    async def get_low_stock_items(self) -> list[InventoryItem]:
        result = await self.db.execute(
            select(InventoryItem).where(
                InventoryItem.is_active == True,  # noqa: E712
                InventoryItem.current_stock <= InventoryItem.reorder_threshold,
            )
        )
        return list(result.scalars().all())

    async def get_stats(self) -> dict:
        """Get inventory statistics for dashboard KPI cards."""
        items_q = select(InventoryItem).where(InventoryItem.is_active == True)  # noqa: E712
        result = await self.db.execute(items_q)
        items = list(result.scalars().all())

        total_items = len(items)
        total_value = sum(float(i.unit_cost) * i.current_stock for i in items)
        low_stock = sum(1 for i in items if i.status == "low_stock")
        out_of_stock = sum(1 for i in items if i.status == "out_of_stock")
        categories = len(set(i.category for i in items))

        return {
            "total_items": total_items,
            "total_value": round(total_value, 2),
            "low_stock_count": low_stock,
            "out_of_stock_count": out_of_stock,
            "categories": categories,
            "healthy_count": total_items - low_stock - out_of_stock,
        }

    async def _broadcast_stock_change(
        self, item: InventoryItem, previous_stock: int
    ) -> None:
        await ws_manager.broadcast_all(
            "inventory:update",
            {
                "item_id": str(item.id),
                "sku": item.sku,
                "name": item.name,
                "current_stock": item.current_stock,
                "previous_stock": previous_stock,
                "status": item.status,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
                "trigger": "manual_update",
            },
        )

    async def _broadcast_threshold_breach(self, item: InventoryItem) -> None:
        await ws_manager.broadcast_all(
            "inventory:alert",
            {
                "item_id": str(item.id),
                "sku": item.sku,
                "name": item.name,
                "current_stock": item.current_stock,
                "reorder_threshold": item.reorder_threshold,
                "status": item.status,
                "message": f"{item.name} ({item.sku}) is {item.status.replace('_', ' ')}",
            },
        )
