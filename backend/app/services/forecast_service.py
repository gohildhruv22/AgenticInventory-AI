"""Forecast service — orchestrates intelligence gathering, agent invocation, and persistence."""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.demand_forecast import DemandForecastAgent, ForecastResult
from app.intelligence.aggregator import IntelligenceAggregator, IntelligenceSignals, get_redis_client
from app.models.forecast import Forecast
from app.models.inventory_item import InventoryItem
from app.websocket.manager import ws_manager

logger = logging.getLogger("agenticinventory.services.forecast")


class ForecastService:
    """Invokes the intelligence aggregator and demand forecast agent,
    then persists the Forecast record with all signal fields."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_forecast(self, item_id: UUID) -> Forecast:
        """Generate a full demand forecast for an inventory item.

        1. Load the inventory item from DB.
        2. Gather intelligence signals (all 4 APIs concurrently).
        3. Invoke the Demand Forecast Agent via Groq LLM.
        4. Persist the Forecast record.
        5. Broadcast via WebSocket.

        Args:
            item_id: UUID of the inventory item.

        Returns:
            The persisted ``Forecast`` ORM instance.

        Raises:
            ValueError: If the item does not exist.
        """
        # 1. Load item
        result = await self.db.execute(
            select(InventoryItem).where(InventoryItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            raise ValueError(f"Inventory item {item_id} not found")

        item_data = {
            "name": item.name,
            "sku": item.sku,
            "category": item.category,
            "current_stock": item.current_stock,
            "reorder_threshold": item.reorder_threshold,
            "safety_stock": item.safety_stock,
            "lead_time_days": item.lead_time_days,
            "unit_cost": float(item.unit_cost),
        }

        logger.info("Generating forecast for item=%s sku=%s", item.name, item.sku)

        # 2. Gather intelligence signals
        redis_client = await get_redis_client()
        try:
            aggregator = IntelligenceAggregator(redis_client)
            signals = await aggregator.gather_signals(
                keyword=item.name,
                category=item.category,
            )
        finally:
            if redis_client:
                await redis_client.aclose()

        # 3. Invoke Demand Forecast Agent
        agent = DemandForecastAgent()
        try:
            forecast_result = await agent.forecast(item_data, signals)
        finally:
            await agent.close()

        # 4. Persist Forecast record
        forecast = self._build_forecast(item_id, forecast_result, signals)
        self.db.add(forecast)
        await self.db.flush()

        logger.info(
            "Forecast persisted: id=%s demand=%d confidence=%.1f order_qty=%d",
            forecast.id,
            forecast.predicted_demand,
            forecast.confidence_score,
            forecast.suggested_order_qty,
        )

        # 5. Broadcast
        await ws_manager.broadcast_all(
            "forecast:created",
            {
                "forecast_id": str(forecast.id),
                "item_id": str(item_id),
                "item_name": item.name,
                "predicted_demand": forecast.predicted_demand,
                "confidence_score": float(forecast.confidence_score),
                "suggested_order_qty": forecast.suggested_order_qty,
            },
        )

        return forecast

    async def get_forecasts_for_item(
        self, item_id: UUID, limit: int = 10
    ) -> list[Forecast]:
        """Retrieve recent forecasts for an inventory item."""
        result = await self.db.execute(
            select(Forecast)
            .where(Forecast.inventory_item_id == item_id)
            .order_by(Forecast.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_latest_forecast(self, item_id: UUID) -> Forecast | None:
        """Retrieve the most recent forecast for an item."""
        result = await self.db.execute(
            select(Forecast)
            .where(Forecast.inventory_item_id == item_id)
            .order_by(Forecast.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _build_forecast(
        self,
        item_id: UUID,
        result: ForecastResult,
        signals: IntelligenceSignals,
    ) -> Forecast:
        """Build a Forecast ORM object from agent result and raw signals."""
        return Forecast(
            inventory_item_id=item_id,
            predicted_demand=result.predicted_demand,
            confidence_score=Decimal(str(round(result.confidence_score, 2))),
            suggested_order_qty=result.suggested_order_qty,
            reasoning=result.reasoning,
            trends_score=Decimal(str(round(signals.trends_score, 2))),
            trend_direction=signals.trend_direction,
            news_sentiment=Decimal(str(round(signals.news_sentiment, 2))),
            weather_impact=Decimal(str(round(signals.weather_impact, 2))),
            holiday_proximity=signals.holiday_proximity,
            holiday_name=signals.holiday_name,
            staleness_flags=signals.staleness_flags,
            raw_signals=signals.to_dict(),
        )
