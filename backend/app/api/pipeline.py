"""Pipeline API — trigger and monitor the agent pipeline for demo purposes."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.inventory_item import InventoryItem
from app.models.user import User
from app.websocket.manager import ws_manager

router = APIRouter(prefix="/pipeline", tags=["pipeline"])
logger = logging.getLogger("agenticinventory.api.pipeline")

# In-memory pipeline state (demo-friendly, no persistence needed)
_pipeline_runs: dict[str, dict] = {}

PIPELINE_AGENTS = [
    "inventory_monitor",
    "demand_forecast",
    "decision_manager",
    "supplier_email",
    "delivery_tracker",
]


class TriggerRequest(BaseModel):
    inventory_item_id: str | None = None


@router.post("/trigger", status_code=202)
async def trigger_pipeline(
    body: TriggerRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Manually trigger the agent pipeline for demo visualization.

    If no item_id is provided, picks a random active inventory item.
    The pipeline runs in the background and emits WebSocket events.
    """
    pipeline_id = str(uuid.uuid4())

    # Resolve item
    item_name = "Sample Item"
    item_id = body.inventory_item_id

    if item_id:
        result = await db.execute(
            select(InventoryItem).where(InventoryItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item:
            item_name = item.name
    else:
        result = await db.execute(
            select(InventoryItem)
            .where(InventoryItem.is_active.is_(True))
            .order_by(InventoryItem.current_stock.asc())
            .limit(1)
        )
        item = result.scalar_one_or_none()
        if item:
            item_id = str(item.id)
            item_name = item.name

    run = {
        "pipeline_id": pipeline_id,
        "item_id": item_id,
        "item_name": item_name,
        "status": "running",
        "current_agent": PIPELINE_AGENTS[0],
        "stages": [
            {"agent": a, "status": "pending", "summary": None}
            for a in PIPELINE_AGENTS
        ],
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    _pipeline_runs[pipeline_id] = run

    background_tasks.add_task(_run_real_pipeline, pipeline_id, item_id, item_name)

    return {"message": "Pipeline triggered", "pipeline_id": pipeline_id}


@router.get("/{pipeline_id}/status")
async def get_pipeline_status(
    pipeline_id: str,
    _user: User = Depends(get_current_user),
):
    """Get current pipeline execution status."""
    run = _pipeline_runs.get(pipeline_id)
    if not run:
        return {"pipeline_id": pipeline_id, "status": "not_found", "stages": []}
    return run


@router.get("/history")
async def pipeline_history(
    limit: int = Query(10, ge=1, le=50),
    _user: User = Depends(get_current_user),
):
    """Get recent pipeline runs."""
    runs = sorted(
        _pipeline_runs.values(),
        key=lambda r: r["started_at"],
        reverse=True,
    )[:limit]
    return {"runs": runs}


# Agent simulation messages (demo-friendly)
_AGENT_MESSAGES = {
    "inventory_monitor": [
        "Scanning inventory levels...",
        "Checking reorder thresholds...",
        "Low stock detected — triggering forecast",
    ],
    "demand_forecast": [
        "Querying Google Trends API...",
        "Analyzing seasonal patterns...",
        "Forecasting demand with 82% confidence",
    ],
    "decision_manager": [
        "Evaluating forecast against thresholds...",
        "Analyzing risk factors...",
        "Decision: APPROVE reorder — confidence exceeds threshold",
    ],
    "supplier_email": [
        "Composing purchase order email...",
        "Resolving supplier from category...",
        "Email sent to supplier successfully",
    ],
    "delivery_tracker": [
        "Initiating delivery tracking...",
        "Configuring simulation parameters...",
        "Delivery tracking active — ETA 3-5 days",
    ],
}

_AGENT_SUMMARIES = {
    "inventory_monitor": "Low stock detected: {qty} units remaining (threshold: {threshold})",
    "demand_forecast": "Confidence: 82.5%, Suggested order: 55 units",
    "decision_manager": "APPROVED — confidence 82.5% exceeds 75% threshold",
    "supplier_email": "Purchase order email sent to supplier",
    "delivery_tracker": "Delivery tracking initiated — estimated 3-5 days",
}


async def _simulate_pipeline(
    pipeline_id: str, item_id: str | None, item_name: str
) -> None:
    """Simulate pipeline execution with realistic timing and WebSocket events."""
    run = _pipeline_runs.get(pipeline_id)
    if not run:
        return

    for idx, agent in enumerate(PIPELINE_AGENTS):
        run["current_agent"] = agent
        run["stages"][idx]["status"] = "processing"
        run["stages"][idx]["started_at"] = datetime.now(timezone.utc).isoformat()

        # Broadcast agent status change
        await ws_manager.broadcast_all(
            "agent:status",
            {
                "agent_type": agent,
                "status": "processing",
                "pipeline_id": pipeline_id,
                "item_id": item_id,
                "message": f"Processing {item_name}...",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Simulate reasoning steps
        messages = _AGENT_MESSAGES.get(agent, ["Processing..."])
        for step_idx, msg in enumerate(messages):
            await asyncio.sleep(0.8)  # Realistic delay between steps

            await ws_manager.broadcast_all(
                "agent:reasoning",
                {
                    "pipeline_id": pipeline_id,
                    "agent_type": agent,
                    "step": f"step_{step_idx + 1}",
                    "message": msg,
                    "progress": (step_idx + 1) / len(messages),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

        # Mark agent as completed
        duration_ms = int(len(messages) * 800)
        summary = _AGENT_SUMMARIES.get(agent, "Completed").format(
            qty=5, threshold=20
        )
        run["stages"][idx]["status"] = "completed"
        run["stages"][idx]["duration_ms"] = duration_ms
        run["stages"][idx]["summary"] = summary

        await ws_manager.broadcast_all(
            "agent:status",
            {
                "agent_type": agent,
                "status": "completed",
                "pipeline_id": pipeline_id,
                "item_id": item_id,
                "message": summary,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Broadcast pipeline progress
        await ws_manager.broadcast_all(
            "pipeline:progress",
            {
                "pipeline_id": pipeline_id,
                "item_id": item_id,
                "item_name": item_name,
                "stages": run["stages"],
                "current_agent": PIPELINE_AGENTS[idx + 1] if idx + 1 < len(PIPELINE_AGENTS) else None,
                "started_at": run["started_at"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    # Mark pipeline as completed
    run["status"] = "completed"
    run["current_agent"] = None
    run["completed_at"] = datetime.now(timezone.utc).isoformat()

    logger.info("Pipeline %s completed for item %s", pipeline_id, item_name)


async def _emit_stage(
    pipeline_id: str,
    item_id: str | None,
    item_name: str,
    idx: int,
    agent: str,
    status: str,
    message: str,
    run: dict,
    summary: str | None = None,
) -> None:
    """Update in-memory run state and broadcast a single stage event."""
    run["stages"][idx]["status"] = status
    if status == "processing":
        run["stages"][idx]["started_at"] = datetime.now(timezone.utc).isoformat()
        run["current_agent"] = agent
    elif status in {"completed", "failed", "skipped"}:
        run["stages"][idx]["completed_at"] = datetime.now(timezone.utc).isoformat()
        if summary:
            run["stages"][idx]["summary"] = summary

    await ws_manager.broadcast_all(
        "agent:status",
        {
            "agent_type": agent,
            "status": status,
            "pipeline_id": pipeline_id,
            "item_id": item_id,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    await ws_manager.broadcast_all(
        "pipeline:progress",
        {
            "pipeline_id": pipeline_id,
            "item_id": item_id,
            "item_name": item_name,
            "stages": run["stages"],
            "current_agent": run.get("current_agent"),
            "started_at": run["started_at"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


async def _run_real_pipeline(
    pipeline_id: str, item_id: str | None, item_name: str
) -> None:
    """Run the actual LLM-driven agent pipeline end-to-end for one item.

    Emits the same WebSocket events the UI already subscribes to so the
    Agents page lights up live as each real agent finishes.
    """
    from uuid import UUID
    from app.config import get_settings
    from app.database import async_session_factory
    from app.services.forecast_service import ForecastService
    from app.services.decision_service import DecisionService
    from app.services.order_service import OrderService

    run = _pipeline_runs.get(pipeline_id)
    if not run:
        return

    settings_obj = get_settings()

    if not item_id:
        run["status"] = "failed"
        run["error"] = "No inventory item available to run the pipeline against."
        return

    item_uuid = UUID(item_id)

    async with async_session_factory() as db:
        # Stage 0: inventory_monitor (already implicit — we know this item breached)
        await _emit_stage(
            pipeline_id, item_id, item_name, 0, "inventory_monitor",
            "processing", f"Scanning stock levels for {item_name}…", run,
        )
        await _emit_stage(
            pipeline_id, item_id, item_name, 0, "inventory_monitor",
            "completed", f"{item_name} flagged for replenishment.", run,
            summary="Threshold breach detected — triggering downstream agents.",
        )

        # Stage 1: demand_forecast (real LLM call)
        await _emit_stage(
            pipeline_id, item_id, item_name, 1, "demand_forecast",
            "processing", "Aggregating market, news, weather, holiday signals…", run,
        )
        try:
            forecast = await ForecastService(db).generate_forecast(item_uuid)
            await db.commit()
            forecast_summary = (
                f"Predicted demand {forecast.predicted_demand} units "
                f"(confidence {float(forecast.confidence_score):.1f}%) — "
                f"suggested order qty {forecast.suggested_order_qty}."
            )
            await _emit_stage(
                pipeline_id, item_id, item_name, 1, "demand_forecast",
                "completed", forecast_summary, run, summary=forecast_summary,
            )
        except Exception as exc:
            await db.rollback()
            logger.exception("Pipeline forecast stage failed: %s", exc)
            await _emit_stage(
                pipeline_id, item_id, item_name, 1, "demand_forecast",
                "failed", f"Forecast failed: {exc}", run,
                summary=f"Failed: {exc}",
            )
            run["status"] = "failed"
            return

        # Stage 2: decision_manager (real LLM call)
        await _emit_stage(
            pipeline_id, item_id, item_name, 2, "decision_manager",
            "processing", "Evaluating forecast against thresholds & risk…", run,
        )
        try:
            decision = await DecisionService(db).evaluate_forecast(forecast.id)
            await db.commit()
            decision_summary = (
                f"Decision: {decision.status.upper()} "
                f"(confidence {float(decision.confidence_level or 0):.1f}%)."
            )
            await _emit_stage(
                pipeline_id, item_id, item_name, 2, "decision_manager",
                "completed", decision_summary, run, summary=decision_summary,
            )
        except Exception as exc:
            await db.rollback()
            logger.exception("Pipeline decision stage failed: %s", exc)
            await _emit_stage(
                pipeline_id, item_id, item_name, 2, "decision_manager",
                "failed", f"Decision failed: {exc}", run,
                summary=f"Failed: {exc}",
            )
            run["status"] = "failed"
            return

        # Stage 3: supplier_email (only if approved)
        if decision.status != "approved":
            skip_msg = (
                f"Skipped — decision status is '{decision.status}', "
                "supplier email only sent for approved orders."
            )
            await _emit_stage(
                pipeline_id, item_id, item_name, 3, "supplier_email",
                "skipped", skip_msg, run, summary=skip_msg,
            )
            await _emit_stage(
                pipeline_id, item_id, item_name, 4, "delivery_tracker",
                "skipped", "No order placed — delivery tracking skipped.", run,
                summary="Skipped (no order)",
            )
            run["status"] = "completed"
            run["completed_at"] = datetime.now(timezone.utc).isoformat()
            return

        await _emit_stage(
            pipeline_id, item_id, item_name, 3, "supplier_email",
            "processing", "Composing purchase order email…", run,
        )
        try:
            order = await OrderService(db).create_order_from_decision(
                decision_id=decision.id,
                admin_email=settings_obj.ADMIN_NOTIFICATION_EMAIL,
            )
            await db.commit()
            order_summary = (
                f"Order {str(order.id)[:8]} → {order.supplier_name} "
                f"({order.supplier_email}) — email {order.email_status}, "
                f"total ${float(order.total_cost):,.2f}."
            )
            await _emit_stage(
                pipeline_id, item_id, item_name, 3, "supplier_email",
                "completed", order_summary, run, summary=order_summary,
            )
        except Exception as exc:
            await db.rollback()
            logger.exception("Pipeline order stage failed: %s", exc)
            await _emit_stage(
                pipeline_id, item_id, item_name, 3, "supplier_email",
                "failed", f"Order/email failed: {exc}", run,
                summary=f"Failed: {exc}",
            )
            run["status"] = "failed"
            return

        # Stage 4: delivery_tracker (lightweight — real DB-backed status)
        await _emit_stage(
            pipeline_id, item_id, item_name, 4, "delivery_tracker",
            "processing", "Setting up delivery tracking…", run,
        )
        delivery_summary = (
            f"Tracking initialized for order {str(order.id)[:8]} — "
            f"awaiting shipment confirmation from {order.supplier_name}."
        )
        await _emit_stage(
            pipeline_id, item_id, item_name, 4, "delivery_tracker",
            "completed", delivery_summary, run, summary=delivery_summary,
        )

    run["status"] = "completed"
    run["current_agent"] = None
    run["completed_at"] = datetime.now(timezone.utc).isoformat()
    logger.info("Real pipeline %s completed for item %s", pipeline_id, item_name)
