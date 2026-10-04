"""Autonomous inventory monitoring loop using FastAPI BackgroundTasks.

Replaces Celery periodic tasks with an async background loop that:
- Scans all active inventory items every configurable interval
- Detects threshold breaches via the Inventory Monitoring Agent
- Triggers the forecasting pipeline for breached items
- Broadcasts real-time events via WebSocket
- Logs full pipeline reasoning traces
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.inventory_monitor import InventoryMonitorAgent, MonitoringResult
from app.config import get_settings
from app.database import async_session_factory
from app.models.agent_decision import AgentDecision
from app.models.inventory_item import InventoryItem
from app.services.decision_service import DecisionService
from app.services.forecast_service import ForecastService
from app.services.order_service import OrderService
from app.websocket.manager import ws_manager

logger = logging.getLogger("agenticinventory.monitoring")

# Module-level state for the monitoring loop
_monitoring_task: asyncio.Task | None = None
_monitoring_active: bool = False

# Default interval (seconds) between monitoring cycles
DEFAULT_INTERVAL_SECONDS = 60


async def _get_active_items(db: AsyncSession) -> list[InventoryItem]:
    """Fetch all active inventory items."""
    result = await db.execute(
        select(InventoryItem).where(InventoryItem.is_active == True)  # noqa: E712
    )
    return list(result.scalars().all())


def _item_to_dict(item: InventoryItem) -> dict:
    """Convert an InventoryItem ORM instance to a plain dict for the agent."""
    return {
        "id": str(item.id),
        "name": item.name,
        "sku": item.sku,
        "category": item.category,
        "current_stock": item.current_stock,
        "reorder_threshold": item.reorder_threshold,
        "safety_stock": item.safety_stock,
        "lead_time_days": item.lead_time_days,
        "unit_cost": float(item.unit_cost),
        "status": item.status,
    }


async def _persist_monitoring_decision(
    db: AsyncSession,
    monitoring_result: MonitoringResult,
) -> AgentDecision:
    """Persist the monitoring analysis as an AgentDecision with reasoning trace."""
    decision = AgentDecision(
        agent_type="inventory_monitor",
        action_type="stock_scan",
        reasoning_trace={
            "analysis_summary": monitoring_result.analysis_summary,
            "total_items_checked": monitoring_result.total_items_checked,
            "breaches_detected": monitoring_result.breaches_detected,
            "items_at_risk": monitoring_result.items_at_risk,
            "reasoning": monitoring_result.reasoning,
            "timestamp": monitoring_result.timestamp,
        },
        confidence_level=None,
        alternatives_considered=[],
        status="executed",
        metadata_={
            "trigger": "autonomous_loop",
            "cycle_timestamp": monitoring_result.timestamp,
        },
    )
    db.add(decision)
    await db.flush()
    return decision


async def _broadcast_monitoring_cycle(
    monitoring_result: MonitoringResult,
    decision_id: UUID,
    pipeline_logs: list[dict],
) -> None:
    """Broadcast monitoring results and pipeline status via WebSocket."""
    await ws_manager.broadcast_all(
        "monitoring:cycle_complete",
        {
            "decision_id": str(decision_id),
            "total_items_checked": monitoring_result.total_items_checked,
            "breaches_detected": monitoring_result.breaches_detected,
            "items_at_risk": monitoring_result.items_at_risk,
            "analysis_summary": monitoring_result.analysis_summary,
            "timestamp": monitoring_result.timestamp,
        },
    )

    # Broadcast individual pipeline logs
    for log_entry in pipeline_logs:
        await ws_manager.broadcast_all("pipeline:log", log_entry)


async def _run_pipeline_for_breach(
    db: AsyncSession,
    item_id_str: str,
    item_name: str,
    sku: str,
    pipeline_logs: list[dict],
) -> None:
    """Trigger the full agent pipeline for a single breached item.

    Stages (all LLM-driven):
      1. Demand Forecast Agent  → predicted demand + confidence
      2. Decision Manager Agent → approve / flag / reject + reasoning
      3. Supplier Email Agent   → composes & sends PO email (only if approved)
    """
    settings = get_settings()

    # ── Stage 1: Forecast ──────────────────────────────────────
    forecast_log = {
        "stage": "forecast",
        "item_id": item_id_str,
        "item_name": item_name,
        "sku": sku,
        "status": "started",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    pipeline_logs.append(forecast_log)

    forecast = None
    try:
        forecast_svc = ForecastService(db)
        forecast = await forecast_svc.generate_forecast(UUID(item_id_str))
        # Commit immediately so the SQLite write lock is released before
        # the next LLM call — otherwise concurrent writers (e.g. the API
        # /pipeline/trigger handler) hit "database is locked".
        await db.commit()

        forecast_log.update({
            "status": "completed",
            "forecast_id": str(forecast.id),
            "predicted_demand": forecast.predicted_demand,
            "confidence_score": float(forecast.confidence_score),
            "suggested_order_qty": forecast.suggested_order_qty,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })

        logger.info(
            "Pipeline forecast complete: item=%s demand=%d confidence=%.1f",
            item_name,
            forecast.predicted_demand,
            float(forecast.confidence_score),
        )

        await ws_manager.broadcast_all(
            "pipeline:forecast_triggered",
            {
                "item_id": item_id_str,
                "item_name": item_name,
                "sku": sku,
                "forecast_id": str(forecast.id),
                "predicted_demand": forecast.predicted_demand,
                "confidence_score": float(forecast.confidence_score),
                "suggested_order_qty": forecast.suggested_order_qty,
            },
        )
    except Exception as exc:
        forecast_log.update({
            "status": "failed",
            "error": str(exc),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.error("Pipeline forecast failed for item=%s: %s", item_name, exc)
        return

    # ── Stage 2: Decision ─────────────────────────────────────
    decision_log = {
        "stage": "decision",
        "item_id": item_id_str,
        "item_name": item_name,
        "sku": sku,
        "status": "started",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    pipeline_logs.append(decision_log)

    decision = None
    try:
        decision_svc = DecisionService(db)
        decision = await decision_svc.evaluate_forecast(forecast.id)
        await db.commit()

        decision_log.update({
            "status": "completed",
            "decision_id": str(decision.id),
            "decision": decision.status,
            "confidence": float(decision.confidence_level or 0),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })

        logger.info(
            "Pipeline decision complete: item=%s decision=%s confidence=%.1f",
            item_name,
            decision.status,
            float(decision.confidence_level or 0),
        )
    except Exception as exc:
        decision_log.update({
            "status": "failed",
            "error": str(exc),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.error("Pipeline decision failed for item=%s: %s", item_name, exc)
        return

    # ── Stage 3: Order + Supplier Email (only when approved) ──
    if not settings.AUTONOMOUS_AUTO_ORDER_ENABLED:
        logger.info("Auto-ordering disabled — stopping pipeline at decision stage")
        return

    if decision.status != "approved":
        skip_log = {
            "stage": "order",
            "item_id": item_id_str,
            "item_name": item_name,
            "sku": sku,
            "status": "skipped",
            "reason": f"decision is '{decision.status}', not 'approved'",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        pipeline_logs.append(skip_log)
        logger.info(
            "Pipeline order skipped: item=%s decision_status=%s",
            item_name, decision.status,
        )
        return

    order_log = {
        "stage": "order",
        "item_id": item_id_str,
        "item_name": item_name,
        "sku": sku,
        "status": "started",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    pipeline_logs.append(order_log)

    try:
        order_svc = OrderService(db)
        order = await order_svc.create_order_from_decision(
            decision_id=decision.id,
            admin_email=settings.ADMIN_NOTIFICATION_EMAIL,
        )
        await db.commit()

        order_log.update({
            "status": "completed",
            "order_id": str(order.id),
            "supplier_name": order.supplier_name,
            "supplier_email": order.supplier_email,
            "email_status": order.email_status,
            "total_cost": float(order.total_cost),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })

        logger.info(
            "Pipeline order complete: item=%s order_id=%s supplier=%s email=%s",
            item_name, order.id, order.supplier_name, order.email_status,
        )
    except Exception as exc:
        order_log.update({
            "status": "failed",
            "error": str(exc),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.exception(
            "Pipeline order failed for item=%s: %s", item_name, exc
        )


async def run_monitoring_cycle() -> dict:
    """Execute a single monitoring cycle.

    Returns a summary dict with cycle results.
    """
    cycle_start = datetime.now(timezone.utc)
    pipeline_logs: list[dict] = []

    logger.info("Starting monitoring cycle at %s", cycle_start.isoformat())

    # Broadcast cycle start
    await ws_manager.broadcast_all(
        "monitoring:cycle_started",
        {"timestamp": cycle_start.isoformat()},
    )

    async with async_session_factory() as db:
        try:
            # 1. Fetch all active items
            items = await _get_active_items(db)
            if not items:
                logger.info("No active inventory items to monitor")
                return {
                    "total_checked": 0,
                    "breaches": 0,
                    "pipelines_triggered": 0,
                    "duration_ms": 0,
                }

            item_dicts = [_item_to_dict(i) for i in items]

            # 2. Run the Monitoring Agent
            agent = InventoryMonitorAgent()
            try:
                monitoring_result = await agent.analyze(item_dicts)
            finally:
                await agent.close()

            # 3. Persist monitoring decision with reasoning trace
            decision = await _persist_monitoring_decision(db, monitoring_result)

            # 4. Update last_checked_at for all scanned items
            now = datetime.now(timezone.utc)
            item_ids = [i.id for i in items]
            await db.execute(
                update(InventoryItem)
                .where(InventoryItem.id.in_(item_ids))
                .values(last_checked_at=now)
            )

            # Commit the monitoring scan + last_checked_at update immediately
            # so we release the SQLite write lock before the per-item LLM
            # pipelines start. Otherwise concurrent /pipeline/trigger handlers
            # block until busy_timeout expires and the UI shows
            # "database is locked".
            await db.commit()

            # 5. Trigger forecast pipeline for breached items
            pipelines_triggered = 0
            item_delay = float(getattr(get_settings(), "PIPELINE_ITEM_DELAY_SECONDS", 0.0))
            at_risk_list = list(monitoring_result.items_at_risk)
            for idx, at_risk in enumerate(at_risk_list):
                item_id_str = at_risk.get("item_id", "")
                item_name = at_risk.get("name", "")
                sku = at_risk.get("sku", "")

                if not item_id_str:
                    continue

                # Each item gets its own short-lived transaction. We commit
                # after every item so the SQLite write lock is released
                # between LLM calls (each item can take 30s+).
                try:
                    await _run_pipeline_for_breach(
                        db, item_id_str, item_name, sku, pipeline_logs
                    )
                    await db.commit()
                except Exception as exc:
                    await db.rollback()
                    logger.error(
                        "Per-item pipeline rolled back for item=%s: %s",
                        item_name, exc,
                    )
                pipelines_triggered += 1

                # Pause between items to keep Groq 8B model under TPM cap
                # (skip the wait after the last item).
                if item_delay > 0 and idx < len(at_risk_list) - 1:
                    logger.debug(
                        "Pipeline cooldown: sleeping %.1fs before next item",
                        item_delay,
                    )
                    await asyncio.sleep(item_delay)

            # 6. Broadcast cycle complete with pipeline logs
            await _broadcast_monitoring_cycle(
                monitoring_result, decision.id, pipeline_logs
            )

            cycle_end = datetime.now(timezone.utc)
            duration_ms = int((cycle_end - cycle_start).total_seconds() * 1000)

            summary = {
                "total_checked": monitoring_result.total_items_checked,
                "breaches": monitoring_result.breaches_detected,
                "pipelines_triggered": pipelines_triggered,
                "duration_ms": duration_ms,
                "decision_id": str(decision.id),
                "timestamp": cycle_start.isoformat(),
            }

            logger.info(
                "Monitoring cycle complete: checked=%d breaches=%d pipelines=%d duration=%dms",
                summary["total_checked"],
                summary["breaches"],
                summary["pipelines_triggered"],
                summary["duration_ms"],
            )

            return summary

        except Exception as exc:
            await db.rollback()
            logger.error("Monitoring cycle failed: %s", exc, exc_info=True)

            await ws_manager.broadcast_all(
                "monitoring:cycle_error",
                {
                    "error": str(exc),
                    "timestamp": cycle_start.isoformat(),
                },
            )

            return {
                "total_checked": 0,
                "breaches": 0,
                "pipelines_triggered": 0,
                "duration_ms": 0,
                "error": str(exc),
            }


async def _monitoring_loop(interval_seconds: int) -> None:
    """Continuous monitoring loop — runs until cancelled."""
    global _monitoring_active

    logger.info(
        "Autonomous monitoring loop started (interval=%ds)", interval_seconds
    )

    while _monitoring_active:
        try:
            await run_monitoring_cycle()
        except Exception as exc:
            logger.error("Monitoring loop iteration error: %s", exc)

        # Wait for next cycle, but check cancellation frequently
        for _ in range(interval_seconds):
            if not _monitoring_active:
                break
            await asyncio.sleep(1)

    logger.info("Autonomous monitoring loop stopped")


def start_monitoring(interval_seconds: int = DEFAULT_INTERVAL_SECONDS) -> None:
    """Start the autonomous monitoring background loop.

    Safe to call multiple times — only one loop runs at a time.
    """
    global _monitoring_task, _monitoring_active

    if _monitoring_active and _monitoring_task and not _monitoring_task.done():
        logger.warning("Monitoring loop already running")
        return

    _monitoring_active = True
    _monitoring_task = asyncio.create_task(
        _monitoring_loop(interval_seconds),
        name="inventory_monitoring_loop",
    )
    logger.info("Monitoring loop task created")


def stop_monitoring() -> None:
    """Stop the autonomous monitoring background loop."""
    global _monitoring_task, _monitoring_active

    _monitoring_active = False

    if _monitoring_task and not _monitoring_task.done():
        _monitoring_task.cancel()
        logger.info("Monitoring loop task cancelled")

    _monitoring_task = None


def is_monitoring_active() -> bool:
    """Check if the monitoring loop is currently running."""
    return _monitoring_active and _monitoring_task is not None and not _monitoring_task.done()
