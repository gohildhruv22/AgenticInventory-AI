"""Pydantic schemas for the SupplierReply resource."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ProcessingStatus = Literal[
    "new", "parsed", "applied", "in_review", "ignored", "failed"
]


class SupplierReplyRead(BaseModel):
    """Full SupplierReply payload, used by admin/audit endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    message_id: str
    from_address: str
    subject: str
    received_at: datetime
    body_excerpt: str
    raw_headers: dict[str, Any] = Field(default_factory=dict)
    matched_order_id: UUID | None = None
    matched_delivery_id: UUID | None = None
    processing_status: ProcessingStatus
    agent_response: dict[str, Any] | None = None
    error_detail: str | None = None
    created_at: datetime
    updated_at: datetime
