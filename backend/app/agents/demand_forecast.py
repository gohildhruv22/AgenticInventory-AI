"""Intelligent Demand Forecast Agent — AutoGen AssistantAgent with Groq LLM.

Analyzes multi-signal intelligence data to produce:
- Predicted demand quantity
- Confidence score (0-100)
- Suggested order quantity
- Explainable reasoning trace
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from autogen_agentchat.agents import AssistantAgent  # noqa: F401 — kept for type re-exports
from autogen_core.models import SystemMessage, UserMessage

from app.agents.config import (
    LLMAgentError,
    create_base_agent_config,
    get_model_client,  # noqa: F401 — retained for compatibility with external callers
    invoke_with_retries,
)
from app.intelligence.aggregator import IntelligenceSignals

logger = logging.getLogger("agenticinventory.agents.demand_forecast")

SYSTEM_PROMPT = """\
You are a Demand Forecast Agent. Given an inventory item and a set of \
intelligence signals, produce a numeric demand forecast with confidence \
and a recommended order quantity.

INPUT: {"item":{name,sku,category,current_stock,reorder_threshold,
safety_stock,lead_time_days,unit_cost},
"signals":{trends_score(0-100),trend_direction,news_sentiment(-1..1),
news_headlines,weather_impact(0-100),weather_summary,holiday_proximity(days),
holiday_name,staleness_flags}}

OUTPUT (JSON only, no markdown):
{"predicted_demand":<int>,"confidence_score":<0-100>,
 "suggested_order_qty":<int>,"reasoning":"<2-3 sentences>"}

RULES:
- Rising trends + high trends_score → higher demand.
- Negative news_sentiment → possible supply risk (lower confidence).
- weather_impact > 50 → increase safety buffer.
- holiday_proximity < 14 days → +10-30% demand.
- Each stale signal → -5 confidence.
- suggested_order_qty = max(0, predicted_demand - current_stock + safety_stock).
- Output VALID JSON only.
"""


@dataclass
class ForecastResult:
    """Parsed output from the Demand Forecast Agent."""

    predicted_demand: int
    confidence_score: float
    suggested_order_qty: int
    reasoning: str


class DemandForecastAgent:
    """Wraps an AutoGen AssistantAgent configured for demand forecasting."""

    def __init__(self) -> None:
        # Lightweight 8B model — structured JSON forecast with clear rules.
        # The 8B has a much higher daily TPD quota than the 70B model, so the
        # autonomous loop can run sustainably without exhausting tokens.
        self._config = create_base_agent_config(
            name="demand_forecast_agent",
            system_message=SYSTEM_PROMPT,
            tier="lightweight",
            max_tokens=1024,
        )
        self._client = self._config["model_client"]
        logger.info("DemandForecastAgent initialized")

    async def forecast(
        self,
        item: dict,
        signals: IntelligenceSignals,
    ) -> ForecastResult:
        """Run the forecast agent and return parsed results.

        Args:
            item: Inventory item data dict.
            signals: Intelligence signals from the aggregator.

        Returns:
            ``ForecastResult`` with demand, confidence, quantity, and reasoning.
        """
        payload = json.dumps(
            {"item": item, "signals": signals.to_dict()},
            default=str,
        )

        logger.info(
            "Running demand forecast for item=%s sku=%s",
            item.get("name", "?"),
            item.get("sku", "?"),
        )

        async def _once() -> ForecastResult:
            response = await self._client.create(
                messages=[
                    SystemMessage(content=SYSTEM_PROMPT),
                    UserMessage(content=payload, source="user"),
                ],
                json_output=True,
            )
            raw = response.content
            if isinstance(raw, list):
                raw = raw[0] if raw else ""
            return self._parse_response(str(raw))

        result = await invoke_with_retries(_once, agent_name="DemandForecastAgent")
        logger.info(
            "Forecast complete: demand=%d confidence=%.1f order_qty=%d",
            result.predicted_demand,
            result.confidence_score,
            result.suggested_order_qty,
        )
        return result

    def _parse_response(self, raw: str) -> ForecastResult:
        """Parse JSON from the LLM response. Raises on any parse failure so
        the retry helper can re-prompt the model."""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            raise LLMAgentError(
                f"DemandForecastAgent returned unparseable JSON: {exc}"
            ) from exc
        return ForecastResult(
            predicted_demand=max(0, int(data.get("predicted_demand", 0))),
            confidence_score=max(0.0, min(100.0, float(data.get("confidence_score", 50.0)))),
            suggested_order_qty=max(0, int(data.get("suggested_order_qty", 0))),
            reasoning=str(data.get("reasoning", "No reasoning provided")),
        )

    async def close(self) -> None:
        """Clean up the model client connection."""
        try:
            await self._client.close()
        except Exception:
            pass
