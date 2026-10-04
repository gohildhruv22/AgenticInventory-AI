# Phase 0 — Research: Supplier Delivery ETA Agent

**Feature**: 004-supplier-delivery-eta-agent
**Date**: 2026-05-21

This document resolves every open technical question that surfaced while drafting `plan.md`. There are no remaining `[NEEDS CLARIFICATION]` markers after this phase.

---

## 1. Inbound mail protocol — IMAP poll vs IMAP IDLE vs webhook

- **Decision**: IMAP poll on a fixed cycle (default 5 minutes), implemented with `aioimaplib`, fetching only messages flagged `UNSEEN` and committing the seen flag after successful processing.
- **Rationale**: The existing outbound stack uses an SMTP provider (Gmail in dev) that also exposes IMAP on the same credentials, so no new account or vendor is required. Polling is simpler to operate than IDLE under FastAPI's async loop, satisfies the SC-002 ≤10-minute p95 budget (poll≤5min + agent≤5s + WS≤250ms ≪ 10min), and degrades gracefully if the mailbox is briefly unreachable. Webhooks were rejected because they require provider-specific configuration (Gmail Pub/Sub, Microsoft Graph subscriptions) that varies per customer deployment.
- **Alternatives considered**:
  - *IMAP IDLE*: lower latency but long-lived sockets are fragile under container restarts and Azure App Service idle timeouts.
  - *Provider webhooks (Gmail Pub/Sub / Microsoft Graph)*: tightly couples deployment to a single provider; violates the "portable, Azure-ready" constraint (X).
  - *POP3*: no folder model, no `UNSEEN` flag, harder to recover from partial failures.

## 2. Background scheduling inside FastAPI

- **Decision**: Run the ingestor as a single `asyncio.create_task` started from the existing `lifespan` context in `app/main.py`, guarded by a per-process advisory lock so two replicas cannot poll the same mailbox concurrently.
- **Rationale**: The project already uses lifespan-managed background tasks (the autonomous pipeline tick). Reusing the same pattern keeps the deployment model unchanged. An advisory lock (DB-row-based `SELECT … FOR UPDATE SKIP LOCKED` on a singleton row in `email_config`) generalises cleanly to PostgreSQL when Azure switchover happens.
- **Alternatives considered**:
  - *APScheduler / Celery beat*: introduces a new dependency and a broker requirement, violating X.
  - *Cron + one-shot CLI*: external scheduling surface; harder to test; loses lifespan-bound graceful shutdown.

## 3. Order-to-message matching

- **Decision**: Two-stage match. (1) Regex-scan the subject and first 4 KB of the body for the canonical PO identifier `Order #<uuid>` (already emitted by `agents/supplier_email.py`) and for the short prefix form `PO <UUID8>` (already used by admin/rationale emails). (2) If no identifier hit, fall back to "most recent open order to the same supplier email address within the last 30 days", but only as a *candidate* — never as an auto-applied match. Candidate matches become review-queue items.
- **Rationale**: Both identifier formats are produced by the platform itself and are stable. The 30-day sender-based fallback covers the common "supplier replies but trims the subject" case while keeping FR-002 honest — ambiguous matches go to humans, never silently to the wrong delivery.
- **Alternatives considered**:
  - *RFC-5322 `In-Reply-To` / `References` threading*: ideal but not always preserved by suppliers (especially mobile clients and CRMs). Kept as a tertiary signal that boosts confidence when present but is not required.
  - *LLM-based order matching*: rejected because matching is deterministic and cheap; using LLM here would burn tokens and add latency for zero accuracy gain.

## 4. Dedupe key and idempotency

- **Decision**: Store the RFC-5322 `Message-ID` header on `supplier_replies` with a `UNIQUE` constraint. Synthesise a fallback key `sha256(from + date + subject + first-256-chars-of-body)` for the (rare) message without a Message-ID. Ingestion attempts an `INSERT … ON CONFLICT DO NOTHING`; conflict → already processed → skip silently.
- **Rationale**: Satisfies FR-007 deterministically. Survives mail-server redelivery, container restarts, and replays from a backup mailbox. The synthesised fallback is content-derived so the same message always hashes to the same key.
- **Alternatives considered**:
  - *Trust IMAP UID*: UIDs are per-folder; if the mailbox is reorganised the same message gets a new UID and would be reprocessed. Rejected.

## 5. Date extraction strategy (LLM + deterministic normaliser)

- **Decision**: The Groq agent returns an ISO-8601 string in its JSON response and a verbatim excerpt of the source phrase. After the response is received, `dateparser.parse(iso_string)` is called as a *validator* — if it returns `None`, the extraction is downgraded to `unclear` and routed to review. For free-text excerpts like "next Tuesday", the agent is instructed to resolve them to an absolute date relative to the email's `Date` header.
- **Rationale**: Keeps constitution II honest — the LLM does the reasoning, `dateparser` only validates the output shape. Removes a whole class of agent hallucinations where a plausible-looking date string is not actually parseable.
- **Alternatives considered**:
  - *Pure regex/dateparser*: cannot handle phrases like "shipping after the long weekend" or distinguish ship-date from delivery-date.
  - *Pure LLM with no validator*: increases the rate of well-formed-looking but nonsensical dates landing in production.

## 6. Confidence threshold for auto-apply vs review

- **Decision**: Default threshold 0.80. Stored in `email_config.eta_auto_apply_threshold`, mutable from the existing Settings page. Three terminal categories always go to review regardless of confidence: `intent=cancel`, `intent=delay` with no parseable new date, and any `parsed_date` in the past relative to `now()`.
- **Rationale**: Matches the FR-004 / FR-011 requirements and gives operators a single knob to tighten or relax automation as trust builds. The default of 0.80 mirrors the threshold used by the existing `decision_manager` agent for auto-approval, keeping operator mental model consistent.

## 7. AutoGen agent design

- **Decision**: A single-turn `AssistantAgent` (no team), system prompt grounded in the same rules-style format used by `decision_manager` and `demand_forecast` agents. Output schema validated by a pydantic model `EtaExtraction { intent, parsed_date, confidence, excerpt, reasoning }`. Invalid JSON → retry once with a strict-JSON reminder → on second failure, mark the reply as `failed` and surface in the review queue.
- **Rationale**: Mirrors the established agent style in the codebase (cheap to read, easy to unit-test with recorded fixtures). Single-turn keeps token cost predictable.

## 8. WebSocket event surface

- **Decision**: Add one new event type `delivery.timeline.appended` with payload `{ delivery_id, entry: <DeliveryTimelineEntryResponse> }`. The existing client-side WS dispatcher already keys on `event` and invalidates the relevant react-query keys; the new event invalidates `queryKeys.deliveries.timeline(id)` and `queryKeys.deliveries.list`.
- **Rationale**: Smallest surface change. Re-uses the existing dispatcher; no new socket, no new auth path.

## 9. Reversibility / undo

- **Decision**: Every call to `apply_eta_update()` writes one row to the existing `action_logs` table with `action_type='delivery.eta_update'` and a payload containing `{ delivery_id, before: {expected_delivery_at, current_stage}, after: {...}, source_reply_id }`. The existing `undo_rollback` agent already handles a generic "restore before-state" rollback; the new `action_type` plugs into that machinery with no agent change.
- **Rationale**: Satisfies constitution III without inventing a parallel reversibility mechanism.

## 10. Secrets handling for IMAP credentials

- **Decision**: Reuse the existing `email_config` row (singleton). Add two optional columns `imap_host` and `imap_port`; the username/password already stored for SMTP are reused. Credentials are masked in API responses by the existing settings serializer.
- **Rationale**: Same provider, same identity — separate credentials would be operational overhead with zero security benefit. Existing masking already covers the new path.

## 11. Frontend page layout

- **Decision**: Extend the existing `Deliveries.tsx`. Each row gets an "Updates" affordance — a chevron with a small badge showing the count of timeline entries since last viewed, and a red dot if there is an unresolved review item on that delivery. Click expands an inline `<DeliveryTimeline />`. A separate `Review Queue` page is added to the existing sidebar (icon: `MailCheck`), surfacing all unmatched / low-confidence items across deliveries.
- **Rationale**: Keeps the primary task ("see what's late and why") one click away while still giving operators a global review surface.

## 12. Testing strategy

- **Decision**:
  - Agent unit tests: 12 recorded fixture emails covering each `intent` × confidence band. Run against the agent with the Groq client replaced by a deterministic stub that replays canned JSON.
  - Ingestor integration tests: in-memory `FakeImapClient` returning a configurable list of `(headers, body)` tuples. Drives the full ingestor cycle against a real test database (SQLite).
  - Contract tests: pytest hits the FastAPI test client against the OpenAPI definitions in `contracts/`.
  - Undo test: place an ETA update, fire the undo endpoint, assert `expected_delivery_at` and `current_stage` are restored byte-for-byte.
  - Frontend: render-tests for `DeliveryTimeline` (variant per intent) and `ReviewItemCard` (variant per resolution state).
- **Rationale**: No live LLM, no live IMAP in CI. Fully deterministic.

---

**Phase 0 status**: COMPLETE. All Technical Context fields are resolved; no `NEEDS CLARIFICATION` remaining.
