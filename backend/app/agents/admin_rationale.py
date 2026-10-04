"""Admin Rationale Agent — produces a grounded LLM narrative for the
admin-notification email.

Per Constitution II this agent has no hard-coded fallback path: if the LLM
cannot produce a grounded, non-empty rationale after retries, the call raises
``LLMAgentError`` and the caller decides how to surface the failure.

See specs/003-email-redesign/spec.md FR-006 / FR-007 / FR-008 / FR-009.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Literal

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from app.agents.config import LLMAgentError, get_model_client, invoke_with_retries

logger = logging.getLogger("agenticinventory.agents.admin_rationale")

# Hard limits per FR-009.
_MAX_RATIONALE_CHARS = 500
_TRUNCATE_TARGET_CHARS = 400

SYSTEM_PROMPT = """You are the Admin Rationale Agent for AgenticInventory AI.

Your job: explain *why* the autonomous agent made a specific purchase decision,
in plain English, for the human administrator who will review the order.

INPUT: a JSON object describing the decision — confidence score (0-1),
order summary, decision drivers (forecast and KPI signals), and alternatives
considered.

OUTPUT: respond with valid JSON containing exactly these keys:
  - "rationale": 2-4 sentences (≤ 500 characters) explaining the decision in
    natural English for a busy admin.
  - "headline": a single short sentence (≤ 90 characters) suitable as a
    one-line summary at the top of the email.

CRITICAL RULES:
1. GROUNDING. Every number you mention MUST appear verbatim in the input. Do
   NOT invent figures, percentages, dates, dollar amounts, or unit counts. If
   you cannot say something with a number from the input, describe it
   qualitatively instead.
2. Be specific. Reference at least 2 of the supplied decision drivers.
3. Plain English. No marketing language, no AI jargon, no model names, no
   buzzwords. Write like a procurement analyst.
4. No greetings or sign-offs. Just the rationale.
5. ALWAYS output valid JSON. No markdown fences. No extra commentary.
"""


@dataclass
class DecisionDriver:
    """A single forecast / KPI signal that fed into the decision."""

    label: str
    value: str
    trend: str = ""  # "up" | "down" | "flat" | ""


@dataclass
class Alternative:
    """An option the agent considered but did not take."""

    option: str
    score: str = ""
    deciding_factor: str = ""


@dataclass
class AdminRationaleContext:
    """Input to the rationale agent."""

    order_id: str
    item_name: str
    supplier_name: str
    total_cost: float
    confidence: float  # 0-1
    decision: str  # "approve" | "flag" | "reject" | ...
    drivers: list[DecisionDriver] = field(default_factory=list)
    alternatives: list[Alternative] = field(default_factory=list)

    def to_prompt_dict(self) -> dict:
        return {
            "order_id": self.order_id[:8].upper(),
            "item": self.item_name,
            "supplier": self.supplier_name,
            "total_cost_usd": round(float(self.total_cost), 2),
            "confidence": round(float(self.confidence), 2),
            "decision": self.decision,
            "decision_drivers": [asdict(d) for d in self.drivers],
            "alternatives_considered": [asdict(a) for a in self.alternatives],
        }


@dataclass
class AdminRationaleResult:
    """Output of the rationale agent."""

    rationale: str
    headline: str
    source: Literal["llm"] = "llm"
    truncated: bool = False


# Matches integers, decimals, percentages, currency-formatted numbers.
_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _extract_numbers(text: str) -> set[str]:
    """Return a normalized set of numeric tokens appearing in text."""
    out: set[str] = set()
    for raw in _NUMBER_RE.findall(text or ""):
        norm = raw.replace(",", "").lstrip("0") or "0"
        if "." in norm:
            norm = norm.rstrip("0").rstrip(".") or "0"
        out.add(norm)
    return out


def _grounded(rationale: str, context: AdminRationaleContext) -> bool:
    """FR-007: every number in the rationale must appear in the input."""
    input_numbers = _extract_numbers(json.dumps(context.to_prompt_dict(), default=str))
    # Confidence is often phrased as a percentage in the rationale — accept
    # both 0.87 and 87 as the same grounded value.
    extras: set[str] = set()
    for n in list(input_numbers):
        try:
            f = float(n)
        except ValueError:
            continue
        if 0 < f < 1:
            pct = f * 100
            extras.add(str(int(pct)) if pct.is_integer() else f"{pct:.0f}")
            extras.add(f"{pct:.1f}".rstrip("0").rstrip("."))
    input_numbers |= extras

    out_numbers = _extract_numbers(rationale)
    ungrounded = out_numbers - input_numbers
    if ungrounded:
        logger.warning(
            "Rationale failed grounding check; ungrounded numbers: %s",
            sorted(ungrounded),
        )
        return False
    return True


def _truncate_at_sentence(text: str) -> tuple[str, bool]:
    """Truncate at a sentence boundary at or below the target length (FR-009)."""
    if len(text) <= _MAX_RATIONALE_CHARS:
        return text, False
    cutoff = text[:_TRUNCATE_TARGET_CHARS]
    # Prefer to truncate at the last sentence boundary.
    last_punct = max(cutoff.rfind("."), cutoff.rfind("!"), cutoff.rfind("?"))
    if last_punct >= 200:
        cutoff = cutoff[: last_punct + 1]
    return cutoff.rstrip() + " (full reasoning in app)", True


class AdminRationaleAgent:
    """Generates a grounded natural-language rationale for the admin email."""

    def __init__(self) -> None:
        # Per Constitution II we do not catch LLM-init failure here; if Groq is
        # unavailable the caller will see the underlying ValueError immediately.
        self._client = get_model_client("lightweight")
        self._agent: AssistantAgent = AssistantAgent(
            name="admin_rationale_agent",
            model_client=self._client,
            system_message=SYSTEM_PROMPT,
        )

    async def generate(self, context: AdminRationaleContext) -> AdminRationaleResult:
        """Produce a rationale + headline. Raises ``LLMAgentError`` on failure."""
        prompt = (
            "Generate a rationale for this purchase decision. "
            "Remember: every number you write MUST appear in the JSON below.\n\n"
            + json.dumps(context.to_prompt_dict(), default=str, indent=2)
        )

        async def _once() -> AdminRationaleResult:
            response = await self._agent.on_messages(
                [TextMessage(content=prompt, source="system")],
                CancellationToken(),
            )
            text = (response.chat_message.content or "").strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
            try:
                data = json.loads(text)
            except (json.JSONDecodeError, ValueError, TypeError) as exc:
                raise LLMAgentError(
                    f"AdminRationaleAgent returned unparseable JSON: {exc}"
                ) from exc
            rationale = str(data.get("rationale", "")).strip()
            headline = str(data.get("headline", "")).strip()

            if not rationale:
                raise LLMAgentError("AdminRationaleAgent returned empty rationale")
            if not _grounded(rationale, context):
                raise LLMAgentError(
                    "AdminRationaleAgent rationale failed grounding check"
                )

            truncated_text, truncated = _truncate_at_sentence(rationale)
            if not headline:
                headline = (
                    f"{context.item_name}: order with {context.supplier_name} at "
                    f"{round(context.confidence * 100)}% confidence"
                )[:90]
            return AdminRationaleResult(
                rationale=truncated_text,
                headline=headline[:120],
                source="llm",
                truncated=truncated,
            )

        return await invoke_with_retries(_once, agent_name="AdminRationaleAgent")

    async def close(self) -> None:
        """Release resources (autogen client is async-capable)."""
        if self._client is not None:
            try:
                close = getattr(self._client, "close", None)
                if callable(close):
                    res = close()
                    if hasattr(res, "__await__"):
                        await res
            except Exception:  # noqa: BLE001
                pass
