"""T021 — ETA ingestor integration tests.

Exercises the end-to-end ``run_ingestor_cycle`` path using
:class:`FakeImapClient` and a stubbed :class:`DeliveryEtaAgent` against
the real (test) SQLite DB.

Sub-cases (mapped to feature 004 FRs):
  (a) auto-apply for a high-confidence ``confirm`` (FR-001/FR-004);
  (b) idempotency: duplicate ``Message-Id`` is persisted exactly once (FR-007);
  (c) machine-generated mail is ignored (FR-008);
  (d) reply that arrives after the order delivered → ``note``-only,
      ``expected_delivery_at`` unchanged (FR-006).

(e) IMAP fetch-retry and (f) date-range disambiguation are covered by
the lower-level imap and agent tests respectively.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.agents.delivery_eta import DeliveryEtaAgent
from app.email._imap_fake import FakeImapClient
from app.email.imap import RawMessage
from app.models.delivery import Delivery
from app.models.delivery_timeline_entry import DeliveryTimelineEntry
from app.models.supplier_order import SupplierOrder
from app.models.supplier_reply import SupplierReply
from app.services.eta_ingestor import run_ingestor_cycle


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _make_order_and_delivery(
    session,
    *,
    supplier_email: str = "supplier@example.com",
    current_stage: str = "ordered",
    expected_delivery_at: datetime | None = None,
) -> tuple[SupplierOrder, Delivery]:
    order = SupplierOrder(
        id=uuid.uuid4(),
        decision_id=uuid.uuid4(),
        supplier_name="ACME Supplies",
        supplier_email=supplier_email,
        items=[{"sku": "SKU-1", "name": "Widget", "quantity": 10}],
        total_cost=Decimal("123.45"),
        email_status="sent",
    )
    session.add(order)
    await session.flush()

    delivery = Delivery(
        id=uuid.uuid4(),
        order_id=order.id,
        current_stage=current_stage,
        stage_history=[],
        expected_delivery_at=expected_delivery_at or (
            datetime.now(timezone.utc) + timedelta(days=14)
        ),
        simulation_config={},
        has_pending_review=False,
    )
    session.add(delivery)
    await session.commit()
    return order, delivery


def _raw_message(
    *,
    uid: str,
    subject: str,
    body: str,
    from_address: str = "supplier@example.com",
    message_id: str | None = None,
    headers: dict[str, str] | None = None,
) -> RawMessage:
    msg_id = (
        message_id
        if message_id is not None
        else f"<msg-{uid}@example.com>"
    )
    return RawMessage(
        uid=str(uid),
        message_id=msg_id,
        from_address=from_address,
        subject=subject,
        date=datetime.now(timezone.utc).isoformat(),
        body_text=body,
        headers=headers or {},
    )


def _canned_extraction(intent: str, *, parsed_date: str | None, confidence: float) -> dict:
    return {
        "intent": intent,
        "parsed_date": parsed_date,
        "confidence": confidence,
        "excerpt": "test excerpt",
        "reasoning": "test reasoning",
    }


# ---------------------------------------------------------------------------
# (a) high-confidence confirm → auto-apply
# ---------------------------------------------------------------------------


async def test_ingestor_auto_applies_high_confidence_confirm(
    test_session, stub_model_client
) -> None:
    order, delivery = await _make_order_and_delivery(test_session)
    original_eta = delivery.expected_delivery_at
    new_eta = (datetime.now(timezone.utc) + timedelta(days=7)).replace(microsecond=0)

    fake = FakeImapClient(
        [
            _raw_message(
                uid="1",
                subject=f"Re: PO Order #{order.id}",
                body="We confirm delivery on the new date.",
            )
        ]
    )
    await fake.connect("host", 993, "u", "p")

    stub_model_client.set_responses(
        [_canned_extraction("confirm", parsed_date=new_eta.isoformat(), confidence=95.0)]
    )

    agent = DeliveryEtaAgent()
    try:
        summary = await run_ingestor_cycle(
            session=test_session, client=fake, agent=agent, threshold=80.0
        )
    finally:
        await agent.close()

    assert summary.auto_applied == 1, summary
    assert summary.raised_reviews == 0

    await test_session.refresh(delivery)
    assert delivery.current_stage == "confirmed"
    assert delivery.expected_delivery_at != original_eta
    # Reply persisted with status applied.
    reply = (
        await test_session.execute(select(SupplierReply))
    ).scalar_one()
    assert reply.processing_status == "applied"
    # Timeline entry created.
    entries = (
        await test_session.execute(
            select(DeliveryTimelineEntry).where(
                DeliveryTimelineEntry.delivery_id == delivery.id
            )
        )
    ).scalars().all()
    assert any(e.event_type == "eta_confirmed" for e in entries)
    # IMAP marked seen.
    assert fake.mark_seen_calls == ["1"]


# ---------------------------------------------------------------------------
# (b) idempotent on duplicate Message-Id (FR-007)
# ---------------------------------------------------------------------------


async def test_ingestor_dedupes_duplicate_message_id(
    test_session, stub_model_client
) -> None:
    order, delivery = await _make_order_and_delivery(test_session)
    dup_id = "<duplicate-id@example.com>"
    new_eta = (datetime.now(timezone.utc) + timedelta(days=10)).replace(microsecond=0)

    fake = FakeImapClient(
        [
            _raw_message(
                uid="1",
                subject=f"Re: Order #{order.id}",
                body="confirm",
                message_id=dup_id,
            ),
            _raw_message(
                uid="2",
                subject=f"Re: Order #{order.id} (resent)",
                body="confirm again",
                message_id=dup_id,  # same Message-Id
            ),
        ]
    )
    await fake.connect("host", 993, "u", "p")

    stub_model_client.set_responses(
        [_canned_extraction("confirm", parsed_date=new_eta.isoformat(), confidence=95.0)]
    )

    agent = DeliveryEtaAgent()
    try:
        summary = await run_ingestor_cycle(
            session=test_session, client=fake, agent=agent, threshold=80.0
        )
    finally:
        await agent.close()

    assert summary.persisted == 1
    assert summary.duplicates == 1
    # Both UIDs marked seen so the inbox doesn't redeliver them.
    assert set(fake.mark_seen_calls) == {"1", "2"}
    # Only ONE supplier_replies row.
    rows = (await test_session.execute(select(SupplierReply))).scalars().all()
    assert len(rows) == 1
    # Only ONE auto-applied timeline entry of type eta_confirmed.
    entries = (
        await test_session.execute(
            select(DeliveryTimelineEntry).where(
                DeliveryTimelineEntry.delivery_id == delivery.id,
                DeliveryTimelineEntry.event_type == "eta_confirmed",
            )
        )
    ).scalars().all()
    assert len(entries) == 1


# ---------------------------------------------------------------------------
# (c) auto-replies / bounces are ignored (FR-008)
# ---------------------------------------------------------------------------


async def test_ingestor_ignores_auto_submitted(test_session, stub_model_client) -> None:
    order, delivery = await _make_order_and_delivery(test_session)

    fake = FakeImapClient(
        [
            _raw_message(
                uid="1",
                subject=f"Auto: Re: Order #{order.id}",
                body="I am out of office.",
                from_address="ooo@example.com",
                headers={"Auto-Submitted": "auto-replied"},
            )
        ]
    )
    await fake.connect("host", 993, "u", "p")
    stub_model_client.set_responses([])  # agent must NOT be called

    agent = DeliveryEtaAgent()
    try:
        summary = await run_ingestor_cycle(
            session=test_session, client=fake, agent=agent, threshold=80.0
        )
    finally:
        await agent.close()

    assert summary.ignored == 1
    assert summary.auto_applied == 0
    assert summary.raised_reviews == 0

    reply = (await test_session.execute(select(SupplierReply))).scalar_one()
    assert reply.processing_status == "ignored"
    # No timeline writes either.
    entries = (
        await test_session.execute(
            select(DeliveryTimelineEntry).where(
                DeliveryTimelineEntry.delivery_id == delivery.id
            )
        )
    ).scalars().all()
    assert entries == []


# ---------------------------------------------------------------------------
# (d) reply after delivery → note only, expected_delivery_at unchanged
# ---------------------------------------------------------------------------


async def test_ingestor_writes_note_only_when_already_delivered(
    test_session, stub_model_client
) -> None:
    original_eta = datetime.now(timezone.utc) - timedelta(days=2)
    order, delivery = await _make_order_and_delivery(
        test_session,
        current_stage="delivered",
        expected_delivery_at=original_eta,
    )

    fake = FakeImapClient(
        [
            _raw_message(
                uid="1",
                subject=f"Re: Order #{order.id} — sorry, delayed!",
                body="actually the date moved",
            )
        ]
    )
    await fake.connect("host", 993, "u", "p")
    stub_model_client.set_responses([])  # agent MUST NOT be called for delivered orders

    agent = DeliveryEtaAgent()
    try:
        summary = await run_ingestor_cycle(
            session=test_session, client=fake, agent=agent, threshold=80.0
        )
    finally:
        await agent.close()

    assert summary.delivered_notes == 1
    assert summary.auto_applied == 0

    await test_session.refresh(delivery)
    # Stage unchanged.
    assert delivery.current_stage == "delivered"
    # ETA unchanged (SQLite drops tzinfo on round-trip; compare naive form).
    stored = delivery.expected_delivery_at
    if stored is not None and stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    assert stored is not None
    assert abs((stored - original_eta).total_seconds()) < 1
    # Exactly one `note` timeline row.
    entries = (
        await test_session.execute(
            select(DeliveryTimelineEntry).where(
                DeliveryTimelineEntry.delivery_id == delivery.id
            )
        )
    ).scalars().all()
    assert [e.event_type for e in entries] == ["note"]
