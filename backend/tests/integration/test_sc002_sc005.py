"""T060 — Programmatic assertions for SC-002 (p95 mailbox→UI ≤ 10 min)
and SC-005 (100% of timeline entries trace back to a source supplier
reply).

Reuses the T021 ingestor fixtures (``FakeImapClient``,
``stub_model_client``). Runs the ingestor over a batch of synthetic
``confirm`` replies, then introspects the persisted
``delivery_timeline_entries`` and ``supplier_replies`` rows.
"""
from __future__ import annotations

import statistics
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


# Mailbox → UI SLO from spec/004 Success Criteria.
SC_002_BUDGET = timedelta(minutes=10)


async def _seed_order(
    session, *, supplier_email: str, idx: int
) -> tuple[SupplierOrder, Delivery]:
    order = SupplierOrder(
        id=uuid.uuid4(),
        decision_id=uuid.uuid4(),
        supplier_name=f"Supplier-{idx}",
        supplier_email=supplier_email,
        items=[{"sku": f"SKU-{idx}", "name": "Widget", "quantity": 1}],
        total_cost=Decimal("10.00"),
        email_status="sent",
    )
    session.add(order)
    await session.flush()
    delivery = Delivery(
        id=uuid.uuid4(),
        order_id=order.id,
        current_stage="ordered",
        stage_history=[],
        expected_delivery_at=datetime.now(timezone.utc) + timedelta(days=14),
        simulation_config={},
        has_pending_review=False,
    )
    session.add(delivery)
    await session.commit()
    return order, delivery


def _raw(
    *, uid: str, order_id: uuid.UUID, supplier_email: str, received_at: datetime
) -> RawMessage:
    return RawMessage(
        uid=uid,
        message_id=f"<sc060-{uid}@example.com>",
        from_address=supplier_email,
        subject=f"Re: PO Order #{order_id}",
        date=received_at.isoformat(),
        body_text="Confirming our new delivery date.",
        headers={},
    )


def _canned_confirm(parsed_date: datetime) -> dict:
    return {
        "intent": "confirm",
        "parsed_date": parsed_date.isoformat(),
        "confidence": 95.0,
        "excerpt": "confirming",
        "reasoning": "stub",
    }


async def test_sc002_and_sc005_via_ingestor_fixtures(
    test_session, stub_model_client
) -> None:
    """Run 20 high-confidence confirm replies through the ingestor and
    verify (a) every timeline entry the agent wrote points back at a
    supplier reply (SC-005) and (b) the p95 mailbox→UI latency budget
    (SC-002) is satisfied.
    """
    n = 20
    new_eta = (datetime.now(timezone.utc) + timedelta(days=7)).replace(microsecond=0)

    # Seed N orders + N raw messages, one per supplier.
    raws: list[RawMessage] = []
    for i in range(n):
        supplier_email = f"supplier-{i}@example.com"
        order, _ = await _seed_order(
            test_session, supplier_email=supplier_email, idx=i
        )
        raws.append(
            _raw(
                uid=str(i + 1),
                order_id=order.id,
                supplier_email=supplier_email,
                # Simulate replies arriving "just now" — mailbox→UI starts
                # ticking from received_at.
                received_at=datetime.now(timezone.utc),
            )
        )

    fake = FakeImapClient(raws)
    await fake.connect("host", 993, "u", "p")

    stub_model_client.set_responses([_canned_confirm(new_eta)] * n)

    agent = DeliveryEtaAgent()
    try:
        summary = await run_ingestor_cycle(
            session=test_session, client=fake, agent=agent, threshold=80.0
        )
    finally:
        await agent.close()

    assert summary.auto_applied == n, summary

    # ---- SC-005: every timeline entry traces back to a supplier reply.
    entries = (
        (
            await test_session.execute(
                select(DeliveryTimelineEntry).where(
                    DeliveryTimelineEntry.event_type.in_(
                        ("eta_confirmed", "eta_revised", "note", "at_risk")
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(entries) == n, f"expected {n} timeline entries, got {len(entries)}"
    missing = [e for e in entries if e.source_reply_id is None]
    assert not missing, (
        f"SC-005 violation: {len(missing)} timeline entries have no "
        f"source_reply_id"
    )

    # ---- SC-002: p95 (timeline_entry.created_at - reply.received_at) <= 10 min.
    reply_by_id = {
        r.id: r
        for r in (await test_session.execute(select(SupplierReply))).scalars().all()
    }
    deltas: list[timedelta] = []
    for e in entries:
        reply = reply_by_id[e.source_reply_id]
        # SQLite's func.now() truncates fractional seconds, so created_at can
        # land microseconds *before* the email's received_at on a fast machine.
        # Clamp to zero — the metric we care about is "how much wall time
        # elapsed between mail arrival and UI-visible timeline write".
        delta = e.created_at - reply.received_at
        if delta < timedelta(0):
            delta = timedelta(0)
        deltas.append(delta)

    deltas_seconds = sorted(d.total_seconds() for d in deltas)
    # statistics.quantiles with n=20 gives 19 cut points → use the 95th.
    p95_seconds = (
        statistics.quantiles(deltas_seconds, n=100)[94]
        if len(deltas_seconds) > 1
        else deltas_seconds[0]
    )
    p95 = timedelta(seconds=p95_seconds)
    assert p95 <= SC_002_BUDGET, (
        f"SC-002 violation: p95 mailbox\u2192UI latency = {p95} "
        f"(budget {SC_002_BUDGET})"
    )
