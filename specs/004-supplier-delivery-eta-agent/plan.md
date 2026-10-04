# Implementation Plan: Supplier Delivery ETA Agent

**Branch**: `004-supplier-delivery-eta-agent` | **Date**: 2026-05-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-supplier-delivery-eta-agent/spec.md`

## Summary

Add an autonomous inbound-email path to AgenticInventory AI. A scheduled ingestor polls the same mailbox used to send purchase orders, deduplicates messages, matches each one to an existing `SupplierOrder` (and therefore `Delivery`), and hands the body to a new AutoGen agent — the **DeliveryEtaAgent** — backed by Groq. The agent returns a structured extraction (`intent` ∈ {confirm, delay, cancel, acknowledge, unclear}, `parsed_date`, `confidence`, verbatim `excerpt`, `reasoning`). High-confidence confirmations update the `Delivery`'s `expected_delivery_at` and `current_stage`, push an entry into `stage_history`, and broadcast a WebSocket event. Low-confidence or negative-intent results land in a new **ETA review queue** that admins resolve from the existing Deliveries page. All mutations route through the existing `ActionLog` so undo is preserved.

The technical approach reuses every existing primitive — AutoGen agents, Groq client tiers, the SQLAlchemy async session, the WebSocket gateway, and the React Deliveries page — and adds 3 new tables, 1 new agent, 1 background service, and 2 new API surfaces (`/api/v1/eta-reviews/*` plus a delivery-timeline expansion on the existing `/api/v1/deliveries`).

## Technical Context

**Language/Version**: Python 3.14 (backend), TypeScript 5.x + React 18 (frontend).

**Primary Dependencies**:
- Backend: FastAPI, SQLAlchemy 2.x async, pydantic v2.13, Microsoft AutoGen (`autogen-agentchat` + `autogen-ext` Groq client), `aioimaplib` for IMAP, `mail-parser` for MIME body extraction, `dateparser` for deterministic date normalisation, existing `agenticinventory.email.smtp` module reused for credentials lookup.
- Frontend: React + Vite + Tailwind, framer-motion, lucide-react, @tanstack/react-query (already present).

**Storage**: SQLite via existing `backend/agenticinventory.db` (Azure target: PostgreSQL; schema portable). New tables: `supplier_replies`, `delivery_timeline_entries`, `eta_review_items`. Extension to existing `deliveries` table: nullable `has_pending_review` boolean, `current_stage` accepts new values `confirmed` and `at_risk`.

**Testing**: pytest with `pytest-asyncio`; httpx `AsyncClient` for API contract tests; Vitest + Testing Library for frontend; fake-IMAP fixture (in-memory class) for ingestor tests; Groq-agent tests use recorded fixture responses — no live LLM in CI.

**Target Platform**: Linux container (Azure App Service / Container Apps ready), modern evergreen browsers.

**Project Type**: Web application — extends existing `backend/` (FastAPI) + `frontend/` (Vite/React) layout.

**Performance Goals**:
- Mailbox-to-UI latency p95 ≤ 10 minutes (SC-002) — ingestor poll interval ≤ 5 min, agent extraction ≤ 5 s p95.
- A single ingestor cycle MUST process ≥ 50 messages without blocking the event loop.
- WebSocket broadcast of a new timeline entry ≤ 250 ms from DB commit.

**Constraints**:
- All AI reasoning routes through the Groq-backed AutoGen client (constitution II).
- Every delivery mutation MUST be reversible via the existing `ActionLog` + `undo_rollback` agent (constitution III).
- No polling-based UI refresh — timeline updates use the existing `/ws` channel (constitution V).
- Inbound mailbox credentials live in the existing settings table; no plaintext secrets in code.
- Same-message dedupe key MUST be the RFC-5322 `Message-ID` header; ingestion is idempotent.

**Scale/Scope**:
- Initial: ≤ 500 supplier replies/day, ≤ 50 concurrent open deliveries.
- 3 new DB tables, 1 new agent, 1 new background scheduler task, 2 API surfaces, 1 new frontend page + 3 components.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. AutoGen-only orchestration | PASS | New `DeliveryEtaAgent` is an `autogen_agentchat.agents.AssistantAgent` built via the existing `agenticinventory.agents` factory. No alternative orchestrator. |
| II. Groq-exclusive LLM | PASS | Agent uses the existing primary-tier Groq client (`llama-3.3-70b-versatile`). `dateparser` is used only to normalise strings the LLM already extracted — not for inference. |
| III. AI explainability & reversibility | PASS | Every agent response carries `reasoning`, `confidence`, `intent`, `excerpt`. Every `Delivery` mutation creates an `action_logs` row so the existing undo flow restores `expected_delivery_at` and `current_stage`. |
| IV. UI/UX excellence | PASS (with documented carve-out — see Complexity Tracking) | Timeline UI follows the current shipped light theme (spec 002 overhaul). Animations, micro-interactions, and component reuse from spec 003 satisfy the intent of the principle. |
| V. Real-time WebSockets | PASS | Each `delivery_timeline_entry` commit publishes `delivery.timeline.appended` on the existing WS channel. No new polling. |
| VI. External intelligence APIs | N/A | Feature consumes inbound email, not external market data. |
| VII. Delivery simulation | PASS | Simulation harness untouched. Ingestor and simulator both write into `delivery_timeline_entries`; the timeline UI renders both sources uniformly. |
| VIII. Reporting & analytics | PASS | Daily KPI report gains two new counts (auto-applied ETAs, pending reviews). No new dashboard surface required. |
| IX. Production-grade email automation | PASS | Reuses the SMTP-grade `email_config` + retry logic. IMAP path adds the same 3-attempt retry-with-backoff pattern. |
| X. Scalable clean architecture & Azure-ready | PASS | New service module `app/services/eta_ingestor.py` is stateless and idempotent; mailbox credentials are externalised; runs equally under SQLite (dev) and PostgreSQL (Azure). |

**Initial gate result**: PASS. One documented carve-out (IV) — no blocker.

**Post-design re-check** (after Phase 1): PASS. Contracts and data model introduce no new orchestrators, providers, or polling paths; every mutation hooks the existing `action_logs` writer; every event flows through the existing WS dispatcher.

## Project Structure

### Documentation (this feature)

```text
specs/004-supplier-delivery-eta-agent/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── eta-reviews.openapi.yaml
│   ├── deliveries-timeline.openapi.yaml
│   └── websocket-events.md
├── checklists/
│   └── requirements.md  # Created during /speckit.specify
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── agents/
│   │   └── delivery_eta.py              # NEW — AutoGen agent: parses supplier replies
│   ├── api/
│   │   ├── deliveries.py                # EXTEND — add /deliveries/{id}/timeline
│   │   └── eta_reviews.py               # NEW — list / resolve review items
│   ├── email/
│   │   └── imap.py                      # NEW — async IMAP client (aioimaplib wrapper)
│   ├── models/
│   │   ├── supplier_reply.py            # NEW
│   │   ├── delivery_timeline_entry.py   # NEW
│   │   ├── eta_review_item.py           # NEW
│   │   └── delivery.py                  # EXTEND — has_pending_review, new stages
│   ├── schemas/
│   │   ├── delivery.py                  # EXTEND — timeline + has_pending_review
│   │   ├── eta_review.py                # NEW
│   │   └── supplier_reply.py            # NEW
│   ├── services/
│   │   ├── eta_ingestor.py              # NEW — orchestrates poll → agent → mutate
│   │   ├── delivery.py                  # EXTEND — apply_eta_update() helper
│   │   └── eta_review.py                # NEW — review-queue service
│   ├── websocket/
│   │   └── events.py                    # EXTEND — delivery.timeline.appended event
│   └── main.py                          # EXTEND — register router + start ingestor task
└── tests/
    ├── contract/
    │   ├── test_eta_reviews_api.py          # NEW
    │   └── test_deliveries_timeline.py      # NEW
    ├── integration/
    │   ├── test_eta_ingestor.py             # NEW — fake-IMAP + recorded agent fixtures
    │   └── test_eta_undo.py                 # NEW — verify ActionLog reversibility
    └── unit/
        └── test_delivery_eta_agent.py       # NEW — agent parses fixture emails

frontend/
├── src/
│   ├── pages/
│   │   ├── Deliveries.tsx               # EXTEND — expandable timeline + review badge
│   │   └── ReviewQueue.tsx              # NEW
│   ├── components/deliveries/
│   │   ├── DeliveryTimeline.tsx         # NEW
│   │   ├── ReviewItemCard.tsx           # NEW
│   │   └── EtaUpdateBadge.tsx           # NEW
│   ├── hooks/
│   │   ├── useDeliveryTimeline.ts       # NEW
│   │   └── useEtaReviews.ts             # NEW
│   └── lib/
│       └── queryKeys.ts                 # EXTEND — etaReviews, deliveryTimeline
└── tests/components/deliveries/
    ├── DeliveryTimeline.test.tsx        # NEW
    └── ReviewItemCard.test.tsx          # NEW
```

**Structure Decision**: Extend the existing two-project web layout (`backend/` + `frontend/`). The feature adds 3 backend models, 1 agent, 2 service modules, 1 IMAP wrapper, 2 router surfaces, and 1 new frontend page + 3 components. No new top-level project, no new framework, no new datastore.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Light-theme UI deviates from constitution IV's dark-theme clause | The shipped application was migrated to a light theme under spec 002 (white-theme-overhaul) and the Deliveries page already follows that system. | Forcing a dark island inside a light page would harm the "UX excellence" goal that the same principle elevates as highest priority. Resolution: align with the active app theme; propose a constitution amendment under a separate change. |
