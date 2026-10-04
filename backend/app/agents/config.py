"""Groq LLM configuration for AutoGen agents.

Provides reusable model client factories for the two Groq-hosted models:
- Primary (llama-3.3-70b-versatile): complex reasoning tasks
- Lightweight (llama-3.1-8b-instant): simple formatting tasks
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Literal, TypeVar

from autogen_core.models import ModelInfo
from autogen_ext.models.openai import OpenAIChatCompletionClient

from app.config import get_settings

logger = logging.getLogger("agenticinventory.agents")


class LLMAgentError(RuntimeError):
    """Raised when an agent cannot obtain a usable LLM response after retries.

    Constitution II forbids substituting hard-coded rule engines for LLM
    inference, so every agent surfaces this error to its caller instead of
    silently producing a non-LLM result. Callers (typically pipeline services)
    are expected to log the failure, skip the affected work item, and continue.
    """


T = TypeVar("T")


def _is_rate_limit_error(exc: BaseException) -> bool:
    """Detect Groq/OpenAI rate-limit / quota errors that won't recover via retry."""
    # openai.RateLimitError has a 429 status_code; the daily TPD quota
    # will not free up within the retry window, so we should fail fast
    # and let the caller skip the current cycle.
    status = getattr(exc, "status_code", None)
    if status == 429:
        return True
    msg = str(exc).lower()
    return (
        "rate_limit_exceeded" in msg
        or "tokens per day" in msg
        or "tpd" in msg
        or "error code: 429" in msg
    )


async def invoke_with_retries(
    fn: Callable[[], Awaitable[T]],
    *,
    agent_name: str,
    attempts: int = 3,
    base_delay: float = 0.5,
) -> T:
    """Call ``fn`` up to ``attempts`` times with linear backoff.

    Any exception raised by ``fn`` is treated as a retryable failure. After
    the final attempt the original exception is re-raised wrapped in
    ``LLMAgentError`` so that callers can distinguish LLM-pipeline failures
    from other RuntimeErrors.

    Rate-limit (429 / daily token quota) errors are non-retryable within
    this short window — they're surfaced as ``LLMAgentError`` after the
    first attempt so the caller can skip and the loop doesn't burn more
    tokens hammering an exhausted quota.

    The underlying Groq HTTP client already retries 429/5xx responses
    internally; this helper sits one level above and additionally covers
    JSON-parse failures and grounding-check failures that the agent itself
    detects.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001 — agent-level retry boundary
            last_exc = exc
            if _is_rate_limit_error(exc):
                logger.warning(
                    "%s: rate limit hit (no retry) — %s",
                    agent_name,
                    exc,
                )
                raise LLMAgentError(
                    f"{agent_name} rate-limited by LLM provider; skipping"
                ) from exc
            logger.warning(
                "%s: LLM attempt %d/%d failed: %s",
                agent_name,
                attempt,
                attempts,
                exc,
            )
            if attempt < attempts:
                await asyncio.sleep(base_delay * attempt)
    raise LLMAgentError(
        f"{agent_name} failed to obtain a usable LLM response after "
        f"{attempts} attempts"
    ) from last_exc

# Groq-hosted Llama model capabilities
_MODEL_INFO = ModelInfo(
    vision=False,
    function_calling=True,
    json_output=True,
    family="unknown",
    structured_output=False,
)

ModelTier = Literal["primary", "lightweight"]


def get_model_client(
    tier: ModelTier = "primary",
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> OpenAIChatCompletionClient:
    """Create an OpenAI-compatible model client pointing at Groq.

    Args:
        tier: ``"primary"`` for llama-3.3-70b-versatile,
              ``"lightweight"`` for llama-3.1-8b-instant.
        temperature: Override default temperature (0.3).
        max_tokens: Override default max_tokens (4096).

    Returns:
        An ``OpenAIChatCompletionClient`` configured for Groq.

    Raises:
        ValueError: If ``GROQ_API_KEY`` is not set.
    """
    settings = get_settings()

    if not settings.GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY is not set. "
            "Add it to your .env file or environment variables."
        )

    model = (
        settings.GROQ_PRIMARY_MODEL
        if tier == "primary"
        else settings.GROQ_LIGHTWEIGHT_MODEL
    )

    temp = temperature if temperature is not None else settings.GROQ_TEMPERATURE
    tokens = max_tokens if max_tokens is not None else settings.GROQ_MAX_TOKENS

    logger.info("Creating Groq model client: model=%s tier=%s", model, tier)

    return OpenAIChatCompletionClient(
        model=model,
        api_key=settings.GROQ_API_KEY,
        base_url=settings.GROQ_BASE_URL,
        temperature=temp,
        max_tokens=tokens,
        model_info=_MODEL_INFO,
    )


def create_base_agent_config(
    name: str,
    system_message: str,
    tier: ModelTier = "primary",
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict:
    """Return kwargs dict for constructing an ``AssistantAgent``.

    Usage::

        from autogen_agentchat.agents import AssistantAgent
        cfg = create_base_agent_config("monitor", "You are …")
        agent = AssistantAgent(**cfg)

    Args:
        name: Agent name (must be a valid Python identifier).
        system_message: System prompt for the agent.
        tier: Model tier to use.
        temperature: Override default temperature.
        max_tokens: Override default max tokens.

    Returns:
        Dict with ``name``, ``model_client``, and ``system_message`` keys.
    """
    client = get_model_client(
        tier, temperature=temperature, max_tokens=max_tokens
    )

    logger.info("Configured agent: name=%s tier=%s", name, tier)

    return {
        "name": name,
        "model_client": client,
        "system_message": system_message,
    }


def setup_agent_logging(level: int = logging.INFO) -> None:
    """Wire AutoGen's built-in event logger into our logging hierarchy."""
    try:
        from autogen_core import EVENT_LOGGER_NAME

        event_logger = logging.getLogger(EVENT_LOGGER_NAME)
        event_logger.setLevel(level)

        if not event_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            event_logger.addHandler(handler)

        logger.info("AutoGen event logging enabled at level %s", level)
    except ImportError:
        logger.warning("autogen_core not available; event logging skipped")
