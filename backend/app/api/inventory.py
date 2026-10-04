from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
    InventoryListResponse,
)
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory", tags=["inventory"])


def _svc(db: AsyncSession = Depends(get_db)) -> InventoryService:
    return InventoryService(db)


@router.get("", response_model=InventoryListResponse)
async def list_inventory(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    category: str | None = None,
    status: str | None = None,
    search: str | None = None,
    sort_by: str = "name",
    sort_order: str = "asc",
    svc: InventoryService = Depends(_svc),
    _user: User = Depends(get_current_user),
):
    return await svc.list_items(
        page=page,
        per_page=per_page,
        category=category,
        status=status,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/categories", response_model=list[str])
async def list_categories(
    svc: InventoryService = Depends(_svc),
    _user: User = Depends(get_current_user),
):
    return await svc.get_categories()


@router.get("/stats")
async def inventory_stats(
    svc: InventoryService = Depends(_svc),
    _user: User = Depends(get_current_user),
):
    return await svc.get_stats()


@router.get("/low-stock", response_model=list[InventoryItemResponse])
async def low_stock_items(
    svc: InventoryService = Depends(_svc),
    _user: User = Depends(get_current_user),
):
    items = await svc.get_low_stock_items()
    return [InventoryItemResponse.model_validate(i) for i in items]


@router.get("/{item_id}", response_model=InventoryItemResponse)
async def get_inventory_item(
    item_id: str,
    svc: InventoryService = Depends(_svc),
    _user: User = Depends(get_current_user),
):
    item = await svc.get_item(item_id)
    return item


@router.post("", response_model=InventoryItemResponse, status_code=201)
async def create_inventory_item(
    body: InventoryItemCreate,
    svc: InventoryService = Depends(_svc),
    _user: User = Depends(get_current_user),
):
    return await svc.create_item(body)


@router.patch("/{item_id}", response_model=InventoryItemResponse)
async def update_inventory_item(
    item_id: str,
    body: InventoryItemUpdate,
    svc: InventoryService = Depends(_svc),
    _user: User = Depends(get_current_user),
):
    return await svc.update_item(item_id, body)


@router.delete("/{item_id}")
async def delete_inventory_item(
    item_id: str,
    svc: InventoryService = Depends(_svc),
    _user: User = Depends(get_current_user),
):
    await svc.delete_item(item_id)
    return {"message": "Item deactivated"}
