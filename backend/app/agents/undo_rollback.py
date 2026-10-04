"""Undo & Rollback Agent — analyzes action dependencies, determines reversibility,
and explains what was rolled back using AutoGen + Groq."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from app.agents.config import LLMAgentError, get_model_client, invoke_with_retries

logger = logging.getLogger("agenticinventory.agents.undo_rollback")

SYSTEM_PROMPT = """You are the Undo & Rollback Agent for AgenticInventory AI.

Your job is to analyze a decision and its related actions to determine:
1. Whether the decision can be safely reversed
2. What compensating actions are needed
3. A clear explanation of what will be (or was) rolled back

INPUT: You receive a JSON object with:
- decision: the agent decision record (status, reasoning, confidence, etc.)
- action_logs: list of action log entries tied to this decision
- related_entities: current state of related supplier orders, deliveries, inventory items

OUTPUT: You MUST respond with valid JSON containing these keys:
- "can_undo": boolean — whether the decision can be safely rolled back
- "reason": string — why it can or cannot be undone
- "risk_level": "low" | "medium" | "high" — risk assessment for the rollback
- "steps": list of strings — human-readable description of each rollback step
- "warnings": list of strings — any warnings or caveats (empty list if none)
- "summary": string — 1-2 sentence summary of the rollback plan or explanation

RULES:
1. A decision CANNOT be undone if:
   - A delivery has reached "delivered" stage (supplier already shipped)
   - The decision is already rolled back
   - The decision status is "rejected" (nothing was executed)
2. Mark risk as "high" if a cancellation email must be sent to a supplier.
3. Mark risk as "medium" if inventory levels will change.
4. Mark risk as "low" for decisions with no external side effects.
5. Always be specific about what will change.
6. Use professional, clear language.
7. Always output valid JSON — no markdown, no extra text.
"""


@dataclass
class RollbackAnalysis:
    """Structured rollback analysis from the agent."""
    can_undo: bool = True
    reason: str = ""
    risk_level: str = "low"
    steps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: str = ""


class UndoRollbackAgent:
    """AutoGen-based agent that analyzes decisions for reversibility
    and explains rollback plans."""

    def __init__(self) -> None:
        self._client = get_model_client("lightweight")
        self._agent = AssistantAgent(
            name="undo_rollback_agent",
            model_client=self._client,
            system_message=SYSTEM_PROMPT,
        )

    async def analyze(
        self,
        decision_data: dict,
        action_logs: list[dict],
        related_entities: dict,
    ) -> RollbackAnalysis:
        """Analyze a decision and determine if it can be rolled back.

        Args:
            decision_data: The agent decision record.
            action_logs: Action log entries tied to this decision.
            related_entities: Current state of supplier orders, deliveries, items.

        Returns:
            A ``RollbackAnalysis`` with the agent's assessment.
        """
        context = {
            "decision": decision_data,
            "action_logs": action_logs,
            "related_entities": related_entities,
        }

        prompt = (
            "Analyze this decision and determine if it can be safely rolled back. "
            "Consider all related entities and action history:\n"
            f"{json.dumps(context, default=str)}"
        )

        async def _once() -> RollbackAnalysis:
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
                    f"UndoRollbackAgent returned unparseable JSON: {exc}"
                ) from exc
            return RollbackAnalysis(
                can_undo=data.get("can_undo", True),
                reason=data.get("reason", ""),
                risk_level=data.get("risk_level", "low"),
                steps=data.get("steps", []),
                warnings=data.get("warnings", []),
                summary=data.get("summary", ""),
            )

        return await invoke_with_retries(_once, agent_name="UndoRollbackAgent")

    async def explain_rollback(self, rollback_summary: dict) -> str:
        """Generate a human-readable explanation of a completed rollback."""
        prompt = (
            "A rollback has been completed. Explain in 2-3 sentences what happened. "
            "Use past tense and be specific about what was reversed:\n"
            f"{json.dumps(rollback_summary, default=str)}"
        )

        async def _once() -> str:
            response = await self._agent.on_messages(
                [TextMessage(content=prompt, source="system")],
                CancellationToken(),
            )
            text = response.chat_message.content.strip()
            if not text:
                raise LLMAgentError("UndoRollbackAgent returned empty explanation")
            return text

        return await invoke_with_retries(_once, agent_name="UndoRollbackAgent.explain")

    async def close(self) -> None:
        """Clean up resources."""
        pass
