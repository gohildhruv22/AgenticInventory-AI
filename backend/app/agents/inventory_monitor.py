"""Inventory Monitoring Agent — AutoGen AssistantAgent with Groq LLM.

Continuously monitors stock levels, detects threshold breaches,
and produces structured reasoning traces explaining its analysis.
Triggers the forecasting pipeline automatically when breaches are found.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from autogen_core.models import SystemMessage, UserMessage

from app.agents.config import (
    LLMAgentError,
    create_base_agent_config,
    invoke_with_retries,
)

logger = logging.getLogger("agenticinventory.agents.inventory_monitor")

# Compact prompt — the LLM only sees pre-filtered at-risk items, so we don't
# need to teach it how to detect breaches. Its job is severity + recommendation.
SYSTEM_PROMPT = """\
You are an Inventory Monitoring Agent. You receive a list of items that have \
ALREADY been flagged as at risk (low or out of stock). Your job is to rank \
them by urgency and explain why.

INPUT JSON: {"items": [{"id","name","sku","current_stock","reorder_threshold",\
"safety_stock","lead_time_days","unit_cost","status"}]}

OUTPUT (JSON only, no markdown):
{
  "analysis_summary": "<1 sentence>",
  "items_at_risk": [
    {"item_id","name","sku","current_stock","reorder_threshold",
     "severity":"critical"|"warning","stock_deficit":<int>,
     "urgency_score":<0-100>,"recommendation":"<short>"}
  ],
  "reasoning": "<2-3 sentences>"
}

RULES:
- current_stock == 0 → "critical", urgency 90-100.
- current_stock <= reorder_threshold → "warning", urgency 50-89.
- stock_deficit = max(0, reorder_threshold - current_stock + safety_stock).
- Boost urgency for high unit_cost or long lead_time_days.
- Sort items_at_risk by urgency_score DESC. Include every input item.
- Output VALID JSON only.
"""


def _is_at_risk(item: dict) -> bool:
    """Deterministic pre-filter: only items at/below threshold need LLM judgment."""
    try:
        return int(item.get("current_stock", 0)) <= int(item.get("reorder_threshold", 0))
    except (TypeError, ValueError):
        return False


@dataclass
class MonitoringResult:
    """Parsed output from the Inventory Monitoring Agent."""

    analysis_summary: str
    total_items_checked: int
    breaches_detected: int
    items_at_risk: list[dict] = field(default_factory=list)
    reasoning: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class InventoryMonitorAgent:
    """Wraps an AutoGen AssistantAgent configured for inventory monitoring."""

    def __init__(self) -> None:
        # Use the lightweight 8B model — monitoring is a simple ranking task,
        # and the 8B Instant has a much higher TPD quota than the 70B model.
        self._config = create_base_agent_config(
            name="inventory_monitor_agent",
            system_message=SYSTEM_PROMPT,
            tier="lightweight",
            max_tokens=1024,
        )
        self._client = self._config["model_client"]
        logger.info("InventoryMonitorAgent initialized (lightweight tier)")

    async def analyze(self, items: list[dict]) -> MonitoringResult:
        """Run the monitoring agent to analyze inventory items.

        Args:
            items: List of inventory item dicts with stock data.

        Returns:
            ``MonitoringResult`` with breach analysis and reasoning.
        """
        if not items:
            return MonitoringResult(
                analysis_summary="No items to monitor.",
                total_items_checked=0,
                breaches_detected=0,
                reasoning="Empty inventory — nothing to analyze.",
            )

        total = len(items)
        # Pre-filter: only items at/below reorder threshold need LLM reasoning.
        # Healthy items consume tokens without contributing to decisions.
        at_risk_input = [i for i in items if _is_at_risk(i)]

        if not at_risk_input:
            logger.info(
                "Monitoring: %d items checked, none at risk — skipping LLM call",
                total,
            )
            return MonitoringResult(
                analysis_summary=f"All {total} items above reorder threshold.",
                total_items_checked=total,
                breaches_detected=0,
                reasoning="Pre-filter found no items requiring agent attention.",
            )

        # Trim each item to only the fields the LLM needs (saves tokens)
        compact_items = [
            {
                "id": i.get("id"),
                "name": i.get("name"),
                "sku": i.get("sku"),
                "current_stock": i.get("current_stock"),
                "reorder_threshold": i.get("reorder_threshold"),
                "safety_stock": i.get("safety_stock"),
                "lead_time_days": i.get("lead_time_days"),
                "unit_cost": i.get("unit_cost"),
                "status": i.get("status"),
            }
            for i in at_risk_input
        ]

        payload = json.dumps({"items": compact_items}, default=str)

        logger.info(
            "Inventory monitor: %d total, %d at-risk → LLM",
            total,
            len(at_risk_input),
        )

        async def _once() -> MonitoringResult:
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
            return self._parse_response(str(raw), total, len(at_risk_input))

        result = await invoke_with_retries(_once, agent_name="InventoryMonitorAgent")
        logger.info(
            "Monitoring complete: checked=%d breaches=%d",
            result.total_items_checked,
            result.breaches_detected,
        )
        return result

    def _parse_response(
        self, raw: str, total_checked: int, breach_count: int
    ) -> MonitoringResult:
        """Parse JSON from the LLM response. Raises on parse failure."""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            raise LLMAgentError(
                f"InventoryMonitorAgent returned unparseable JSON: {exc}"
            ) from exc
        # We supply the totals from the pre-filter — LLM ranks/reasons only.
        return MonitoringResult(
            analysis_summary=str(data.get("analysis_summary", "")),
            total_items_checked=total_checked,
            breaches_detected=breach_count,
            items_at_risk=list(data.get("items_at_risk", [])),
            reasoning=str(data.get("reasoning", "")),
        )

    async def close(self) -> None:
        """Clean up model client resources."""
        if hasattr(self._client, "close"):
            await self._client.close()
        elif hasattr(self._client, "aclose"):
            await self._client.aclose()

