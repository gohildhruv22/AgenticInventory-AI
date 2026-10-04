"""Decision service — evaluates forecasts via Decision Manager Agent and persists decisions."""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.decision_manager import DecisionManagerAgent, DecisionResult
from app.models.action_log import ActionLog
from app.models.agent_decision import AgentDecision
from app.models.forecast import Forecast
from app.models.inventory_item import InventoryItem
from app.websocket.manager import ws_manager

logger = logging.getLogger("agenticinventory.services.decision")


class DecisionService:
    """Invokes the Decision Manager Agent and persists AgentDecision records
    with full reasoning traces and alternative considerations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def evaluate_forecast(
        self,
        forecast_id: UUID,
        thresholds: dict | None = None,
    ) -> AgentDecision:
        """Evaluate a forecast and create a decision record.

        1. Load the forecast and its inventory item.
        2. Invoke the Decision Manager Agent via Groq LLM.
        3. Persist the AgentDecision record with reasoning trace.
        4. Broadcast the decision via WebSocket.

        Args:
            forecast_id: UUID of the forecast to evaluate.
            thresholds: Optional override for decision thresholds.

        Returns:
            The persisted ``AgentDecision`` ORM instance.

        Raises:
            ValueError: If the forecast or item does not exist.
        """
        # 1. Load forecast
        result = await self.db.execute(
            select(Forecast).where(Forecast.id == forecast_id)
        )
        forecast = result.scalar_one_or_none()
        if not forecast:
            raise ValueError(f"Forecast {forecast_id} not found")

        # Load inventory item
        result = await self.db.execute(
            select(InventoryItem).where(
                InventoryItem.id == forecast.inventory_item_id
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise ValueError(
                f"Inventory item {forecast.inventory_item_id} not found"
            )

        item_data = {
            "name": item.name,
            "sku": item.sku,
            "category": item.category,
            "current_stock": item.current_stock,
            "reorder_threshold": item.reorder_threshold,
            "safety_stock": item.safety_stock,
            "lead_time_days": item.lead_time_days,
            "unit_cost": float(item.unit_cost),
            "supplier_email": item.supplier_email or "",
        }

        forecast_data = {
            "predicted_demand": forecast.predicted_demand,
            "confidence_score": float(forecast.confidence_score),
            "suggested_order_qty": forecast.suggested_order_qty,
            "reasoning": forecast.reasoning,
        }

        logger.info(
            "Evaluating forecast=%s for item=%s sku=%s",
            forecast_id,
            item.name,
            item.sku,
        )

        # 2. Invoke Decision Manager Agent
        agent = DecisionManagerAgent(thresholds=thresholds)
        try:
            decision_result = await agent.evaluate(
                item_data, forecast_data, thresholds
            )
        finally:
            await agent.close()

        # 3. Persist AgentDecision record
        decision = self._build_decision(
            item.id, forecast_id, decision_result, item_data, forecast_data
        )
        self.db.add(decision)
        await self.db.flush()

        logger.info(
            "Decision persisted: id=%s decision=%s confidence=%.1f order_qty=%d",
            decision.id,
            decision_result.decision,
            decision_result.confidence,
            decision_result.approved_order_qty,
        )

        # Record action log for rollback support
        action_log = ActionLog(
            agent_type="decision_manager",
            action_type="evaluate_forecast",
            entity_type="inventory_item",
            entity_id=item.id,
            before_state={
                "current_stock": item.current_stock,
                "reorder_threshold": item.reorder_threshold,
            },
            after_state={
                "decision_id": str(decision.id),
                "decision": decision_result.decision,
                "approved_order_qty": decision_result.approved_order_qty,
            },
            compensating_action={
                "type": "restore_inventory",
                "params": {
                    "item_id": str(item.id),
                    "restore_stock": item.current_stock,
                    "order_qty": decision_result.approved_order_qty,
                },
                "restore_entity": True,
            },
            decision_id=decision.id,
            status="executed",
            reasoning_trace={
                "reason": decision_result.reasoning,
                "confidence": decision_result.confidence,
            },
        )
        self.db.add(action_log)
        await self.db.flush()

        # 4. Broadcast decision via WebSocket
        await ws_manager.broadcast_all(
            "decision:created",
            {
                "decision_id": str(decision.id),
                "item_id": str(item.id),
                "item_name": item.name,
                "sku": item.sku,
                "forecast_id": str(forecast_id),
                "decision": decision_result.decision,
                "confidence": decision_result.confidence,
                "approved_order_qty": decision_result.approved_order_qty,
                "estimated_cost": decision_result.estimated_cost,
                "reasoning": decision_result.reasoning,
                "risk_factors": decision_result.risk_factors,
            },
        )

        return decision

    async def evaluate_item(
        self,
        item_id: UUID,
        thresholds: dict | None = None,
    ) -> AgentDecision | None:
        """Evaluate the latest forecast for an inventory item.

        Convenience method that finds the most recent forecast and evaluates it.

        Args:
            item_id: UUID of the inventory item.
            thresholds: Optional override for decision thresholds.

        Returns:
            The persisted ``AgentDecision``, or None if no forecast exists.
        """
        result = await self.db.execute(
            select(Forecast)
            .where(Forecast.inventory_item_id == item_id)
            .order_by(Forecast.created_at.desc())
            .limit(1)
        )
        forecast = result.scalar_one_or_none()
        if not forecast:
            logger.warning("No forecast found for item %s — skipping decision", item_id)
            return None

        return await self.evaluate_forecast(forecast.id, thresholds)

    async def get_decisions_for_item(
        self, item_id: UUID, limit: int = 10
    ) -> list[AgentDecision]:
        """Retrieve recent decisions for an inventory item."""
        result = await self.db.execute(
            select(AgentDecision)
            .where(AgentDecision.inventory_item_id == item_id)
            .order_by(AgentDecision.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_latest_decision(self, item_id: UUID) -> AgentDecision | None:
        """Retrieve the most recent decision for an item."""
        result = await self.db.execute(
            select(AgentDecision)
            .where(AgentDecision.inventory_item_id == item_id)
            .order_by(AgentDecision.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_pending_decisions(self) -> list[AgentDecision]:
        """Retrieve all flagged decisions waiting for human review."""
        result = await self.db.execute(
            select(AgentDecision)
            .where(AgentDecision.status == "flagged")
            .order_by(AgentDecision.created_at.desc())
        )
        return list(result.scalars().all())

    async def approve_flagged(self, decision_id: UUID) -> AgentDecision:
        """Manually approve a previously flagged decision."""
        result = await self.db.execute(
            select(AgentDecision).where(AgentDecision.id == decision_id)
        )
        decision = result.scalar_one_or_none()
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")

        if decision.status != "flagged":
            raise ValueError(
                f"Decision {decision_id} is '{decision.status}', not 'flagged'"
            )

        decision.status = "approved"
        # Restore the suggested qty from the reasoning trace
        suggested_qty = decision.reasoning_trace.get("suggested_order_qty", 0)
        decision.metadata_ = {
            **decision.metadata_,
            "manually_approved": True,
            "approved_order_qty": suggested_qty,
        }
        await self.db.flush()

        await ws_manager.broadcast_all(
            "decision:approved",
            {
                "decision_id": str(decision.id),
                "item_id": str(decision.inventory_item_id),
                "status": "approved",
            },
        )

        return decision

    def _build_decision(
        self,
        item_id: UUID,
        forecast_id: UUID,
        result: DecisionResult,
        item_data: dict,
        forecast_data: dict,
    ) -> AgentDecision:
        """Build an AgentDecision ORM object from agent result."""
        # Map decision string to status
        status_map = {
            "approve": "approved",
            "flag": "flagged",
            "reject": "rejected",
        }

        return AgentDecision(
            agent_type="decision_manager",
            action_type="order_evaluation",
            inventory_item_id=item_id,
            forecast_id=forecast_id,
            reasoning_trace={
                "decision": result.decision,
                "reasoning": result.reasoning,
                "risk_factors": result.risk_factors,
                "forecast_confidence": forecast_data.get("confidence_score", 0),
                "predicted_demand": forecast_data.get("predicted_demand", 0),
                "suggested_order_qty": forecast_data.get("suggested_order_qty", 0),
                "approved_order_qty": result.approved_order_qty,
                "estimated_cost": result.estimated_cost,
                "item_context": {
                    "name": item_data.get("name"),
                    "sku": item_data.get("sku"),
                    "current_stock": item_data.get("current_stock"),
                    "unit_cost": item_data.get("unit_cost"),
                },
            },
            confidence_level=Decimal(str(round(result.confidence, 2))),
            alternatives_considered=result.alternatives,
            status=status_map.get(result.decision, "executed"),
            metadata_={
                "approved_order_qty": result.approved_order_qty,
                "estimated_cost": result.estimated_cost,
            },
        )
