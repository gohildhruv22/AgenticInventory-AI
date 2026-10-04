"""Supplier Email Agent — AutoGen AssistantAgent with Groq LLM.

Composes professional purchase order emails and admin notification emails
based on approved order decisions. Handles category-based supplier lookup
and produces structured email content with reasoning traces.
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

logger = logging.getLogger("agenticinventory.agents.supplier_email")

SYSTEM_PROMPT = """\
You are a Supplier Email Agent. Compose a professional purchase order email \
to a supplier plus an admin notification summary.

INPUT: {"order":{order_id,supplier_name,supplier_email,
items:[{name,sku,category,quantity,unit_cost}],total_cost,urgency},
"decision_context":{decision,confidence,reasoning,risk_factors},
"company":{name,contact_email}}

OUTPUT (JSON only, no markdown):
{"subject":"...","body_text":"...",
 "body_html_variables":{"greeting":"...","intro_paragraph":"...",
   "closing_paragraph":"...","urgency_note":"..."},
 "admin_summary":{"subject":"...","summary":"...","action_required":bool},
 "reasoning":"<1 sentence>"}

RULES:
- Subject includes order_id and category.
- urgency=critical → "[URGENT]" prefix + expedited request.
- urgency=high → mention preferred delivery timeline.
- Include all items (name, sku, qty, unit_cost, line total) and total_cost.
- Professional, concise tone.
- admin_summary.action_required = true when confidence < 80 or high cost.
- Output VALID JSON only.
"""


@dataclass
class EmailComposition:
    """Parsed output from the Supplier Email Agent."""

    subject: str
    body_text: str
    body_html_variables: dict = field(default_factory=dict)
    admin_summary: dict = field(default_factory=dict)
    reasoning: str = ""


class SupplierEmailAgent:
    """Wraps an AutoGen AssistantAgent configured for email composition."""

    def __init__(self) -> None:
        self._config = create_base_agent_config(
            name="supplier_email_agent",
            system_message=SYSTEM_PROMPT,
            tier="lightweight",
            max_tokens=1024,
        )
        self._client = self._config["model_client"]
        logger.info("SupplierEmailAgent initialized")

    async def compose(
        self,
        order: dict,
        decision_context: dict,
        company: dict | None = None,
    ) -> EmailComposition:
        """Compose a purchase order email and admin notification.

        Args:
            order: Order details with items, supplier info, costs.
            decision_context: Decision reasoning for context.
            company: Company info for email branding.

        Returns:
            ``EmailComposition`` with subject, body, and admin summary.
        """
        if company is None:
            company = {
                "name": "AgenticInventory AI",
                "contact_email": "procurement@agenticinventory.ai",
            }

        payload = json.dumps(
            {
                "order": order,
                "decision_context": decision_context,
                "company": company,
            },
            default=str,
        )

        logger.info(
            "Composing email for order=%s supplier=%s",
            order.get("order_id", "?"),
            order.get("supplier_name", "?"),
        )

        async def _once() -> EmailComposition:
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

        result = await invoke_with_retries(_once, agent_name="SupplierEmailAgent")
        logger.info(
            "Email composed: subject=%s",
            result.subject[:60],
        )
        return result

    def _parse_response(self, raw: str) -> EmailComposition:
        """Parse JSON from the LLM response. Raises on parse failure."""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            raise LLMAgentError(
                f"SupplierEmailAgent returned unparseable JSON: {exc}"
            ) from exc
        return EmailComposition(
            subject=str(data.get("subject", "")),
            body_text=str(data.get("body_text", "")),
            body_html_variables=dict(data.get("body_html_variables", {})),
            admin_summary=dict(data.get("admin_summary", {})),
            reasoning=str(data.get("reasoning", "")),
        )

    async def close(self) -> None:
        """Clean up model client resources."""
        if hasattr(self._client, "close"):
            await self._client.close()
        elif hasattr(self._client, "aclose"):
            await self._client.aclose()
