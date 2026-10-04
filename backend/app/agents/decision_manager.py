"""Decision Manager Agent — AutoGen AssistantAgent with Groq LLM.

Evaluates demand forecasts against configurable thresholds and produces:
- Approve / flag / reject decision
- Confidence-weighted reasoning trace
- Alternative considerations
- Full explainable audit trail
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from autogen_core.models import SystemMessage, UserMessage

from app.agents.config import (
    LLMAgentError,
    create_base_agent_config,
    invoke_with_retries,
)

logger = logging.getLogger("agenticinventory.agents.decision_manager")

SYSTEM_PROMPT = """\
You are a Decision Manager Agent. Evaluate a demand forecast and decide \
approve / flag / reject. Provide reasoning and 2 alternatives.

INPUT: {"item":{name,sku,category,current_stock,reorder_threshold,
safety_stock,lead_time_days,unit_cost,supplier_email},
"forecast":{predicted_demand,confidence_score,suggested_order_qty,reasoning},
"thresholds":{auto_approve_confidence,max_order_value,min_confidence_to_flag}}

OUTPUT (JSON only, no markdown):
{"decision":"approve"|"flag"|"reject","confidence":<0-100>,
 "approved_order_qty":<int>,"estimated_cost":<float>,
 "reasoning":"<2-4 sentences>","risk_factors":["..."],
 "alternatives":[{"action":"...","pros":"...","cons":"..."}]}

RULES:
- APPROVE if forecast.confidence_score >= auto_approve_confidence AND \
estimated_cost <= max_order_value AND supplier_email is set.
- FLAG if confidence_score >= min_confidence_to_flag but below \
auto_approve_confidence, or cost > max_order_value.
- REJECT if confidence < min_confidence_to_flag or qty <= 0 or no supplier_email.
- current_stock == 0 → lower approval threshold by 15.
- approved_order_qty = suggested_order_qty on approve, else 0.
- Always include >=2 alternatives.
- Output VALID JSON only.
"""

# Configurable decision thresholds
DEFAULT_THRESHOLDS = {
    "auto_approve_confidence": 70.0,
    "max_order_value": 10000.0,
    "min_confidence_to_flag": 40.0,
}


@dataclass
class DecisionResult:
    """Parsed output from the Decision Manager Agent."""

    decision: str  # "approve" | "flag" | "reject"
    confidence: float
    approved_order_qty: int
    estimated_cost: float
    reasoning: str
    risk_factors: list[str] = field(default_factory=list)
    alternatives: list[dict] = field(default_factory=list)


class DecisionManagerAgent:
    """Wraps an AutoGen AssistantAgent configured for order decision-making."""

    def __init__(self, thresholds: dict | None = None) -> None:
        # Lightweight 8B model — the decision is rule-based JSON output.
        # Using 8B keeps the autonomous loop within Groq's daily TPD quota.
        self._config = create_base_agent_config(
            name="decision_manager_agent",
            system_message=SYSTEM_PROMPT,
            tier="lightweight",
            max_tokens=1024,
        )
        self._client = self._config["model_client"]
        self._thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
        logger.info(
            "DecisionManagerAgent initialized with thresholds=%s",
            self._thresholds,
        )

    async def evaluate(
        self,
        item: dict,
        forecast: dict,
        thresholds: dict | None = None,
    ) -> DecisionResult:
        """Evaluate a forecast and produce an approve/flag/reject decision.

        Args:
            item: Inventory item data dict.
            forecast: Forecast result dict with predicted_demand, confidence_score, etc.
            thresholds: Optional override for decision thresholds.

        Returns:
            ``DecisionResult`` with decision, reasoning, and alternatives.
        """
        effective_thresholds = {**self._thresholds, **(thresholds or {})}

        payload = json.dumps(
            {
                "item": item,
                "forecast": forecast,
                "thresholds": effective_thresholds,
            },
            default=str,
        )

        logger.info(
            "Evaluating decision for item=%s sku=%s forecast_confidence=%.1f",
            item.get("name", "?"),
            item.get("sku", "?"),
            forecast.get("confidence_score", 0),
        )

        async def _once() -> DecisionResult:
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

        result = await invoke_with_retries(_once, agent_name="DecisionManagerAgent")
        logger.info(
            "Decision complete: decision=%s confidence=%.1f order_qty=%d cost=%.2f",
            result.decision,
            result.confidence,
            result.approved_order_qty,
            result.estimated_cost,
        )
        return result

    def _parse_response(self, raw: str) -> DecisionResult:
        """Parse JSON from the LLM response. Raises on parse failure."""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            raise LLMAgentError(
                f"DecisionManagerAgent returned unparseable JSON: {exc}"
            ) from exc

        decision = str(data.get("decision", "reject")).lower()
        if decision not in ("approve", "flag", "reject"):
            decision = "flag"

        return DecisionResult(
            decision=decision,
            confidence=max(0.0, min(100.0, float(data.get("confidence", 50.0)))),
            approved_order_qty=max(0, int(data.get("approved_order_qty", 0))),
            estimated_cost=max(0.0, float(data.get("estimated_cost", 0.0))),
            reasoning=str(data.get("reasoning", "No reasoning provided")),
            risk_factors=list(data.get("risk_factors", [])),
            alternatives=list(data.get("alternatives", [])),
        )

    async def close(self) -> None:
        """Clean up model client resources."""
        if hasattr(self._client, "close"):
            await self._client.close()
        elif hasattr(self._client, "aclose"):
            await self._client.aclose()
