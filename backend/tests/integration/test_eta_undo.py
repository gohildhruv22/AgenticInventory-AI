"""T022 — Undo / rollback of an applied ETA update.

Drives the full happy path through ``run_ingestor_cycle`` so an
``action_logs`` row with ``action_type='delivery.eta_update'`` is
written, then calls
:meth:`RollbackService._execute_compensating_action` and asserts the
delivery's pre-update state is restored byte-for-byte and a
``manual_override`` timeline entry is appended (constitution III).
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
from app.models.action_log import ActionLog
from app.models.delivery import Delivery
from app.models.delivery_timeline_entry import DeliveryTimelineEntry
from app.models.supplier_order import SupplierOrder
from app.services.eta_ingestor import run_ingestor_cycle
from app.services.rollback_service import RollbackService


pytestmark = pytest.mark.asyncio


def _raw_message(uid: str, subject: str, body: str) -> RawMessage:
    return RawMessage(
        uid=uid,
        message_id=f"<{uid}@example.com>",
        from_address="supplier@example.com",
        subject=subject,
        date=datetime.now(timezone.utc).isoformat(),
        body_text=body,
        headers={},
    )


async def test_undo_restores_eta_byte_for_byte(
    test_session, stub_model_client
) -> None:
    # --- seed order + delivery in "ordered" state with a known ETA ---
    original_eta_aware = (datetime.now(timezone.utc) + timedelta(days=21)).replace(
        microsecond=0
    )
    order = SupplierOrder(
        id=uuid.uuid4(),
        decision_id=uuid.uuid4(),
        supplier_name="ACME",
        supplier_email="supplier@example.com",
        items=[{"sku": "A", "name": "thing", "quantity": 1}],
        total_cost=Decimal("10.00"),
        email_status="sent",
    )
    test_session.add(order)
    await test_session.flush()

    delivery = Delivery(
        id=uuid.uuid4(),
        order_id=order.id,
        current_stage="ordered",
        stage_history=[],
        expected_delivery_at=original_eta_aware,
        simulation_config={},
        has_pending_review=False,
    )
    test_session.add(delivery)
    await test_session.commit()

    original_stage = delivery.current_stage
    # SQLite drops tzinfo on round-trip; capture both forms for comparison.
    await test_session.refresh(delivery)
    original_eta_stored = delivery.expected_delivery_at

    # --- run a cycle that auto-applies a confirm ---
    new_eta = (datetime.now(timezone.utc) + timedelta(days=7)).replace(microsecond=0)
    fake = FakeImapClient(
        [_raw_message("1", f"Re: Order #{order.id}", "confirmed for new date")]
    )
    await fake.connect("h", 993, "u", "p")
    stub_model_client.set_responses(
        [
            {
                "intent": "confirm",
                "parsed_date": new_eta.isoformat(),
                "confidence": 95.0,
                "excerpt": "we confirm",
                "reasoning": "ok",
            }
        ]
    )
    agent = DeliveryEtaAgent()
    try:
        summary = await run_ingestor_cycle(
            session=test_session, client=fake, agent=agent, threshold=80.0
        )
    finally:
        await agent.close()
    assert summary.auto_applied == 1

    # --- locate the action_log row ---
    action_log = (
        await test_session.execute(
            select(ActionLog).where(ActionLog.action_type == "delivery.eta_update")
        )
    ).scalar_one()
    assert action_log.compensating_action is not None
    assert action_log.compensating_action.get("type") == "restore_eta"

    # --- delivery state was mutated ---
    await test_session.refresh(delivery)
    assert delivery.current_stage == "confirmed"
    assert delivery.expected_delivery_at != original_eta_stored

    # --- invoke the compensating action ---
    svc = RollbackService(test_session)
    result = await svc._execute_compensating_action(action_log)
    await test_session.commit()
    assert result.get("action") in {"restore_eta", "restore_eta_skipped"} or result
    # Spec: byte-for-byte restoration.
    await test_session.refresh(delivery)
    assert delivery.current_stage == original_stage
    assert delivery.expected_delivery_at == original_eta_stored

    # --- manual_override timeline entry appended ---
    entries = (
        await test_session.execute(
            select(DeliveryTimelineEntry).where(
                DeliveryTimelineEntry.delivery_id == delivery.id
            )
        )
    ).scalars().all()
    assert any(
        e.event_type == "manual_override" and e.actor_type == "admin"
        for e in entries
    ), [e.event_type for e in entries]
