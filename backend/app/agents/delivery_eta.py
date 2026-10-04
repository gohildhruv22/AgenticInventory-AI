"""DeliveryEtaAgent — AutoGen AssistantAgent that parses supplier replies.

Single-turn agent. Given the headers and plain-text body of a supplier
message, it returns a strict JSON `EtaExtraction` describing the supplier's
intent (confirm / delay / cancel / acknowledge / unclear), an absolute parsed
date (when one can be derived), the agent's confidence, a verbatim excerpt
from the message, and a short reasoning trace.

Constitution II compliance:
  - The agent NEVER falls back to a deterministic rule-engine. If the LLM
    fails to return parseable JSON twice (one "strict-JSON reminder" retry
    plus the outer `invoke_with_retries` loop), the caller receives
    ``LLMAgentError`` and the supplier reply is routed to the review queue
    by the caller (data-model §3, reason ``low_confidence`` is the default).
  - ``dateparser`` is used only as a *post-LLM validator* (research.md §5):
    the agent supplies an ISO-8601 string; the validator confirms it parses.
    If validation fails the extraction is downgraded to ``intent='unclear'``
    with lowered confidence so the reply is routed to review.

See specs/004-supplier-delivery-eta-agent/research.md §7.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime

import dateparser
from autogen_agentchat.agents import AssistantAgent  # noqa: F401 — for re-exports
from autogen_core.models import SystemMessage, UserMessage
from pydantic import ValidationError

from app.agents.config import (
    LLMAgentError,
    create_base_agent_config,
    get_model_client,  # noqa: F401 — retained for external callers
    invoke_with_retries,
)
from app.schemas.eta_review import EtaExtraction

logger = logging.getLogger("agenticinventory.agents.delivery_eta")


SYSTEM_PROMPT = """\
You are the Supplier Delivery ETA Agent.

Your job: read a single supplier email (headers + plain-text body) and decide
what the supplier is telling us about a delivery.

INPUT: a JSON object with these fields:
  - now_iso        : the current time as an ISO-8601 string with timezone.
  - received_at_iso: the email's Date header as ISO-8601 (use for relative dates).
  - from_address   : sender email (already lower-cased).
  - subject        : raw subject line.
  - body           : plain-text body (HTML stripped; ≤ 8 KB).

OUTPUT: return ONLY a strict JSON object — no markdown, no commentary — with
EXACTLY these keys:
  {
    "intent":        "confirm" | "delay" | "cancel" | "acknowledge" | "unclear",
    "parsed_date":   ISO-8601 string with timezone, or null,
    "confidence":    number from 0 to 100 inclusive,
    "excerpt":       a verbatim quote from the body (≤ 240 chars) that
                     supports your choice,
    "reasoning":     2-3 short sentences explaining your decision
  }

INTENT RULES:
  - "confirm"      : supplier explicitly affirms a specific delivery date.
  - "delay"        : supplier signals the delivery will be later than originally
                     scheduled (whether or not they provide a new date).
  - "cancel"       : supplier withdraws or refuses the order (in whole or in part).
  - "acknowledge"  : supplier confirms receipt of the PO but has not yet
                     committed to a delivery date.
  - "unclear"      : the message is off-topic, out-of-office, non-English you
                     cannot reliably parse, or otherwise lacks enough signal.

DATE RULES (CRITICAL):
  - Always resolve relative phrases ("next Tuesday", "end of week", "after the
    long weekend") to an ABSOLUTE date using `received_at_iso` as the anchor.
  - Return `parsed_date` as a full ISO-8601 timestamp with timezone (use UTC
    if the supplier did not specify; never invent a local timezone).
  - If you cannot find a defensible date, set `parsed_date` to null and lower
    your confidence — DO NOT GUESS.
  - If the only date you can extract is in the past relative to `now_iso`,
    return it anyway — downstream code will route it to review.

CONFIDENCE RULES:
  - 90-100: explicit absolute date in the body matching the subject.
  - 70-89 : clear intent but a relative phrase, or date only in subject.
  - 50-69 : intent reasonable but date inference required several hops.
  - 0-49  : guessing — prefer raising "unclear" with parsed_date=null.

NEVER add fields. NEVER wrap the JSON in markdown fences. Respond with the
JSON object only.
"""

_RETRY_REMINDER = (
    "Your previous response was not valid JSON or did not match the required "
    "schema. Respond again with ONLY a JSON object containing the exact keys "
    "intent, parsed_date, confidence, excerpt, reasoning — no markdown, no "
    "prose, no extra fields."
)


@dataclass
class AgentInput:
    """Structured input passed to the agent. Keeps prompt construction tidy."""

    now: datetime
    received_at: datetime
    from_address: str
    subject: str
    body: str

    def to_user_message(self) -> str:
        payload = {
            "now_iso": self.now.isoformat(),
            "received_at_iso": self.received_at.isoformat(),
            "from_address": self.from_address,
            "subject": self.subject,
            "body": self.body[:8192],
        }
        return json.dumps(payload, default=str)


class DeliveryEtaAgent:
    """Wraps an AutoGen AssistantAgent for ETA extraction.

    Use ``await DeliveryEtaAgent().extract(AgentInput(...))`` and feed the
    returned ``EtaExtraction`` through :func:`validate_extraction` to attach
    the post-LLM dateparser sanity check.
    """

    def __init__(self) -> None:
        self._config = create_base_agent_config(
            name="delivery_eta_agent",
            system_message=SYSTEM_PROMPT,
            tier="primary",
        )
        self._client = self._config["model_client"]
        logger.info("DeliveryEtaAgent initialized")

    async def extract(self, payload: AgentInput) -> EtaExtraction:
        """Run the agent and return a validated ``EtaExtraction``.

        Implements the research §7 "one strict-JSON reminder" retry inside a
        single call to :func:`invoke_with_retries`. The outer retry loop covers
        transient transport / 429 / 5xx failures. Persistent parse failure
        surfaces as ``LLMAgentError`` so the caller can route the reply to the
        review queue.
        """
        user_msg = payload.to_user_message()

        async def _once() -> EtaExtraction:
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                UserMessage(content=user_msg, source="user"),
            ]
            # First attempt.
            response = await self._client.create(
                messages=messages, json_output=True
            )
            raw = self._extract_text(response.content)
            try:
                return self._parse(raw)
            except LLMAgentError as first_err:
                logger.warning(
                    "DeliveryEtaAgent: first parse failed (%s); retrying with reminder",
                    first_err,
                )
                # Strict-JSON reminder retry — research §7.
                messages.append(UserMessage(content=raw, source="assistant"))
                messages.append(UserMessage(content=_RETRY_REMINDER, source="user"))
                retry = await self._client.create(
                    messages=messages, json_output=True
                )
                return self._parse(self._extract_text(retry.content))

        return await invoke_with_retries(_once, agent_name="DeliveryEtaAgent")

    @staticmethod
    def _extract_text(content) -> str:
        if isinstance(content, list):
            content = content[0] if content else ""
        return str(content)

    @staticmethod
    def _parse(raw: str) -> EtaExtraction:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        try:
            return EtaExtraction.model_validate_json(text)
        except (ValidationError, ValueError, TypeError) as exc:
            # Try one tolerant pass: parse as Python JSON then re-validate. The
            # model occasionally returns numeric strings or stray whitespace
            # the Pydantic JSON parser rejects.
            try:
                data = json.loads(text)
                return EtaExtraction.model_validate(data)
            except (ValidationError, ValueError, TypeError) as exc2:
                raise LLMAgentError(
                    f"DeliveryEtaAgent returned unparseable JSON: {exc2}"
                ) from exc

    async def close(self) -> None:
        try:
            await self._client.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# T016 — post-LLM validator
# ---------------------------------------------------------------------------


def validate_extraction(
    extraction: EtaExtraction,
    message_received_at: datetime,
) -> EtaExtraction:
    """Validate that the agent's ``parsed_date`` actually parses.

    Per research §5, ``dateparser`` is the deterministic post-LLM validator.
    If the agent emitted a parsed_date that ``dateparser`` cannot resolve to
    an absolute datetime, downgrade the extraction to ``intent='unclear'``
    with reduced confidence so the caller routes the reply to review.

    The validator is pure — it returns a new ``EtaExtraction`` and never
    mutates its input.
    """
    # Anchor relative parses to the email's Date header per research §5 / §7.
    settings = {
        "RELATIVE_BASE": message_received_at.replace(tzinfo=None)
        if message_received_at.tzinfo is None
        else message_received_at,
        "RETURN_AS_TIMEZONE_AWARE": True,
        "PREFER_DATES_FROM": "future",
    }

    # If the agent already gave a valid datetime, accept it.
    if extraction.parsed_date is not None:
        return extraction

    # Agent provided no date — leave intent untouched; downstream routes
    # delay/unclear/cancel without a date to review anyway.
    if extraction.intent == "unclear":
        return extraction

    # `cancel` and `acknowledge` are valid signals on their own — a cancel
    # ("we must cancel") doesn't need a date; the ingestor routes it via
    # raised_reason='negative_intent' separately. Keep the agent's intent.
    if extraction.intent in ("cancel", "acknowledge"):
        return extraction

    # The agent claimed a real intent (confirm/delay) but no date. Try to recover a date from
    # the excerpt as a last-ditch deterministic pass; if dateparser also fails,
    # downgrade to unclear so the reply goes to review.
    recovered = dateparser.parse(extraction.excerpt, settings=settings)  # type: ignore[arg-type]
    if recovered is not None:
        return extraction.model_copy(update={"parsed_date": recovered})

    return extraction.model_copy(
        update={
            "intent": "unclear",
            "confidence": min(extraction.confidence, 40.0),
        }
    )
