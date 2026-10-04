"""T032 + T033 — Contract tests for the deliveries-timeline OpenAPI surface.

Covers:
  - T032: ``GET /api/v1/deliveries/{id}/timeline`` shape (ordered, `since`
    filter, `limit` cap, 404 unknown, 401 without session).
  - T033: ``GET /api/v1/deliveries`` and ``GET /api/v1/deliveries/{id}``
    now return ``has_pending_review`` and ``latest_timeline_entry``.

Authentication is bypassed via FastAPI dependency overrides — the tests
focus on the response shape contract, not auth.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models.delivery import Delivery
from app.models.delivery_timeline_entry import DeliveryTimelineEntry
from app.models.supplier_order import SupplierOrder
from app.models.user import User

pytestmark = pytest.mark.asyncio


_TIMELINE_REQUIRED_FIELDS = {
    "id",
    "delivery_id",
    "event_type",
    "occurred_at",
    "actor_type",
    "created_at",
}
_TIMELINE_EVENT_TYPES = {
    "eta_confirmed",
    "eta_revised",
    "acknowledged",
    "at_risk",
    "delivered",
    "manual_override",
    "note",
}


def _stub_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="admin@example.com",
        password_hash="x",
        role="admin",
        is_active=True,
    )


async def _seed_delivery_with_timeline(test_session) -> tuple[Delivery, list[DeliveryTimelineEntry]]:
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
        current_stage="confirmed",
        stage_history=[],
        expected_delivery_at=datetime.now(timezone.utc) + timedelta(days=7),
        simulation_config={},
        has_pending_review=False,
    )
    test_session.add(delivery)
    await test_session.flush()

    base = datetime.now(timezone.utc).replace(microsecond=0)
    entries = []
    for i, ev in enumerate(["eta_confirmed", "eta_revised", "note"]):
        entry = DeliveryTimelineEntry(
            id=uuid.uuid4(),
            delivery_id=delivery.id,
            event_type=ev,
            occurred_at=base + timedelta(hours=i),
            actor_type="agent",
            actor_id="ingestor",
            supplier_excerpt=f"excerpt for {ev}",
            note="seeded" if ev == "note" else None,
        )
        test_session.add(entry)
        entries.append(entry)
    await test_session.commit()
    return delivery, entries


@pytest.fixture
async def client(test_session):
    """ASGI test client with auth + DB session overridden to the test session."""
    user = _stub_user()
    app.dependency_overrides[get_current_user] = lambda: user

    async def _get_db_override():
        yield test_session

    app.dependency_overrides[get_db] = _get_db_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# T032 — GET /deliveries/{id}/timeline
# ---------------------------------------------------------------------------


async def test_timeline_returns_ordered_entries(test_session, client):
    delivery, _ = await _seed_delivery_with_timeline(test_session)
    resp = await client.get(f"/api/v1/deliveries/{delivery.id}/timeline")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["delivery_id"] == str(delivery.id)
    entries = body["entries"]
    assert len(entries) == 3
    # Order: most-recent first (per service spec).
    occurred = [e["occurred_at"] for e in entries]
    assert occurred == sorted(occurred, reverse=True)
    for e in entries:
        missing = _TIMELINE_REQUIRED_FIELDS - set(e)
        assert not missing, f"missing fields: {missing}"
        assert e["event_type"] in _TIMELINE_EVENT_TYPES
        assert e["actor_type"] in {"agent", "admin", "simulator"}


async def test_timeline_since_filter(test_session, client):
    delivery, entries = await _seed_delivery_with_timeline(test_session)
    # The middle entry's occurred_at as the cursor: should return only
    # entries with occurred_at strictly greater.
    cursor = entries[1].occurred_at.isoformat()
    resp = await client.get(
        f"/api/v1/deliveries/{delivery.id}/timeline",
        params={"since": cursor},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["entries"]) == 1
    assert body["entries"][0]["event_type"] == "note"


async def test_timeline_limit_capped_at_200(test_session, client):
    delivery, _ = await _seed_delivery_with_timeline(test_session)
    # `limit` validates 1..200 — 201 must be rejected with 422.
    resp = await client.get(
        f"/api/v1/deliveries/{delivery.id}/timeline",
        params={"limit": 201},
    )
    assert resp.status_code == 422


async def test_timeline_404_unknown_delivery(client):
    resp = await client.get(f"/api/v1/deliveries/{uuid.uuid4()}/timeline")
    assert resp.status_code == 404


async def test_timeline_401_without_session(test_session):
    """Without the auth override, the endpoint must reject anonymous calls."""

    async def _get_db_override():
        yield test_session

    app.dependency_overrides[get_db] = _get_db_override
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(f"/api/v1/deliveries/{uuid.uuid4()}/timeline")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# T033 — DeliveryResponse additions
# ---------------------------------------------------------------------------


async def test_delivery_list_includes_pending_flag_and_latest_entry(
    test_session, client
):
    delivery, entries = await _seed_delivery_with_timeline(test_session)
    resp = await client.get("/api/v1/deliveries")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    rows = [d for d in body["deliveries"] if d["id"] == str(delivery.id)]
    assert len(rows) == 1
    row = rows[0]
    assert "has_pending_review" in row
    assert row["has_pending_review"] is False
    assert "latest_timeline_entry" in row
    latest = row["latest_timeline_entry"]
    assert latest is not None
    assert latest["event_type"] == "note"  # last-by-occurred_at


async def test_delivery_detail_includes_additions(test_session, client):
    delivery, _ = await _seed_delivery_with_timeline(test_session)
    resp = await client.get(f"/api/v1/deliveries/{delivery.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["has_pending_review"] is False
    assert body["latest_timeline_entry"]["event_type"] == "note"
