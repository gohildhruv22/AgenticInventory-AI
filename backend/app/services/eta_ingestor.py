"""Supplier-reply ingestor — feature 004.

Responsibilities:
  - Connect to the configured IMAP inbox via :class:`ImapClient`
    (or any :class:`ImapClientProtocol` implementation — the fake is used
    in tests);
  - Fetch UNSEEN messages once per cycle;
  - Persist each as a :class:`SupplierReply`, deduplicating on
    ``message_id`` (and on the SHA-256 fallback key when Message-Id is
    absent — research §6);
  - Try to match the reply to an open :class:`SupplierOrder` (T023);
  - For matched, non-delivered orders: run the
    :class:`DeliveryEtaAgent` (T025), decide auto-apply (T026) vs review
    queue (T027) based on ``confidence_threshold`` and the FR-011 rules;
  - For replies that arrive after the order delivered: write a
    ``note`` timeline entry, skip the agent (FR-006);
  - Mark each message as ``\\Seen`` only after its DB transaction
    commits — preserves at-least-once / idempotent semantics on crash.

Constitution II — every LLM call goes through :func:`invoke_with_retries`
inside :class:`DeliveryEtaAgent.extract`. On terminal parse failure the
ingestor routes the reply to the review queue (raised_reason
``low_confidence``) instead of dropping it (FR-014).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Awaitable, Callable, Sequence

from dateutil import parser as dateutil_parser
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.config import LLMAgentError
from app.agents.delivery_eta import AgentInput, DeliveryEtaAgent, validate_extraction
from app.database import async_session_factory
from app.email.imap import ImapClient, ImapClientProtocol, RawMessage
from app.models.delivery import Delivery
from app.models.email_config import EmailConfiguration
from app.models.supplier_order import SupplierOrder
from app.models.supplier_reply import SupplierReply
from app.schemas.eta_review import EtaExtraction
from app.services.delivery_service import (
    append_timeline_entry,
    apply_eta_update,
    publish_timeline_event,
    serialise_delivery_summary,
    serialise_timeline_entry,
)
from app.services.eta_review_service import (
    raise_review_item,
    serialise_review_summary,
)
from app.websocket.events import (
    publish_eta_review_raised,
    publish_timeline_appended,
)

logger = logging.getLogger("agenticinventory.services.eta_ingestor")


# ---------------------------------------------------------------------------
# T023 — matching
# ---------------------------------------------------------------------------

# Canonical supplier-side references the order agent embeds in subjects:
#   - "Order #<uuid>"  — full UUID emitted by SupplierEmailAgent
#   - "PO <UUID8>"      — short reference used in human follow-ups
_ORDER_UUID_RE = re.compile(
    r"order\s*#\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)
_ORDER_SHORT_RE = re.compile(r"\bPO\s+([0-9a-f]{8})\b", re.IGNORECASE)

# Body scan window — research §6 says match on subject + first 4 KB of body.
_BODY_MATCH_WINDOW = 4096


@dataclass
class MatchResult:
    """Outcome of :func:`match_reply_to_order`.

    - ``order``/``delivery`` resolved: confident match — auto-apply
      remains gated on the agent's confidence vs the configured threshold.
    - ``order``/``delivery`` are ``None`` and ``candidate_order_ids`` may
      be non-empty: ambiguous match (multiple open orders from same
      supplier) — caller raises a review with reason ``ambiguous_match``.
    - Everything ``None``: unmatched — caller raises with
      ``unmatched_order``.
    """

    order: SupplierOrder | None = None
    delivery: Delivery | None = None
    candidate_order_ids: list[uuid.UUID] = field(default_factory=list)
    match_confidence: int = 0  # 0..100 — only used for telemetry
    rationale: str = ""


async def _fetch_delivery_for_order(
    session: AsyncSession, order_id: uuid.UUID
) -> Delivery | None:
    row = await session.execute(
        select(Delivery).where(Delivery.order_id == order_id)
    )
    return row.scalar_one_or_none()


def _normalise_address(addr: str) -> str:
    return (addr or "").strip().lower()


async def match_reply_to_order(
    session: AsyncSession, reply: RawMessage | SupplierReply
) -> MatchResult:
    """Try to locate the :class:`SupplierOrder` that ``reply`` answers.

    Strategy (research §6):
      1. Explicit ``Order #<uuid>`` in subject or first 4 KB of body — full
         UUID is the strongest signal; lookup by id.
      2. ``PO <UUID8>`` — match against the first 8 hex chars of
         ``supplier_orders.id``; ambiguous if more than one hit.
      3. Fallback: open orders sent to the supplier whose email matches
         the reply's ``from_address`` in the last 30 days. One hit =>
         candidate; many => ambiguous; zero => unmatched.

    ``In-Reply-To`` / ``References`` headers boost the rationale string
    but do not change the match (we'd need to persist outbound
    Message-Ids on ``supplier_orders`` to chain by header, which is a
    separate feature).
    """
    if isinstance(reply, RawMessage):
        subject = reply.subject or ""
        body = (reply.body_text or "")[:_BODY_MATCH_WINDOW]
        from_address = _normalise_address(reply.from_address)
        headers = reply.headers
    else:
        subject = reply.subject or ""
        body = (reply.body_excerpt or "")[:_BODY_MATCH_WINDOW]
        from_address = _normalise_address(reply.from_address)
        headers = reply.raw_headers or {}

    search_blob = f"{subject}\n{body}"

    # 1. Full UUID
    m = _ORDER_UUID_RE.search(search_blob)
    if m:
        try:
            order_id = uuid.UUID(m.group(1))
        except ValueError:
            order_id = None
        if order_id is not None:
            order = (
                await session.execute(
                    select(SupplierOrder).where(SupplierOrder.id == order_id)
                )
            ).scalar_one_or_none()
            if order is not None:
                delivery = await _fetch_delivery_for_order(session, order.id)
                in_reply_to = bool(
                    headers.get("In-Reply-To") or headers.get("References")
                )
                conf = 100 if in_reply_to else 95
                return MatchResult(
                    order=order,
                    delivery=delivery,
                    candidate_order_ids=[order.id],
                    match_confidence=conf,
                    rationale="full_uuid_in_subject_or_body",
                )

    # 2. Short PO ref (first 8 hex chars of id)
    short_hits = _ORDER_SHORT_RE.findall(search_blob)
    if short_hits:
        short = short_hits[0].lower()
        # SQLite stores UUIDs as text — we can substring on the string
        # form of the id. To stay portable we cast and prefix-match.
        rows = (
            await session.execute(
                select(SupplierOrder).where(
                    SupplierOrder.id.cast(__import__("sqlalchemy").String).like(
                        f"{short}%"
                    )
                )
            )
        ).scalars().all()
        if len(rows) == 1:
            order = rows[0]
            return MatchResult(
                order=order,
                delivery=await _fetch_delivery_for_order(session, order.id),
                candidate_order_ids=[order.id],
                match_confidence=80,
                rationale="po_short_ref",
            )
        if len(rows) > 1:
            return MatchResult(
                candidate_order_ids=[r.id for r in rows],
                match_confidence=40,
                rationale="po_short_ref_ambiguous",
            )

    # 3. Fallback — recent open orders from the same supplier address.
    if from_address:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        rows = (
            await session.execute(
                select(SupplierOrder).where(
                    SupplierOrder.supplier_email == from_address,
                    SupplierOrder.created_at >= cutoff,
                )
            )
        ).scalars().all()
        # Filter to orders whose delivery hasn't been marked 'delivered'.
        open_rows: list[SupplierOrder] = []
        for o in rows:
            d = await _fetch_delivery_for_order(session, o.id)
            if d is None or d.current_stage != "delivered":
                open_rows.append(o)
        if len(open_rows) == 1:
            order = open_rows[0]
            return MatchResult(
                order=order,
                delivery=await _fetch_delivery_for_order(session, order.id),
                candidate_order_ids=[order.id],
                match_confidence=55,
                rationale="sender_30d_single_open_order",
            )
        if len(open_rows) > 1:
            return MatchResult(
                candidate_order_ids=[o.id for o in open_rows],
                match_confidence=25,
                rationale="sender_30d_multiple_open_orders",
            )

    return MatchResult(rationale="no_match")


# ---------------------------------------------------------------------------
# T024 — persistence + dedupe
# ---------------------------------------------------------------------------

_AUTO_SUBMITTED_VALUES: frozenset[str] = frozenset(
    {"auto-replied", "auto-generated", "auto-notified"}
)
# Common bounce / delivery-status senders.
_BOUNCE_SENDERS = ("mailer-daemon@", "postmaster@", "noreply@", "no-reply@")


def _is_machine_generated(raw: RawMessage) -> bool:
    """Return True for auto-replies / bounces (FR-008)."""
    h = {k.lower(): str(v).strip().lower() for k, v in (raw.headers or {}).items()}
    auto = h.get("auto-submitted", "")
    if auto and auto != "no" and any(v in auto for v in _AUTO_SUBMITTED_VALUES):
        return True
    if h.get("precedence", "") in ("bulk", "auto_reply", "list"):
        return True
    from_addr = (raw.from_address or "").lower()
    if any(from_addr.startswith(p) for p in _BOUNCE_SENDERS):
        return True
    return False


def _fallback_dedupe_key(raw: RawMessage) -> str:
    """SHA-256 of (from, date, subject, first 256 body chars) — research §6."""
    payload = "|".join(
        [
            raw.from_address or "",
            raw.date or "",
            raw.subject or "",
            (raw.body_text or "")[:256],
        ]
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()


def _parse_received_at(raw: RawMessage) -> datetime:
    if raw.date:
        try:
            dt = dateutil_parser.parse(raw.date)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError, OverflowError):
            pass
    return datetime.now(timezone.utc)


async def persist_reply(
    session: AsyncSession,
    *,
    raw: RawMessage,
    match: MatchResult,
) -> SupplierReply | None:
    """Insert a new ``supplier_replies`` row.

    Returns ``None`` when the row already exists (idempotent — FR-007) and
    the caller can safely skip processing. Returns the inserted row
    otherwise.

    Machine-generated mail (auto-replies, bounces) is persisted with
    ``processing_status='ignored'`` so the operator can still audit it,
    but the caller MUST NOT run the agent against it (FR-008).
    """
    message_id = (raw.message_id or "").strip() or _fallback_dedupe_key(raw)

    # Dedupe — try insert and catch UNIQUE violation via a precheck. Both are
    # safe under SQLite given the ingestor's single-cycle advisory lock.
    existing = (
        await session.execute(
            select(SupplierReply).where(SupplierReply.message_id == message_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        logger.info(
            "persist_reply: skipping duplicate message_id=%s reply_id=%s",
            message_id,
            existing.id,
        )
        return None

    status = "ignored" if _is_machine_generated(raw) else "new"

    reply = SupplierReply(
        message_id=message_id,
        from_address=_normalise_address(raw.from_address),
        subject=(raw.subject or "")[:998],
        received_at=_parse_received_at(raw),
        body_excerpt=(raw.body_text or "")[:65536],
        raw_headers=dict(raw.headers or {}),
        matched_order_id=match.order.id if match.order else None,
        matched_delivery_id=match.delivery.id if match.delivery else None,
        processing_status=status,
    )
    session.add(reply)
    await session.flush()
    logger.info(
        "persist_reply: reply_id=%s status=%s matched_order=%s match_conf=%d (%s)",
        reply.id,
        status,
        match.order.id if match.order else None,
        match.match_confidence,
        match.rationale,
    )
    return reply


# ---------------------------------------------------------------------------
# T025 — agent + dispatch
# ---------------------------------------------------------------------------


# Map raised-reason heuristics — keep this in one place so the unit tests can
# pin behaviour without re-deriving it.
def _decide_raised_reason(
    extraction: EtaExtraction,
    match: MatchResult,
    *,
    threshold: float,
) -> str | None:
    """Return the ``raised_reason`` if the extraction needs review, else ``None``.

    Order of checks (FR-011 + research §8):
      - cancel intent or any "negative" signal → ``negative_intent``;
      - unmatched order → ``unmatched_order``;
      - ambiguous match → ``ambiguous_match``;
      - parsed_date in the past → ``past_date``;
      - unclear intent → ``low_confidence``;
      - confidence below threshold → ``low_confidence``.
    """
    if extraction.intent == "cancel":
        return "negative_intent"
    if match.order is None and match.candidate_order_ids:
        return "ambiguous_match"
    if match.order is None:
        return "unmatched_order"
    if extraction.parsed_date is not None:
        now = datetime.now(timezone.utc)
        pd = extraction.parsed_date
        if pd.tzinfo is None:
            pd = pd.replace(tzinfo=timezone.utc)
        if pd < now - timedelta(hours=1):
            return "past_date"
    if extraction.intent == "unclear":
        return "low_confidence"
    if float(extraction.confidence) < threshold:
        return "low_confidence"
    return None


async def process_reply(
    session: AsyncSession,
    *,
    reply: SupplierReply,
    match: MatchResult,
    agent: DeliveryEtaAgent,
    threshold: float = 80.0,
) -> dict[str, Any]:
    """Run the agent on a parsed reply and dispatch the outcome.

    Returns a summary dict for cycle telemetry and the ingestor's post-
    commit WebSocket broadcast step (callers MUST commit before firing
    the events).

    Possible return shapes (`outcome` field):
      - ``"applied"`` — high-confidence confirm/delay/acknowledge,
        ``apply_eta_update`` was called; ``timeline_event_payload`` is set;
      - ``"review"`` — review queue item was raised; ``review_payload``
        and optionally ``timeline_event_payload`` are set;
      - ``"delivered_note"`` — order already delivered; only a ``note``
        timeline entry was appended (FR-006);
      - ``"failed"`` — agent failed even after retries; the reply was
        flipped to ``processing_status='failed'`` AND a review was
        raised so no signal is lost.
    """
    delivery = match.delivery
    # Replies to already-delivered orders never run the agent (FR-006).
    if delivery is not None and delivery.current_stage == "delivered":
        entry = await append_timeline_entry(
            session,
            delivery_id=delivery.id,
            event_type="note",
            occurred_at=datetime.now(timezone.utc),
            actor_type="agent",
            actor_id="delivery_eta_agent",
            supplier_excerpt=(reply.body_excerpt or "")[:1000],
            source_reply_id=reply.id,
            note="Supplier reply received after delivery completion; no ETA change.",
        )
        reply.processing_status = "parsed"
        reply.agent_response = {"outcome": "delivered_note"}
        return {
            "outcome": "delivered_note",
            "delivery": delivery,
            "timeline_entry": entry,
        }

    payload = AgentInput(
        now=datetime.now(timezone.utc),
        received_at=reply.received_at,
        from_address=reply.from_address,
        subject=reply.subject,
        body=reply.body_excerpt,
    )

    try:
        extraction = await agent.extract(payload)
        extraction = validate_extraction(extraction, reply.received_at)
    except LLMAgentError as exc:
        # Surface but DO NOT drop — raise a review so no supplier signal is lost.
        logger.warning(
            "process_reply: agent failed (reply_id=%s): %s — routing to review",
            reply.id,
            exc,
        )
        reply.processing_status = "failed"
        reply.error_detail = str(exc)[:2000]
        # Manufacture a minimal "unclear" extraction for the review row so the
        # operator sees that the agent itself failed.
        synthetic = EtaExtraction(
            intent="unclear",
            parsed_date=None,
            confidence=0.0,
            excerpt=(reply.body_excerpt or "")[:1000] or "(empty body)",
            reasoning=f"LLM extraction failed after retries: {exc}",
        )
        review, timeline_entry = await raise_review_item(
            session,
            reply=reply,
            extraction=synthetic,
            raised_reason="low_confidence",
            candidate_delivery=delivery,
            candidate_order_ids=match.candidate_order_ids,
        )
        # Reply moves to in_review only after agent_response is recorded.
        reply.processing_status = "in_review"
        return {
            "outcome": "failed",
            "review": review,
            "delivery": delivery,
            "timeline_entry": timeline_entry,
        }

    # Persist the agent's raw response on the reply for traceability.
    reply.agent_response = extraction.model_dump(mode="json")
    reply.processing_status = "parsed"

    reason = _decide_raised_reason(extraction, match, threshold=threshold)

    # ---- review path ------------------------------------------------------
    if reason is not None:
        review, timeline_entry = await raise_review_item(
            session,
            reply=reply,
            extraction=extraction,
            raised_reason=reason,
            candidate_delivery=delivery,
            candidate_order_ids=match.candidate_order_ids,
        )
        reply.processing_status = "in_review"
        return {
            "outcome": "review",
            "review": review,
            "delivery": delivery,
            "timeline_entry": timeline_entry,
        }

    # ---- auto-apply path -------------------------------------------------
    assert delivery is not None  # _decide_raised_reason guarantees this
    timeline_entry = await apply_eta_update(
        session,
        delivery=delivery,
        extraction=extraction,
        reply=reply,
    )
    reply.processing_status = "applied"
    return {
        "outcome": "applied",
        "delivery": delivery,
        "timeline_entry": timeline_entry,
    }


# ---------------------------------------------------------------------------
# T028 — top-level cycle
# ---------------------------------------------------------------------------


_INGESTOR_LOCK = asyncio.Lock()  # process-wide guard (advisory)


@dataclass
class IngestorCycleSummary:
    """Returned by :func:`run_ingestor_cycle` for telemetry / tests."""

    fetched: int = 0
    persisted: int = 0
    duplicates: int = 0
    ignored: int = 0
    auto_applied: int = 0
    raised_reviews: int = 0
    delivered_notes: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


# Type alias for the dependency-injected client factory.
ClientFactory = Callable[[], Awaitable[ImapClientProtocol]] | Callable[
    [], ImapClientProtocol
]


async def _load_imap_config(
    session: AsyncSession,
) -> EmailConfiguration | None:
    """Return the most recently created `email_configurations` row with
    IMAP fields populated, or ``None`` if no inbox is configured.
    """
    row = (
        await session.execute(
            select(EmailConfiguration)
            .where(EmailConfiguration.imap_host.is_not(None))
            .order_by(EmailConfiguration.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return row


async def _default_client_factory(
    config: EmailConfiguration,
) -> ImapClientProtocol:
    client = ImapClient()
    # smtp_password_encrypted doubles as the IMAP password in dev (single
    # mailbox for SMTP + IMAP). Production would split these.
    await client.connect(
        host=config.imap_host or "",
        port=int(config.imap_port or 993),
        user=config.smtp_username,
        password=config.smtp_password_encrypted,
    )
    return client


async def run_ingestor_cycle(
    *,
    session: AsyncSession | None = None,
    client: ImapClientProtocol | None = None,
    config: EmailConfiguration | None = None,
    agent: DeliveryEtaAgent | None = None,
    threshold: float | None = None,
    mailbox: str = "INBOX",
) -> IngestorCycleSummary:
    """Execute one supplier-reply ingestion pass.

    Both ``session`` and ``client`` are dependency-injected to keep this
    function trivially testable. In production the FastAPI lifespan hook
    (T029) calls it without arguments and the function:
      - opens a fresh :class:`AsyncSession`;
      - loads the latest IMAP config from ``email_configurations``;
      - constructs an :class:`ImapClient` and connects via
        :func:`open_imap_client` (close-on-exit guaranteed by ``finally``).

    Returns an :class:`IngestorCycleSummary` for telemetry. Errors per
    message are logged and counted; one bad message never aborts the cycle.
    """
    summary = IngestorCycleSummary()

    if _INGESTOR_LOCK.locked():
        logger.info("run_ingestor_cycle: another cycle in progress; skipping")
        return summary

    async with _INGESTOR_LOCK:
        owns_session = session is None
        if owns_session:
            session_cm = async_session_factory()
            session = await session_cm.__aenter__()
        else:
            session_cm = None

        owns_client = client is None
        if owns_client:
            if config is None:
                config = await _load_imap_config(session)
            if config is None or not config.imap_host:
                logger.info(
                    "run_ingestor_cycle: no IMAP config — skipping (configured ETAs from "
                    "email require email_configurations.imap_host)"
                )
                if owns_session and session_cm is not None:
                    await session_cm.__aexit__(None, None, None)
                return summary
            client = await _default_client_factory(config)

        owns_agent = agent is None
        if owns_agent:
            agent = DeliveryEtaAgent()

        effective_threshold = (
            float(threshold)
            if threshold is not None
            else float(config.eta_auto_apply_threshold) if config is not None else 80.0
        )

        logger.info(
            "EtaIngestor configured: host=%s mailbox=%s threshold=%.2f",
            getattr(config, "imap_host", "(fake)"),
            mailbox,
            effective_threshold,
        )

        try:
            async for raw in _iter_messages(client, mailbox):
                summary.fetched += 1
                try:
                    await _process_one_message(
                        session=session,
                        client=client,
                        raw=raw,
                        agent=agent,
                        threshold=effective_threshold,
                        summary=summary,
                    )
                except Exception as exc:  # noqa: BLE001 — boundary
                    summary.errors.append(f"{raw.uid}: {exc}")
                    logger.exception(
                        "run_ingestor_cycle: message uid=%s failed: %s",
                        raw.uid,
                        exc,
                    )
                    try:
                        await session.rollback()
                    except Exception:
                        pass
        finally:
            if owns_client:
                try:
                    await client.close()
                except Exception:
                    pass
            if owns_agent:
                try:
                    await agent.close()
                except Exception:
                    pass
            if owns_session and session_cm is not None:
                await session_cm.__aexit__(None, None, None)

        logger.info(
            "EtaIngestor cycle complete: fetched=%d persisted=%d duplicates=%d "
            "ignored=%d auto_applied=%d reviews=%d delivered_notes=%d failed=%d errors=%d",
            summary.fetched,
            summary.persisted,
            summary.duplicates,
            summary.ignored,
            summary.auto_applied,
            summary.raised_reviews,
            summary.delivered_notes,
            summary.failed,
            len(summary.errors),
        )
        return summary


async def _iter_messages(
    client: ImapClientProtocol, mailbox: str
) -> AsyncIterator[RawMessage]:
    """Adapter — `fetch_unseen` is an async generator on both ImapClient
    and FakeImapClient.
    """
    async for msg in client.fetch_unseen(mailbox):  # type: ignore[func-returns-value]
        yield msg


async def _process_one_message(
    *,
    session: AsyncSession,
    client: ImapClientProtocol,
    raw: RawMessage,
    agent: DeliveryEtaAgent,
    threshold: float,
    summary: IngestorCycleSummary,
) -> None:
    """One end-to-end pass for a single message; commits on success and
    marks the message as `\\Seen` only after the commit succeeded.
    """
    match = await match_reply_to_order(session, raw)
    reply = await persist_reply(session, raw=raw, match=match)
    if reply is None:
        summary.duplicates += 1
        # Even duplicates must be marked seen — otherwise we re-fetch them forever.
        await session.commit()
        await client.mark_seen(raw.uid)
        return

    summary.persisted += 1

    if reply.processing_status == "ignored":
        summary.ignored += 1
        await session.commit()
        await client.mark_seen(raw.uid)
        return

    result = await process_reply(
        session,
        reply=reply,
        match=match,
        agent=agent,
        threshold=threshold,
    )

    await session.commit()
    await client.mark_seen(raw.uid)

    # Post-commit broadcasts. Order matters (WS contract §1):
    #   raised → timeline.appended → resolved
    outcome = result["outcome"]
    delivery = result.get("delivery")
    timeline_entry = result.get("timeline_entry")
    review = result.get("review")

    if outcome == "applied":
        summary.auto_applied += 1
        if delivery is not None and timeline_entry is not None:
            await publish_timeline_event(delivery=delivery, entry=timeline_entry)
    elif outcome == "review":
        summary.raised_reviews += 1
        if review is not None:
            await publish_eta_review_raised(
                review=serialise_review_summary(review=review, reply=reply),
                candidate_delivery_id=delivery.id if delivery is not None else None,
            )
        if delivery is not None and timeline_entry is not None:
            await publish_timeline_appended(
                delivery_id=delivery.id,
                entry=serialise_timeline_entry(timeline_entry),
                delivery_summary=serialise_delivery_summary(delivery),
            )
    elif outcome == "delivered_note":
        summary.delivered_notes += 1
        if delivery is not None and timeline_entry is not None:
            await publish_timeline_event(delivery=delivery, entry=timeline_entry)
    elif outcome == "failed":
        summary.failed += 1
        if review is not None:
            await publish_eta_review_raised(
                review=serialise_review_summary(review=review, reply=reply),
                candidate_delivery_id=delivery.id if delivery is not None else None,
            )
        if delivery is not None and timeline_entry is not None:
            await publish_timeline_appended(
                delivery_id=delivery.id,
                entry=serialise_timeline_entry(timeline_entry),
                delivery_summary=serialise_delivery_summary(delivery),
            )
