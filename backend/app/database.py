from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    # Enable WAL journaling so the autonomous loop and the API request
    # handlers can write concurrently without hitting "database is locked".
    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_set_pragmas(dbapi_connection, _connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        connect_args={"timeout": 5},
    )

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Convenience alias used by auto_seed_demo_data() and tests
AsyncSessionLocal = async_session_factory


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Auto-create all tables. Used on startup for SQLite / quick-start setups.

    For production (Postgres on Azure), use Alembic migrations instead.
    """
    from app import models  # noqa: F401 — register models with Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def auto_seed_demo_data() -> int:
    """Populate the inventory table with demo data if it's empty.

    Returns the number of items inserted (0 if already seeded).
    Safe to call on every startup — it only seeds when the table is empty.
    """
    from sqlalchemy import select, func
    from app.api.seed import SEED_ITEMS
    from app.models.inventory_item import InventoryItem

    async with AsyncSessionLocal() as session:
        count = (await session.execute(select(func.count(InventoryItem.id)))).scalar_one()
        if count > 0:
            return 0

        for item_data in SEED_ITEMS:
            session.add(InventoryItem(**item_data))
        await session.commit()
        return len(SEED_ITEMS)


async def auto_seed_demo_activity() -> dict:
    """Populate agent decisions, forecasts, supplier orders, deliveries, and KPI
    reports with demo data so the Analytics / Decisions / Reports pages have
    something compelling to show.

    Skips seeding if AgentDecision already has any rows. Returns a dict of
    counts per table inserted.
    """
    import random
    import uuid
    from datetime import date, datetime, timedelta, timezone
    from decimal import Decimal

    from sqlalchemy import delete, select, func
    from app.models.agent_decision import AgentDecision
    from app.models.delivery import Delivery
    from app.models.forecast import Forecast
    from app.models.inventory_item import InventoryItem
    from app.models.kpi_report import KPIReport
    from app.models.supplier_order import SupplierOrder

    rng = random.Random(42)  # deterministic demo data
    counts = {
        "decisions": 0,
        "forecasts": 0,
        "orders": 0,
        "deliveries": 0,
        "reports": 0,
    }

    async with AsyncSessionLocal() as session:
        # Skip if decisions already exist
        existing = (
            await session.execute(select(func.count(AgentDecision.id)))
        ).scalar_one()
        if existing > 0:
            return counts

        items = (await session.execute(select(InventoryItem))).scalars().all()
        if not items:
            return counts

        # Clear out any leftover rows from prior partial seeds / manual triggers
        # so the seeder produces a clean, consistent demo dataset.
        await session.execute(delete(Delivery))
        await session.execute(delete(SupplierOrder))
        await session.execute(delete(KPIReport))
        await session.execute(delete(Forecast))
        await session.flush()

        now = datetime.now(timezone.utc)

        AGENT_TYPES = [
            "decision_manager",
            "forecast",
            "monitoring",
            "supplier_email",
            "delivery_tracker",
            "reporting_kpi",
        ]
        STATUSES = ["approved", "executed", "flagged", "rejected", "rolled_back"]
        STATUS_WEIGHTS = [0.45, 0.25, 0.15, 0.10, 0.05]
        ACTION_BY_AGENT = {
            "decision_manager": ["approve_order", "flag_for_review", "reject_order"],
            "forecast": ["generate_forecast", "update_forecast"],
            "monitoring": ["detect_low_stock", "detect_anomaly"],
            "supplier_email": ["send_purchase_order", "send_admin_alert"],
            "delivery_tracker": ["update_delivery_stage", "mark_delivered"],
            "reporting_kpi": ["generate_daily_report", "summarize_kpis"],
        }
        SUPPLIERS = {
            "Electronics": ("TechSupply Co.", "orders@techsupply.com"),
            "Office Supplies": ("Office World Inc.", "sales@officeworld.com"),
            "Raw Materials": ("MetalWorks Ltd.", "procurement@metalworks.com"),
            "Food & Beverage": ("Fresh Goods Co.", "orders@freshgoods.com"),
            "Cleaning Supplies": ("CleanPro Bulk", "bulk@cleanpro.com"),
        }

        decisions_created: list[AgentDecision] = []

        # ── Generate 60 decisions across the last 7 days ────────────────
        for _ in range(60):
            days_ago = rng.randint(0, 6)
            hours_ago = rng.randint(0, 23)
            created_at = now - timedelta(days=days_ago, hours=hours_ago)

            agent_type = rng.choice(AGENT_TYPES)
            status = rng.choices(STATUSES, weights=STATUS_WEIGHTS, k=1)[0]
            action_type = rng.choice(ACTION_BY_AGENT[agent_type])
            item = rng.choice(items)
            confidence = Decimal(str(round(rng.uniform(55, 98), 2)))

            reasoning_trace = {
                "input_context": f"Stock check for {item.name} ({item.sku})",
                "reasoning": (
                    f"Current stock is {item.current_stock} units against a reorder "
                    f"threshold of {item.reorder_threshold}. "
                    + (
                        "Triggering reorder workflow."
                        if item.current_stock <= item.reorder_threshold
                        else "Stock levels are healthy — no action required."
                    )
                ),
                "confidence": float(confidence),
                "item_context": {
                    "name": item.name,
                    "sku": item.sku,
                    "category": item.category,
                    "current_stock": item.current_stock,
                    "reorder_threshold": item.reorder_threshold,
                },
                "data_sources": ["inventory_snapshot", "historical_velocity", "supplier_lead_time"],
            }
            alternatives = [
                {"option": "Reorder full case", "score": round(rng.uniform(0.6, 0.95), 2)},
                {"option": "Defer to next cycle", "score": round(rng.uniform(0.2, 0.6), 2)},
                {"option": "Split order across suppliers", "score": round(rng.uniform(0.3, 0.7), 2)},
            ]

            d = AgentDecision(
                id=uuid.uuid4(),
                agent_type=agent_type,
                action_type=action_type,
                inventory_item_id=item.id,
                forecast_id=None,
                reasoning_trace=reasoning_trace,
                confidence_level=confidence,
                alternatives_considered=alternatives,
                status=status,
                metadata_={"seeded": True},
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(d)
            decisions_created.append(d)
            counts["decisions"] += 1

        await session.flush()

        # ── Generate 25 forecasts over the last 7 days ──────────────────
        TREND_DIRECTIONS = ["up", "down", "stable"]
        for _ in range(25):
            item = rng.choice(items)
            days_ago = rng.randint(0, 6)
            created_at = now - timedelta(days=days_ago, hours=rng.randint(0, 23))
            predicted = rng.randint(max(5, item.reorder_threshold // 2), item.reorder_threshold * 3)
            confidence = Decimal(str(round(rng.uniform(60, 96), 2)))
            suggested_qty = max(item.reorder_threshold * 2 - item.current_stock, 10)

            f = Forecast(
                id=uuid.uuid4(),
                inventory_item_id=item.id,
                predicted_demand=predicted,
                confidence_score=confidence,
                suggested_order_qty=suggested_qty,
                reasoning=(
                    f"Based on 30-day demand velocity and current stock of {item.current_stock}, "
                    f"projecting {predicted} units demand in next lead time window."
                ),
                trends_score=Decimal(str(round(rng.uniform(40, 90), 2))),
                trend_direction=rng.choice(TREND_DIRECTIONS),
                news_sentiment=Decimal(str(round(rng.uniform(-1, 1), 2))),
                weather_impact=Decimal(str(round(rng.uniform(0, 20), 2))),
                holiday_proximity=rng.choice([None, 3, 7, 14, 30]),
                holiday_name=rng.choice([None, "Black Friday", "Year-End", "Summer Peak"]),
                staleness_flags=[],
                raw_signals={"velocity_30d": rng.randint(10, 200)},
                created_at=created_at,
            )
            session.add(f)
            counts["forecasts"] += 1

        await session.flush()

        # ── Generate supplier orders from a subset of approved decisions ─
        approved_or_executed = [
            d for d in decisions_created if d.status in ("approved", "executed", "rolled_back")
        ][:18]
        EMAIL_STATUSES = ["sent", "sent", "sent", "sent", "queued", "failed"]

        orders_created: list[SupplierOrder] = []
        for d in approved_or_executed:
            item = next((it for it in items if it.id == d.inventory_item_id), rng.choice(items))
            supplier_name, supplier_email = SUPPLIERS.get(
                item.category, ("Generic Supplier", "orders@example.com")
            )
            qty = rng.randint(10, 80)
            total = (item.unit_cost or Decimal("10.00")) * qty

            order = SupplierOrder(
                id=uuid.uuid4(),
                decision_id=d.id,
                supplier_name=supplier_name,
                supplier_email=supplier_email,
                items=[
                    {
                        "name": item.name,
                        "sku": item.sku,
                        "category": item.category,
                        "quantity": qty,
                        "unit_cost": float(item.unit_cost or 0),
                    }
                ],
                total_cost=total,
                email_status=rng.choice(EMAIL_STATUSES),
                email_message_id=f"<{uuid.uuid4()}@agenticinventory.ai>",
                retry_count=rng.choice([0, 0, 0, 1, 2]),
                created_at=d.created_at,
                updated_at=d.created_at,
            )
            session.add(order)
            orders_created.append(order)
            counts["orders"] += 1

        await session.flush()

        # ── Generate deliveries for ~70% of orders ──────────────────────
        DELIVERY_STAGES = [
            "ordered",
            "confirmed",
            "shipped",
            "in_transit",
            "out_for_delivery",
            "delivered",
            "delivered",
            "failed",
        ]
        for order in orders_created[: int(len(orders_created) * 0.75)]:
            stage = rng.choice(DELIVERY_STAGES)
            expected = order.created_at + timedelta(days=rng.randint(3, 14))
            actual = expected if stage == "delivered" else None
            stage_history = [
                {
                    "stage": "ordered",
                    "at": order.created_at.isoformat(),
                    "note": "Purchase order generated by Decision Manager",
                }
            ]
            if stage != "ordered":
                stage_history.append(
                    {
                        "stage": stage,
                        "at": (order.created_at + timedelta(days=rng.randint(1, 5))).isoformat(),
                        "note": "Stage updated by Delivery Tracker agent",
                    }
                )

            delivery = Delivery(
                id=uuid.uuid4(),
                order_id=order.id,
                current_stage=stage,
                stage_history=stage_history,
                expected_delivery_at=expected,
                actual_delivery_at=actual,
                items_received=order.items if stage == "delivered" else None,
                simulation_config={"seeded": True},
                created_at=order.created_at,
                updated_at=order.created_at + timedelta(days=1),
            )
            session.add(delivery)
            counts["deliveries"] += 1

        await session.flush()

        # ── Generate 7 daily KPI reports (last 7 days) ──────────────────
        # Idempotent: any report_date that already exists is skipped to
        # avoid UNIQUE constraint violations on re-seed.
        existing_report_dates = set(
            (
                await session.execute(select(KPIReport.report_date))
            ).scalars().all()
        )
        for days_ago in range(7):
            report_date = (now - timedelta(days=days_ago)).date()
            if report_date in existing_report_dates:
                continue
            day_orders = [o for o in orders_created if o.created_at.date() == report_date]
            day_decisions = [d for d in decisions_created if d.created_at.date() == report_date]

            order_volume = len(day_orders)
            total_spend = sum((o.total_cost for o in day_orders), Decimal("0"))
            approved = sum(1 for d in day_decisions if d.status == "approved")
            flagged = sum(1 for d in day_decisions if d.status == "flagged")
            rolled_back = sum(1 for d in day_decisions if d.status == "rolled_back")
            confidences = [d.confidence_level for d in day_decisions if d.confidence_level]
            avg_conf = (
                Decimal(str(round(sum(c for c in confidences) / len(confidences), 2)))
                if confidences
                else None
            )
            sent_orders = sum(1 for o in day_orders if o.email_status == "sent")
            delivery_rate = (
                Decimal(str(round(sent_orders / len(day_orders) * 100, 2)))
                if day_orders
                else None
            )

            supplier_perf: dict = {}
            for o in day_orders:
                s = supplier_perf.setdefault(
                    o.supplier_name, {"orders": 0, "spend": 0.0}
                )
                s["orders"] += 1
                s["spend"] += float(o.total_cost)

            agent_activity: dict = {}
            for d in day_decisions:
                agent_activity[d.agent_type] = agent_activity.get(d.agent_type, 0) + 1

            report = KPIReport(
                id=uuid.uuid4(),
                report_date=report_date,
                order_volume=order_volume,
                total_spend=total_spend,
                forecast_accuracy=Decimal(str(round(rng.uniform(78, 94), 2))),
                avg_confidence_score=avg_conf,
                decisions_approved=approved,
                decisions_flagged=flagged,
                decisions_rolled_back=rolled_back,
                deliveries_completed=rng.randint(0, max(1, order_volume)),
                deliveries_failed=rng.randint(0, 2),
                supplier_performance=supplier_perf,
                agent_activity=agent_activity,
                email_delivery_rate=delivery_rate,
                cost_savings_estimate=Decimal(str(round(rng.uniform(200, 3500), 2))),
                email_sent=days_ago > 0,  # today not yet emailed
                email_sent_at=(now - timedelta(days=days_ago)) if days_ago > 0 else None,
                email_recipients=["admin@agenticinventory.ai"] if days_ago > 0 else [],
                report_data={
                    "generated_at": (now - timedelta(days=days_ago)).isoformat(),
                    "seeded": True,
                },
                created_at=now - timedelta(days=days_ago),
            )
            session.add(report)
            counts["reports"] += 1

        await session.commit()
        return counts
