"""T020 — DeliveryEtaAgent unit tests.

Stubs `OpenAIChatCompletionClient.create` so the agent returns canned
JSON. Each scenario validates that the agent + validator combo produces
the expected intent / confidence / parsed_date triple.

Twelve canonical scenarios are parametrised inline rather than loaded
from `tests/fixtures/eta_agent/<slug>.eml` files because the supplier
body never reaches the stub LLM — only the canned JSON output matters
for behavioural coverage of the agent class.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.agents.config import LLMAgentError
from app.agents.delivery_eta import AgentInput, DeliveryEtaAgent, validate_extraction


_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_input(body: str = "the body") -> AgentInput:
    return AgentInput(
        now=_NOW,
        received_at=_NOW,
        from_address="supplier@example.com",
        subject="Re: PO 12345678",
        body=body,
    )


# (slug, agent_response, expected_intent_after_validate, min_conf, max_conf,
#  expects_parsed_date)
_SCENARIOS = [
    (
        "confirm_high_confidence",
        {
            "intent": "confirm",
            "parsed_date": "2026-06-09T10:00:00+00:00",
            "confidence": 95.0,
            "excerpt": "Order will arrive June 9 at 10am.",
            "reasoning": "Supplier confirmed a precise delivery date.",
        },
        "confirm", 90.0, 100.0, True,
    ),
    (
        "confirm_medium_confidence",
        {
            "intent": "confirm",
            "parsed_date": "2026-06-09T00:00:00+00:00",
            "confidence": 70.0,
            "excerpt": "Should ship by end of next week.",
            "reasoning": "Phrase 'should' lowers certainty.",
        },
        "confirm", 50.0, 80.0, True,
    ),
    (
        "confirm_low_confidence",
        {
            "intent": "confirm",
            "parsed_date": "2026-06-15T00:00:00+00:00",
            "confidence": 40.0,
            "excerpt": "Hoping mid-June works.",
            "reasoning": "Vague language.",
        },
        "confirm", 0.0, 50.0, True,
    ),
    (
        "delay_with_new_date",
        {
            "intent": "delay",
            "parsed_date": "2026-06-20T00:00:00+00:00",
            "confidence": 85.0,
            "excerpt": "Delayed to June 20.",
            "reasoning": "Explicit revised date.",
        },
        "delay", 80.0, 100.0, True,
    ),
    (
        "delay_no_date",
        {
            "intent": "delay",
            "parsed_date": None,
            "confidence": 60.0,
            "excerpt": "Will be delayed but unsure when.",
            "reasoning": "No new date provided.",
        },
        "unclear", 0.0, 40.0, False,  # validator downgrades
    ),
    (
        "cancel_full_order",
        {
            "intent": "cancel",
            "parsed_date": None,
            "confidence": 90.0,
            "excerpt": "We must cancel the order.",
            "reasoning": "Cancellation declared.",
        },
        "cancel", 80.0, 100.0, False,
    ),
    (
        "cancel_partial_lineitem",
        {
            "intent": "cancel",
            "parsed_date": None,
            "confidence": 75.0,
            "excerpt": "Cancelling SKU-A; rest ships as planned.",
            "reasoning": "Partial cancellation — caller may treat as confirm.",
        },
        "cancel", 60.0, 90.0, False,
    ),
    (
        "acknowledge_no_eta",
        {
            "intent": "acknowledge",
            "parsed_date": None,
            "confidence": 80.0,
            "excerpt": "Thanks, will update soon.",
            "reasoning": "Polite ack only.",
        },
        "acknowledge", 70.0, 90.0, False,
    ),
    (
        "acknowledge_with_attachment",
        {
            "intent": "acknowledge",
            "parsed_date": None,
            "confidence": 70.0,
            "excerpt": "See attached invoice.",
            "reasoning": "Attachment-only reply.",
        },
        "acknowledge", 60.0, 80.0, False,
    ),
    (
        "unclear_off_topic",
        {
            "intent": "unclear",
            "parsed_date": None,
            "confidence": 20.0,
            "excerpt": "Out of office until July.",
            "reasoning": "Auto-reply not about the order.",
        },
        "unclear", 0.0, 40.0, False,
    ),
    (
        "non_english",
        {
            "intent": "unclear",
            "parsed_date": None,
            "confidence": 25.0,
            "excerpt": "Bonjour, l'ordre est en route.",
            "reasoning": "Non-English body the model cannot reliably parse.",
        },
        "unclear", 0.0, 40.0, False,
    ),
    (
        "past_date",
        {
            "intent": "confirm",
            "parsed_date": "2026-05-15T00:00:00+00:00",  # before _NOW = 2026-06-01
            "confidence": 75.0,
            "excerpt": "Will arrive May 15.",
            "reasoning": "Supplier confused — date already passed.",
        },
        "confirm", 70.0, 80.0, True,  # agent still says confirm; ingestor raises 'past_date'
    ),
]


@pytest.mark.parametrize(
    "slug,response,expected_intent,min_conf,max_conf,expects_date",
    _SCENARIOS,
    ids=[s[0] for s in _SCENARIOS],
)
async def test_delivery_eta_agent_scenarios(
    stub_model_client,
    slug: str,
    response: dict,
    expected_intent: str,
    min_conf: float,
    max_conf: float,
    expects_date: bool,
) -> None:
    stub_model_client.set_responses([response])

    agent = DeliveryEtaAgent()
    try:
        raw_extraction = await agent.extract(_make_input())
    finally:
        await agent.close()

    validated = validate_extraction(raw_extraction, _NOW)
    assert validated.intent == expected_intent, slug
    assert min_conf <= float(validated.confidence) <= max_conf, slug
    if expects_date:
        assert validated.parsed_date is not None, slug
    else:
        # validator may keep or null the date; either is fine when expects_date=False
        pass


async def test_delivery_eta_agent_invalid_json_then_retry_then_fail(
    stub_model_client,
) -> None:
    """Invalid JSON → strict-JSON reminder retry → invalid again →
    ``invoke_with_retries`` retries the whole `_once` (so we burn six
    stub responses) → final failure as `LLMAgentError`.
    """
    bad = "not a json blob"
    # 3 attempts × 2 calls per attempt (initial + reminder) = 6 responses.
    stub_model_client.set_responses([bad] * 6)

    agent = DeliveryEtaAgent()
    try:
        with pytest.raises(LLMAgentError):
            await agent.extract(_make_input())
    finally:
        await agent.close()


async def test_validator_downgrades_when_no_date(stub_model_client) -> None:
    """Even if the LLM emits intent='delay' without a date, the validator
    downgrades to 'unclear' with confidence ≤ 40 so the ingestor routes
    the reply to review.
    """
    stub_model_client.set_responses(
        [
            {
                "intent": "delay",
                "parsed_date": None,
                "confidence": 80.0,
                "excerpt": "Delayed — no idea when.",
                "reasoning": "Date missing.",
            }
        ]
    )
    agent = DeliveryEtaAgent()
    try:
        raw = await agent.extract(_make_input())
    finally:
        await agent.close()

    validated = validate_extraction(raw, _NOW)
    assert validated.intent == "unclear"
    assert float(validated.confidence) <= 40.0
