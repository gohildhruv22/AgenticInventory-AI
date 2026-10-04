"""Reporting & KPI Agent — generates natural-language KPI summaries using AutoGen + Groq."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from app.agents.config import LLMAgentError, get_model_client, invoke_with_retries

logger = logging.getLogger("agenticinventory.agents.reporting_kpi")

SYSTEM_PROMPT = """You are the Reporting & KPI Agent for AgenticInventory AI.

Your job is to analyze a single day of inventory and procurement operations
and produce an executive brief that an operations manager can act on in under
60 seconds.

INPUT: A JSON object with:
  - Headline counts: order_volume, total_spend, decisions_*, deliveries_*.
  - KPIs: forecast_accuracy, avg_confidence_score, automation_rate, otif_rate,
    stockout_rate, rollback_rate, email_delivery_rate, perfect_order_rate,
    at_risk_count, active_skus, avg_order_value.
  - Lists: spend_by_category, top_suppliers, low_stock_items (name, sku,
    current_stock, threshold), flagged_items (item_name, confidence,
    estimated_cost), recent_deliveries (item, stage, supplier).
  - Context: weekly_avg_orders, weekly_avg_spend (7-day baseline).

OUTPUT — VALID JSON ONLY (no markdown fences, no commentary):
{
  "summary":         "<2-3 plain-English sentences referencing specific numbers from the input>",
  "highlights":      ["<3-5 bullets, each citing a specific item name, supplier, or number>"],
  "trends":          ["<1-3 observations comparing today vs the weekly baseline>"],
  "risk_alerts":     ["<0-3 concerns; reference the SKU/item by name>"],
  "recommendations": ["<1-3 imperative actions starting with a verb — Reorder, Review, Investigate, Email, etc.>"],
  "score":           <int 0-100>
}

GROUNDING RULES (critical):
1. Every number you write MUST appear verbatim in the input. Do not fabricate
   percentages, dollar amounts, dates, or SKU counts.
2. Reference at least 2 specific item names or supplier names by name in
   highlights or recommendations. Never write generic phrases like
   "review forecasting model" or "monitor key metrics".
3. If stockout_rate > 0 or at_risk_count > 0, the FIRST recommendation must
   reference the most critical low_stock_item by name.
4. If any flagged_items exist, raise at least one risk_alert that names the
   item and its confidence.
5. If forecast_accuracy < 70 or avg_confidence_score < 60, add a risk_alert.
6. If order_volume == 0 and total_spend == 0, write "Quiet day — no orders
   placed." as the summary and recommend reviewing yesterday's open items.

SCORE RUBRIC:
- 90-100: All KPIs green, zero stockouts, zero rollbacks, ≥1 order placed.
- 70-89:  Minor concerns (e.g., 1-2 flagged items, automation < 60%).
- 50-69:  At-risk SKUs > 3, forecast accuracy < 70%, or > 20% rollback.
- 0-49:   Stockouts present, supplier email failures, or no activity at all.

TONE: Operations manager / procurement analyst. No jargon, no marketing,
no AI hype, no greetings or sign-offs.
"""


@dataclass
class KPISummary:
    """Structured KPI summary from the agent."""
    summary: str = ""
    highlights: list[str] = field(default_factory=list)
    trends: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    risk_alerts: list[str] = field(default_factory=list)
    score: int = 0


class ReportingKPIAgent:
    """AutoGen-based agent that produces natural-language KPI summaries."""

    def __init__(self) -> None:
        self._client = get_model_client("lightweight")
        self._agent = AssistantAgent(
            name="reporting_kpi_agent",
            model_client=self._client,
            system_message=SYSTEM_PROMPT,
        )

    async def summarize(self, metrics: dict) -> KPISummary:
        """Analyze metrics and produce a KPISummary via the LLM."""
        prompt = f"Analyze these daily KPI metrics and provide your summary:\n{json.dumps(metrics, default=str)}"

        async def _once() -> KPISummary:
            response = await self._agent.on_messages(
                [TextMessage(content=prompt, source="system")],
                CancellationToken(),
            )

            text = response.chat_message.content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            try:
                data = json.loads(text)
            except (json.JSONDecodeError, ValueError, TypeError) as exc:
                raise LLMAgentError(
                    f"ReportingKPIAgent returned unparseable JSON: {exc}"
                ) from exc
            return KPISummary(
                summary=data.get("summary", ""),
                highlights=data.get("highlights", []),
                trends=data.get("trends", []),
                recommendations=data.get("recommendations", []),
                risk_alerts=data.get("risk_alerts", []),
                score=int(data.get("score", 0)),
            )

        return await invoke_with_retries(_once, agent_name="ReportingKPIAgent")

    async def close(self) -> None:
        """Clean up resources."""
        pass
