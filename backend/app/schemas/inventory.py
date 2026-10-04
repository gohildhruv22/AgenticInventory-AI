from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class InventoryItemCreate(BaseModel):
    name: str = Field(max_length=200)
    sku: str = Field(max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    category: str = Field(max_length=100)
    current_stock: int = Field(ge=0, default=0)
    reorder_threshold: int = Field(ge=0)
    safety_stock: int = Field(ge=0, default=0)
    lead_time_days: int = Field(ge=1, default=7)
    unit_cost: Decimal = Field(ge=0)
    supplier_email: str | None = None


class InventoryItemUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    current_stock: int | None = Field(default=None, ge=0)
    reorder_threshold: int | None = Field(default=None, ge=0)
    safety_stock: int | None = Field(default=None, ge=0)
    lead_time_days: int | None = Field(default=None, ge=1)
    unit_cost: Decimal | None = Field(default=None, ge=0)
    supplier_email: str | None = None
    is_active: bool | None = None


class InventoryItemResponse(BaseModel):
    id: UUID
    name: str
    sku: str
    category: str
    current_stock: int
    reorder_threshold: int
    safety_stock: int
    lead_time_days: int
    unit_cost: Decimal
    supplier_email: str | None
    status: str
    is_active: bool
    last_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InventoryListResponse(BaseModel):
    items: list[InventoryItemResponse]
    total: int
    page: int
    per_page: int
    pages: int
