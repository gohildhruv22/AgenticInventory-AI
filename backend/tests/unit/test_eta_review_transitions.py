"""T058 — exhaustive transition tests for `EtaReviewItem.resolution_state`
and `SupplierReply.processing_status` validators (data-model §1 & §3).

Plain unit tests — no DB or session required because both validators are
SQLAlchemy `@validates` hooks that fire on simple attribute assignment.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.eta_review_item import (
    EtaReviewItem,
    _ALLOWED_RESOLUTION_TRANSITIONS,
    _VALID_RESOLUTIONS,
)
from app.models.supplier_reply import (
    SupplierReply,
    _ALLOWED_STATUS_TRANSITIONS,
    _VALID_STATUSES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_reply(status: str = "new") -> SupplierReply:
    return SupplierReply(
        message_id=f"<{uuid4()}@example.test>",
        from_address="supplier@example.test",
        subject="Order #1234",
        received_at=datetime.now(timezone.utc),
        body_excerpt="hello",
        raw_headers={},
        processing_status=status,
    )


def _new_review(state: str = "pending") -> EtaReviewItem:
    return EtaReviewItem(
        supplier_reply_id=uuid4(),
        candidate_order_ids=[],
        agent_intent="confirm",
        agent_confidence=Decimal("50.00"),
        agent_reasoning="reason",
        raised_reason="low_confidence",
        resolution_state=state,
    )


# ---------------------------------------------------------------------------
# SupplierReply.processing_status
# ---------------------------------------------------------------------------


def test_processing_status_unknown_value_rejected():
    with pytest.raises(ValueError, match="unknown value"):
        _new_reply(status="totally-invalid")


@pytest.mark.parametrize("initial", sorted(_VALID_STATUSES))
def test_processing_status_initial_assignment_allows_any(initial):
    # First assignment on a fresh instance must work for every valid value
    # (validator's "current is None" branch).
    reply = _new_reply(status=initial)
    assert reply.processing_status == initial


def _legal_transitions() -> list[tuple[str, str]]:
    return [
        (src, dst)
        for src, allowed in _ALLOWED_STATUS_TRANSITIONS.items()
        for dst in allowed
    ]


def _illegal_transitions() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for src in _VALID_STATUSES:
        allowed = _ALLOWED_STATUS_TRANSITIONS.get(src, frozenset())
        for dst in _VALID_STATUSES:
            if dst == src:
                continue  # self-assignment is always a no-op
            if dst in allowed:
                continue
            pairs.append((src, dst))
    return pairs


@pytest.mark.parametrize("src,dst", _legal_transitions())
def test_processing_status_legal_transition(src, dst):
    reply = _new_reply(status=src)
    reply.processing_status = dst
    assert reply.processing_status == dst


@pytest.mark.parametrize("src,dst", _illegal_transitions())
def test_processing_status_illegal_transition(src, dst):
    reply = _new_reply(status=src)
    with pytest.raises(ValueError, match="illegal transition"):
        reply.processing_status = dst


@pytest.mark.parametrize("terminal", ["applied", "ignored", "failed"])
def test_processing_status_terminal_states_block_any_change(terminal):
    reply = _new_reply(status=terminal)
    for other in _VALID_STATUSES:
        if other == terminal:
            continue
        with pytest.raises(ValueError, match="illegal transition"):
            reply.processing_status = other


# ---------------------------------------------------------------------------
# EtaReviewItem.resolution_state
# ---------------------------------------------------------------------------


def test_resolution_state_unknown_value_rejected():
    with pytest.raises(ValueError, match="unknown value"):
        _new_review(state="not-a-state")


@pytest.mark.parametrize("initial", sorted(_VALID_RESOLUTIONS))
def test_resolution_state_initial_assignment_allows_any(initial):
    review = _new_review(state=initial)
    assert review.resolution_state == initial


def _legal_review_transitions() -> list[tuple[str, str]]:
    return [
        (src, dst)
        for src, allowed in _ALLOWED_RESOLUTION_TRANSITIONS.items()
        for dst in allowed
    ]


def _illegal_review_transitions() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for src in _VALID_RESOLUTIONS:
        allowed = _ALLOWED_RESOLUTION_TRANSITIONS.get(src, frozenset())
        for dst in _VALID_RESOLUTIONS:
            if dst == src:
                continue
            if dst in allowed:
                continue
            pairs.append((src, dst))
    return pairs


@pytest.mark.parametrize("src,dst", _legal_review_transitions())
def test_resolution_state_legal_transition(src, dst):
    review = _new_review(state=src)
    review.resolution_state = dst
    assert review.resolution_state == dst


@pytest.mark.parametrize("src,dst", _illegal_review_transitions())
def test_resolution_state_illegal_transition(src, dst):
    review = _new_review(state=src)
    with pytest.raises(ValueError, match="illegal transition"):
        review.resolution_state = dst


@pytest.mark.parametrize("terminal", ["approved", "corrected", "dismissed"])
def test_resolution_state_terminal_blocks_any_change(terminal):
    review = _new_review(state=terminal)
    for other in _VALID_RESOLUTIONS:
        if other == terminal:
            continue
        with pytest.raises(ValueError, match="illegal transition"):
            review.resolution_state = other
