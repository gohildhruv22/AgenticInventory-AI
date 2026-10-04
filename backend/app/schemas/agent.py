from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ReasoningTrace(BaseModel):
    input_context: str = ""
    rationale: str = ""
    confidence: float = 0.0
    alternatives: list[dict[str, str]] = []
    data_sources: list[str] = []


class AgentDecisionResponse(BaseModel):
    id: UUID
    agent_type: str
    action_type: str
    inventory_item_id: UUID | None
    forecast_id: UUID | None
    reasoning_trace: dict[str, Any]
    confidence_level: Decimal | None
    alternatives_considered: list[dict[str, Any]]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DecisionListResponse(BaseModel):
    decisions: list[AgentDecisionResponse]
    total: int
    page: int
    per_page: int
    pages: int


class UndoResponse(BaseModel):
    message: str
    decision_id: UUID
    actions_reversed: int
    rollback_summary: list[dict[str, Any]]
