"""Pydantic schemas for ETA reviews and the agent's structured output.

Mirrors the contract in
``specs/004-supplier-delivery-eta-agent/contracts/eta-reviews.openapi.yaml``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Intent values produced by the agent (data-model §3 + research §7).
EtaIntent = Literal["confirm", "delay", "cancel", "acknowledge", "unclear"]
RaisedReason = Literal[
    "low_confidence",
    "unmatched_order",
    "ambiguous_match",
    "negative_intent",
    "past_date",
    "non_english",
]
ResolutionState = Literal["pending", "approved", "corrected", "dismissed"]
CorrectIntent = Literal["confirm", "delay", "cancel", "acknowledge"]


class EtaExtraction(BaseModel):
    """Strict JSON contract returned by ``DeliveryEtaAgent``.

    Parsed via ``model_validate_json`` from the raw LLM response. Any field
    failure raises ``pydantic.ValidationError`` which the agent converts to
    ``LLMAgentError`` so ``invoke_with_retries`` can re-prompt.
    """

    model_config = ConfigDict(extra="forbid")

    intent: EtaIntent
    parsed_date: datetime | None = Field(
        default=None,
        description=(
            "Resolved absolute ETA. None means the agent could not extract a "
            "date even though the intent is parseable (e.g. 'confirm received')."
        ),
    )
    confidence: float = Field(ge=0.0, le=100.0)
    excerpt: str = Field(
        max_length=1000,
        description="Verbatim quote from the supplier message that justifies the parse.",
    )
    reasoning: str = Field(
        max_length=2000,
        description="Natural-language justification for the agent's choice.",
    )


class ErrorResponse(BaseModel):
    detail: str


class SupplierReplyEmbedded(BaseModel):
    """Slimmed `SupplierReply` payload embedded in review detail responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subject: str
    from_address: str
    received_at: datetime
    body_excerpt: str


class EtaReviewSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    raised_at: datetime
    raised_reason: RaisedReason
    agent_intent: EtaIntent
    agent_parsed_date: datetime | None = None
    agent_confidence: float = Field(ge=0.0, le=100.0)
    resolution_state: ResolutionState
    candidate_delivery_id: UUID | None = None
    supplier_from: str
    supplier_reply_excerpt: str = Field(max_length=400)


class EtaReviewResolutionPayload(BaseModel):
    delivery_id: UUID
    parsed_date: datetime
    intent: CorrectIntent


class EtaReviewDetailResponse(EtaReviewSummary):
    agent_reasoning: str
    candidate_order_ids: list[UUID] = Field(default_factory=list)
    supplier_reply: SupplierReplyEmbedded
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    resolution_payload: EtaReviewResolutionPayload | None = None


class EtaReviewListResponse(BaseModel):
    items: list[EtaReviewSummary]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    per_page: int = Field(ge=1)
    pages: int = Field(ge=0)


class EtaReviewCorrectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delivery_id: UUID
    parsed_date: datetime
    intent: CorrectIntent
    note: str | None = Field(default=None, max_length=500)


class EtaReviewDismissRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=500)
