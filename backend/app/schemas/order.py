"""Schemas for supplier order API endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    decision_id: UUID
    supplier_name: str
    supplier_email: str
    items: list[dict]
    total_cost: float
    email_status: str
    email_message_id: str | None = None
    retry_count: int
    created_at: datetime
    updated_at: datetime


class CreateOrderRequest(BaseModel):
    decision_id: str


class OrderListResponse(BaseModel):
    orders: list[OrderResponse]
    total: int
    page: int
    per_page: int
    pages: int
