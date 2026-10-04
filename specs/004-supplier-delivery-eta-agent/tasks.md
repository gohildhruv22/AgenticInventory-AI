# Tasks: Supplier Delivery ETA Agent

**Feature**: 004-supplier-delivery-eta-agent
**Branch**: `004-supplier-delivery-eta-agent`
**Input**: Design documents from `/specs/004-supplier-delivery-eta-agent/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/eta-reviews.openapi.yaml, contracts/deliveries-timeline.openapi.yaml, contracts/websocket-events.md, quickstart.md

**Tests**: INCLUDED — contract tests for both OpenAPI specs and integration tests for the ingest → parse → apply pipeline are required by the user request and constitution III (reversibility must be proven).

**Organization**: Tasks are grouped by user story so each story (US1, US2, US3) can be implemented, tested, and demoed independently. Foundational phase is required before any user story can begin.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Task can run in parallel with other [P] tasks (different files, no in-flight dependency on incomplete tasks).
- **[Story]**: User story tag — US1 = automatic ETA capture, US2 = timeline UI, US3 = low-confidence review queue. Setup, Foundational, and Polish phases carry no story tag.

## Path Conventions

- Backend: `backend/app/...`, tests under `backend/tests/...` (create the tree if it does not exist).
- Frontend: `frontend/src/...`, tests under `frontend/tests/...`.
- Alembic migrations: `backend/migrations/versions/...`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Pin new Python/JS dependencies and prepare the test scaffolding the rest of the phases assume exists.

- [x] T001 Add backend runtime dependencies `aioimaplib`, `mail-parser`, `dateparser` to [backend/requirements.txt](backend/requirements.txt) and [backend/pyproject.toml](backend/pyproject.toml); pin to versions compatible with Python 3.14.
- [x] T002 [P] Create the backend test tree if missing: add empty `__init__.py` files for `backend/tests/`, `backend/tests/contract/`, `backend/tests/integration/`, `backend/tests/unit/`, and configure `pytest-asyncio` mode in [backend/pyproject.toml](backend/pyproject.toml) (`asyncio_mode = "auto"`).
- [x] T003 [P] Add a frontend dev dependency on `@faker-js/faker` (only if missing) for timeline/review fixture generation in component tests, updating [frontend/package.json](frontend/package.json).
- [x] T004 [P] Create the recorded-fixture directory `backend/tests/fixtures/eta_agent/` with a `README.md` describing the 12 canonical supplier-reply scenarios from research.md §12 (confirm × 3 confidence bands, delay × 2, cancel × 2, acknowledge × 2, unclear × 1, non_english × 1, past_date × 1).

**Checkpoint**: New dependencies install cleanly (`pip install -r backend/requirements.txt`, `npm install` in frontend) and the test directory tree is discoverable by pytest.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database schema, ORM models, pydantic schemas, the AutoGen agent contract, and the IMAP wrapper. Nothing in US1/US2/US3 can compile without these. Per constitution II, the agent here only defines the contract and Groq wiring; the ingest-loop that calls it is in US1.

**⚠️ CRITICAL**: All US1/US2/US3 tasks depend on this phase completing.

### Database & migrations

- [x] T005 Create Alembic migration `backend/migrations/versions/2026_05_xx_eta_agent_init.py` per data-model.md §6: create tables `supplier_replies`, `delivery_timeline_entries`, `eta_review_items` with all columns, indexes, and FKs; `ALTER TABLE deliveries ADD COLUMN has_pending_review BOOLEAN NOT NULL DEFAULT FALSE` (indexed); `ALTER TABLE email_config ADD COLUMN imap_host VARCHAR(255) NULL, imap_port INTEGER NULL, eta_auto_apply_threshold NUMERIC(5,2) NOT NULL DEFAULT 80.00`; include the legacy `stage_history` → `delivery_timeline_entries` backfill (`actor_type='simulator'`).

### ORM models (parallel — different files)

- [x] T006 [P] Create `SupplierReply` ORM model in [backend/app/models/supplier_reply.py](backend/app/models/supplier_reply.py) matching data-model.md §1, including the `processing_status` transition validator (`ValueError` on illegal transitions).
- [x] T007 [P] Create `DeliveryTimelineEntry` ORM model in [backend/app/models/delivery_timeline_entry.py](backend/app/models/delivery_timeline_entry.py) matching data-model.md §2, with the append-only invariant enforced via a service-level guard (no `__table_args__` updates on existing rows).
- [x] T008 [P] Create `EtaReviewItem` ORM model in [backend/app/models/eta_review_item.py](backend/app/models/eta_review_item.py) matching data-model.md §3, including the `resolution_state` transition validator.
- [x] T009 Extend [backend/app/models/delivery.py](backend/app/models/delivery.py) with the `has_pending_review` column, document the new allowed `current_stage` values (`confirmed`, `at_risk`) in the docstring, and add the `timeline_entries` and `pending_review_items` relationship back-refs to the new models from T006–T008.
- [x] T010 Extend [backend/app/models/email_config.py](backend/app/models/email_config.py) with the new `imap_host`, `imap_port`, `eta_auto_apply_threshold` columns and update its `__repr__` / serializer.
- [x] T011 Register the three new model modules in [backend/app/models/\_\_init\_\_.py](backend/app/models/__init__.py) so Alembic autogenerate picks them up.

### Pydantic schemas (parallel — different files)

- [x] T012 [P] Create `EtaExtraction` pydantic model (intent, parsed_date, confidence, excerpt, reasoning) and response/request schemas for the review queue in [backend/app/schemas/eta_review.py](backend/app/schemas/eta_review.py), matching `contracts/eta-reviews.openapi.yaml` (`EtaReviewSummary`, `EtaReviewDetailResponse`, `EtaReviewListResponse`, `EtaReviewCorrectRequest`, `ErrorResponse`).
- [x] T013 [P] Create `SupplierReplyRead` schema in [backend/app/schemas/supplier_reply.py](backend/app/schemas/supplier_reply.py) for nested embedding inside review-item detail responses.
- [x] T014 [P] Extend [backend/app/schemas/delivery.py](backend/app/schemas/delivery.py) to add `DeliveryTimelineEntry`, the `has_pending_review` and `latest_timeline_entry` fields on the existing `DeliveryResponse`, and a `DeliveryTimelineResponse` envelope per `contracts/deliveries-timeline.openapi.yaml`.

### Agent contract & Groq wiring

- [x] T015 Implement the `DeliveryEtaAgent` AutoGen `AssistantAgent` factory in [backend/app/agents/delivery_eta.py](backend/app/agents/delivery_eta.py): grounded system prompt per research.md §7, strict JSON output validated against `EtaExtraction`, MUST call the existing `app.agents.config.invoke_with_retries` and MUST raise `LLMAgentError` on parse failure (no rule-engine fallback — constitution II). Include a single-retry "strict-JSON reminder" before failing.
- [x] T016 [P] Implement the deterministic post-LLM date validator: `validate_extraction(extraction, message_received_at) -> EtaExtraction` in the same module, calling `dateparser.parse` on the agent-returned ISO string per research.md §5; if `None`, downgrade to `intent='unclear'` and lower confidence.

### IMAP wrapper

- [x] T017 Implement the async IMAP client in [backend/app/email/imap.py](backend/app/email/imap.py) wrapping `aioimaplib`: `connect(host, port, user, password)`, `fetch_unseen() -> AsyncIterator[RawMessage]`, `mark_seen(uid)`, with the 3-attempt retry-with-backoff pattern (constitution IX), connection lifecycle managed by an async context manager, and a `FakeImapClient` protocol-equivalent stub colocated in `backend/app/email/_imap_fake.py` for tests.

### Cross-cutting

- [x] T018 Extend [backend/app/websocket/events.py](backend/app/websocket/events.py) to register the three new event types (`delivery.timeline.appended`, `eta_review.raised`, `eta_review.resolved`) per `contracts/websocket-events.md`, exposing typed publisher helpers `publish_timeline_appended(...)`, `publish_eta_review_raised(...)`, `publish_eta_review_resolved(...)`.
- [x] T019 Run `alembic upgrade head` against the local SQLite DB and verify the backfill produced one `delivery_timeline_entries` row per legacy `stage_history` entry (smoke step — fix migration if mismatched).

**Checkpoint**: Migration applies cleanly, models import without circular errors, pydantic schemas validate the canonical fixtures, the agent factory loads and a happy-path canned JSON returns a valid `EtaExtraction`, and the IMAP wrapper passes its own connect/disconnect smoke test against `FakeImapClient`. User stories can now begin in parallel.

---

## Phase 3: User Story 1 — Automatic ETA capture from supplier reply (Priority: P1) 🎯 MVP

**Goal**: A scheduled ingestor polls the mailbox, matches each new reply to a `Delivery`, invokes the `DeliveryEtaAgent`, and — when confidence ≥ threshold and intent is `confirm`/`acknowledge` — updates `expected_delivery_at`, advances `current_stage`, writes a `delivery_timeline_entries` row, writes an `action_logs` row for undo, and broadcasts `delivery.timeline.appended`. Replies that match an already-`delivered` order produce only an informational `note` entry.

**Independent Test**: Run `pytest backend/tests/integration/test_eta_ingestor.py -k test_high_confidence_confirm_auto_applies`. Drives the full ingestor cycle against `FakeImapClient` + a stubbed Groq client; asserts the matching delivery's `expected_delivery_at`, `current_stage='confirmed'`, the timeline row, the action_log row, and the WS broadcast.

### Tests for User Story 1 (write FIRST, ensure they FAIL)

- [x] T020 [P] [US1] Unit test the agent against all 12 recorded fixtures in [backend/tests/unit/test_delivery_eta_agent.py](backend/tests/unit/test_delivery_eta_agent.py): for each fixture, the stubbed Groq client returns canned JSON, the agent + validator yield the expected `intent`/`confidence`/`parsed_date`/`excerpt`. Includes the "invalid JSON → one retry → `LLMAgentError`" path.
- [x] T021 [P] [US1] Integration test the full ingest pipeline in [backend/tests/integration/test_eta_ingestor.py](backend/tests/integration/test_eta_ingestor.py) covering: (a) high-confidence confirm auto-applies, (b) duplicate `Message-ID` ingested twice produces exactly one timeline row (FR-007), (c) `Auto-Submitted: auto-replied` headers are ignored (FR-008), (d) reply to an already-`delivered` order writes a `note` and does NOT mutate the date (FR-006), (e) IMAP raises once then succeeds — the next cycle still processes the message (FR-015), (f) date-range `"between June 5 and June 9"` selects June 9 (FR-014).
- [x] T022 [P] [US1] Integration test reversibility in [backend/tests/integration/test_eta_undo.py](backend/tests/integration/test_eta_undo.py): apply an ETA update, hit the existing undo endpoint with the new `action_type='delivery.eta_update'`, assert `expected_delivery_at` and `current_stage` are restored byte-for-byte and a `manual_override` timeline entry is appended (constitution III).

### Implementation for User Story 1

- [x] T023 [P] [US1] Implement the order-to-message matcher `match_reply_to_order(reply, session) -> MatchResult` in [backend/app/services/eta_ingestor.py](backend/app/services/eta_ingestor.py) per research.md §3: regex for `Order #<uuid>` and `PO <UUID8>` in subject + first 4 KB of body; fallback "most-recent open order from the same sender in 30d" → returned as a `candidate` (NOT auto-applied); `In-Reply-To`/`References` headers boost confidence but are not required.
- [x] T024 [US1] In the same [backend/app/services/eta_ingestor.py](backend/app/services/eta_ingestor.py), implement `persist_reply(raw_message, match, session)` doing `INSERT … ON CONFLICT DO NOTHING` on `supplier_replies.message_id` with the sha256 fallback key per research.md §4; classifies auto-submitted/postmaster senders as `processing_status='ignored'` per FR-008.
- [x] T025 [US1] In [backend/app/services/eta_ingestor.py](backend/app/services/eta_ingestor.py), implement `process_reply(reply, session)`: load matched delivery, call `DeliveryEtaAgent` via `invoke_with_retries`, run the validator, then dispatch to `apply_eta_update(...)` (high-conf confirm/acknowledge to a non-delivered order) or `raise_review_item(...)` (any of the six `raised_reason` values from data-model.md §3). Skip the agent call entirely when the matched delivery's `current_stage='delivered'` and write a `note` timeline entry instead (FR-006). The whole function MUST raise `LLMAgentError` upward without falling back to a rule engine.
- [x] T026 [US1] Implement the `apply_eta_update(delivery, extraction, reply, session)` helper in [backend/app/services/delivery.py](backend/app/services/delivery.py) (new file — follow the existing `_service.py` naming convention if preferred during implementation): updates `expected_delivery_at` and `current_stage` (`pending`→`confirmed` or `confirmed`→`confirmed` for revisions), appends a `delivery_timeline_entries` row with `event_type ∈ {eta_confirmed, eta_revised}`, writes one `action_logs` row of `action_type='delivery.eta_update'` with `{before, after, source_reply_id}` payload per research.md §9, and calls `publish_timeline_appended(...)` (T018) AFTER the DB commit.
- [x] T027 [US1] Implement `raise_review_item(reply, extraction, candidate, session)` in [backend/app/services/eta_review.py](backend/app/services/eta_review.py): inserts an `eta_review_items` row with the correct `raised_reason`, sets `has_pending_review=true` on the candidate delivery (if any), writes a corresponding `acknowledged` / `at_risk` timeline entry (the only mutation allowed before admin action — FR-011), and publishes `eta_review.raised` BEFORE `delivery.timeline.appended` per the ordering guarantee in `contracts/websocket-events.md`.
- [x] T028 [US1] Implement the scheduled ingestor entrypoint `run_ingestor_cycle(...)` in [backend/app/services/eta_ingestor.py](backend/app/services/eta_ingestor.py): loads IMAP config from `email_config`, acquires the advisory lock (`SELECT … FOR UPDATE SKIP LOCKED` on the singleton settings row — research.md §2), iterates `fetch_unseen()`, calls `persist_reply` + `process_reply` per message, commits the seen flag only on success; logs `EtaIngestor configured: …` and per-cycle summary.
- [x] T029 [US1] Register the ingestor as an `asyncio.create_task` started from the existing FastAPI `lifespan` in [backend/app/main.py](backend/app/main.py), guarded by a config flag (e.g., `settings.eta_ingestor_enabled`) so tests can disable it; ensure graceful shutdown joins the task.
- [x] T030 [US1] Extend the existing pipeline tick in [backend/app/services/monitoring_service.py](backend/app/services/monitoring_service.py) to optionally invoke one `run_ingestor_cycle()` per tick (off by default in test envs) so the existing manual `POST /api/v1/pipeline/tick` endpoint can drive an ingest deterministically for the quickstart smoke flow.
- [x] T031 [US1] Extend the daily KPI report builder in [backend/app/services/report_service.py](backend/app/services/report_service.py) to include the two new counts (`auto_applied_eta_count`, `pending_review_count`) per plan.md constitution check VIII; expose them in the existing [backend/app/schemas/report.py](backend/app/schemas/report.py) `KpiReport` schema.

**Checkpoint**: Tests T020–T022 pass. Quickstart steps 1, 3, 4, 5, and 8 succeed end-to-end. US2 and US3 may now begin in parallel.

---

## Phase 4: User Story 2 — Delivery timeline visible to admin (Priority: P2)

**Goal**: Each Deliveries-page row shows the current stage, current expected date, and an expandable, chronological timeline (with supplier excerpts and timestamps) of every agent- and admin-driven update. The list also reflects `has_pending_review` and updates live over WebSocket without polling.

**Independent Test**: With mixed deliveries (one auto-applied via US1, one manually edited, one untouched), open the Deliveries page; each row shows the correct stage and expected date; expanding a row reveals an ordered timeline with the supplier excerpt; a delivery with two agent revisions shows the most-recent date in the row and both updates in the timeline. Live test: trigger a new ingestor cycle in another tab and confirm the open timeline grows without refresh.

### Tests for User Story 2 (write FIRST, ensure they FAIL)

- [x] T032 [P] [US2] Contract test against `contracts/deliveries-timeline.openapi.yaml` in [backend/tests/contract/test_deliveries_timeline.py](backend/tests/contract/test_deliveries_timeline.py): hit `GET /api/v1/deliveries/{id}/timeline` with seeded entries, assert response matches the OpenAPI schema (entries ordered by `occurred_at`, `since` filter respected, `limit` capped at 200, 404 on unknown delivery, 401 without session).
- [x] T033 [P] [US2] Contract test the augmented `DeliveryResponse` in the same file: assert the existing `GET /api/v1/deliveries` and `GET /api/v1/deliveries/{id}` now return `has_pending_review: boolean` and `latest_timeline_entry: DeliveryTimelineEntry | null` per the `DeliveryResponseAdditions` schema, and pre-existing fields are unchanged.
- [x] T034 [P] [US2] Frontend component test in [frontend/tests/components/deliveries/DeliveryTimeline.test.tsx](frontend/tests/components/deliveries/DeliveryTimeline.test.tsx): renders one variant per `event_type` (eta_confirmed, eta_revised, acknowledged, at_risk, delivered, manual_override, note); asserts the supplier excerpt and parsed date are visible for confirmed/revised entries; asserts entries render in reverse-chronological order.

### Implementation for User Story 2

- [x] T035 [P] [US2] Implement `list_timeline(delivery_id, since, limit, session)` in [backend/app/services/delivery.py](backend/app/services/delivery.py): query `delivery_timeline_entries` ordered by `occurred_at DESC`, apply the `since` and `limit` filters, return the pydantic `DeliveryTimelineResponse` envelope.
- [x] T036 [US2] Add `GET /api/v1/deliveries/{delivery_id}/timeline` route to [backend/app/api/deliveries.py](backend/app/api/deliveries.py) wired to T035; enforce the existing admin-session dependency; return 404 when the delivery does not exist.
- [x] T037 [US2] In the same [backend/app/api/deliveries.py](backend/app/api/deliveries.py), extend the existing list and detail endpoints to populate `has_pending_review` (read from the column added in T009) and `latest_timeline_entry` (one extra correlated subquery, single round-trip).
- [x] T038 [P] [US2] Create the React Query key helpers `queryKeys.deliveries.timeline(id)` and `queryKeys.etaReviews.list(state)` in `frontend/src/lib/queryKeys.ts` (create the file).
- [x] T039 [P] [US2] Create the `useDeliveryTimeline(deliveryId)` hook in `frontend/src/hooks/useDeliveryTimeline.ts` calling the new endpoint and keyed by T038; include the `since` cursor for incremental fetch.
- [x] T040 [P] [US2] Implement the `<DeliveryTimeline />` component in `frontend/src/components/deliveries/DeliveryTimeline.tsx`: chronological list using `framer-motion` for expand animation; `lucide-react` icons per `event_type`; shows the parsed date, confidence badge, supplier excerpt (collapsed to 2 lines with "show more"), actor label, and `occurred_at`. Light theme only (constitution carve-out documented in plan.md complexity tracking).
- [x] T041 [P] [US2] Implement the `<EtaUpdateBadge />` component in `frontend/src/components/deliveries/EtaUpdateBadge.tsx`: small pill showing the count of timeline entries since the row was last viewed; red dot variant when `has_pending_review === true`.
- [x] T042 [US2] Extend [frontend/src/pages/Deliveries.tsx](frontend/src/pages/Deliveries.tsx) to render the chevron-affordance per row, mount `<DeliveryTimeline />` on expand, surface `<EtaUpdateBadge />` in the row header, and display `latest_timeline_entry.supplier_excerpt` as a one-line summary under the expected date when present. "Awaiting supplier confirmation" copy MUST appear when `current_stage='pending'` and no timeline entries exist (FR-009 / acceptance scenario 3).
- [ ] T043 [US2] Wire the existing frontend WebSocket dispatcher to handle `delivery.timeline.appended`: on receipt, invalidate `queryKeys.deliveries.timeline(delivery_id)` and `queryKeys.deliveries.list`, and patch the `delivery_summary` snapshot into the cached list row per `contracts/websocket-events.md` §1.

**Checkpoint**: Tests T032–T034 pass. Quickstart step 6 succeeds (timeline grows live, two-revision case shown correctly).

---

## Phase 5: User Story 3 — Low-confidence parses are flagged for human review (Priority: P3)

**Goal**: When the agent's parse is low-confidence, unmatched, ambiguous, negative-intent, past-date, or non-English, no delivery is mutated. An `eta_review_items` row is created, `has_pending_review` is flipped on the candidate delivery (if any), and admins resolve the item from a dedicated Review Queue page. Resolutions update the delivery, append a timeline entry, and mark the review terminal.

**Independent Test**: Send three deliberately ambiguous replies (no order ID, "cannot fulfill", date in past). After the next ingestor cycle: `GET /api/v1/eta-reviews?state=pending` returns three items; no delivery `expected_delivery_at` changed silently; the Deliveries page shows the red-dot indicator on the affected delivery (when matched); the Review Queue page lists the items. Approve one with the agent's proposed date → delivery updates, timeline gains an `eta_confirmed` entry, review moves to `approved`. Correct one with a different date → delivery uses the admin's date. Dismiss the third → delivery unchanged, review marked `dismissed`.

### Tests for User Story 3 (write FIRST, ensure they FAIL)

- [ ] T044 [P] [US3] Contract test against `contracts/eta-reviews.openapi.yaml` in [backend/tests/contract/test_eta_reviews_api.py](backend/tests/contract/test_eta_reviews_api.py): covers `GET /eta-reviews` pagination + state filter, `GET /eta-reviews/{id}`, `POST /eta-reviews/{id}/approve`, `POST /eta-reviews/{id}/correct` (with valid and invalid payloads — 400 on past date / unknown delivery), `POST /eta-reviews/{id}/dismiss`, and the 409 path on a re-resolution attempt. All response shapes validated against the OpenAPI schema.
- [ ] T045 [P] [US3] Integration test in [backend/tests/integration/test_eta_review_resolution.py](backend/tests/integration/test_eta_review_resolution.py): raise a review item via the ingestor (reuse fixtures from T021), then drive each of approve/correct/dismiss through the API and assert (a) the delivery is updated or not as expected, (b) the timeline gains the appropriate entry, (c) `has_pending_review` is recomputed to `false` if no other open reviews reference the delivery, (d) the `eta_review.resolved` WS event is published AFTER `delivery.timeline.appended` per ordering guarantee.
- [ ] T046 [P] [US3] Frontend component test in [frontend/tests/components/deliveries/ReviewItemCard.test.tsx](frontend/tests/components/deliveries/ReviewItemCard.test.tsx): renders one variant per `resolution_state` (pending shows approve/correct/dismiss controls; approved/corrected/dismissed render read-only with the resolving admin and timestamp).

### Implementation for User Story 3

- [x] T047 [P] [US3] Extend [backend/app/services/eta_review.py](backend/app/services/eta_review.py) (started in T027) with `list_reviews(state, page, per_page, session)`, `get_review(review_id, session)`, `approve(review_id, admin_id, session)`, `correct(review_id, payload, admin_id, session)`, `dismiss(review_id, note, admin_id, session)`. Each terminal action: validates the state transition, calls `apply_eta_update` (T026) for approve/correct, writes the `resolution_payload`/`resolved_by`/`resolved_at`, recomputes `has_pending_review` on the affected delivery, publishes `eta_review.resolved` per `contracts/websocket-events.md` §3.
- [x] T048 [US3] Create the FastAPI router [backend/app/api/eta_reviews.py](backend/app/api/eta_reviews.py) exposing the five endpoints from `contracts/eta-reviews.openapi.yaml` wired to T047; reuse the existing admin-session dependency; return 409 on already-resolved items.
- [x] T049 [US3] Register the new router in [backend/app/main.py](backend/app/main.py) under `/api/v1` prefix alongside the existing routers.
- [x] T050 [P] [US3] Create the `useEtaReviews(state)` and `useResolveEtaReview()` hooks in `frontend/src/hooks/useEtaReviews.ts`, keyed via T038 helpers.
- [x] T051 [P] [US3] Implement the `<ReviewItemCard />` component in `frontend/src/components/deliveries/ReviewItemCard.tsx`: shows the supplier excerpt, agent reasoning, agent intent + confidence, candidate delivery summary, three buttons (Approve / Correct → opens a small form with delivery picker + date picker / Dismiss → opens an optional note input). Light theme, framer-motion for state transitions, lucide-react icons.
- [x] T052 [US3] Create the `<ReviewQueue />` page in `frontend/src/pages/ReviewQueue.tsx` listing all `<ReviewItemCard />` items with a state filter tab (`pending` / `approved` / `corrected` / `dismissed` / `all`); pagination using the `per_page` query param.
- [x] T053 [US3] Register the Review Queue route in [frontend/src/router.tsx](frontend/src/router.tsx) and add a sidebar entry with the `MailCheck` icon (per research.md §11) showing a red-dot badge when any `pending` reviews exist (subscribe to the `eta_review.raised`/`eta_review.resolved` WS events).
- [x] T054 [US3] Wire the existing frontend WS dispatcher to handle `eta_review.raised` (invalidate `queryKeys.etaReviews.list({state:'pending'})`, flip `has_pending_review` on the cached delivery, show a toast linking to the Review Queue) and `eta_review.resolved` (invalidate the review caches and the affected delivery's timeline).

**Checkpoint**: Tests T044–T046 pass. Quickstart step 7 succeeds end-to-end. All three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Hardening, documentation, and the full quickstart sweep.

- [x] T055 [P] Add settings UI for the IMAP host/port and `eta_auto_apply_threshold` in the existing Settings → Email page (`frontend/src/pages/Settings.tsx` or equivalent), backed by the columns added in T010.
- [x] T056 [P] Update [README.md](README.md) and [backend/README.md](backend/README.md) (if present) with a short "Supplier ETA Agent" section pointing to `specs/004-supplier-delivery-eta-agent/quickstart.md`.
- [x] T057 [P] Add structured logging coverage check: ensure `EtaIngestor` and the review-resolution service emit log lines tagged with `delivery_id` and `supplier_reply_id` for every mutation (auditability — FR-012).
- [x] T058 [P] Add a `tests/unit/test_eta_review_transitions.py` covering the `resolution_state` and `processing_status` state-machine validators from T006 and T008 exhaustively (every legal and every illegal transition).
- [x] T059 Run the full `quickstart.md` smoke flow end-to-end against a fresh SQLite DB; record any deviation as a follow-up task. All 15 FR rows in the quickstart smoke-script summary table MUST be green.
- [x] T060 Verify success criteria SC-002 (p95 mailbox-to-UI ≤ 10 min) and SC-005 (100% of timeline entries trace back to a source message) using the test fixtures from T021 — assert programmatically.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Phase 1 completion — BLOCKS all user stories.
- **US1 (Phase 3)**: depends on Phase 2. Required for the MVP. Once green, US2 and US3 can start in parallel.
- **US2 (Phase 4)**: depends on Phase 2. Independent of US3. (US2 displays whatever timeline entries exist — agent-written ones from US1, simulator-written ones from the migration backfill, or manually inserted ones in a contract test, so it is genuinely demoable without US3 — but it derives its primary user value once US1 is feeding the table.)
- **US3 (Phase 5)**: depends on Phase 2 and reuses the `raise_review_item` helper from T027 (US1). T047–T054 can begin as soon as T027 lands, even if the rest of US1 is incomplete.
- **Polish (Phase 6)**: depends on US1+US2+US3.

### Within each user story

- Tests are written FIRST (T020–T022 for US1; T032–T034 for US2; T044–T046 for US3) and MUST fail before implementation lands (TDD per user request).
- Models → services → endpoints → UI.
- WebSocket publish call sites are wired in service-layer commits, never in routers.
- Stop at the checkpoint and validate the story independently before moving to the next priority.

### Parallel opportunities

- All Phase 1 tasks except T001 (dependency install must come first) are [P].
- Phase 2 ORM-model tasks T006/T007/T008 and schema tasks T012/T013/T014 are [P] within their respective groups.
- All Phase 3 tests T020/T021/T022 are [P] (different files).
- All Phase 4 frontend tasks T038–T041 are [P] (different files), and contract tests T032/T033/T034 are [P].
- All Phase 5 hooks/components T050/T051 and tests T044/T045/T046 are [P].
- Phase 6 tasks T055–T058 are all [P].

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together (TDD — must fail before implementation):
Task: "Unit test the agent against 12 recorded fixtures in backend/tests/unit/test_delivery_eta_agent.py"
Task: "Integration test the ingest pipeline in backend/tests/integration/test_eta_ingestor.py"
Task: "Integration test undo in backend/tests/integration/test_eta_undo.py"

# Then launch the parallelizable models from Phase 2 (if not already done):
Task: "Create SupplierReply model in backend/app/models/supplier_reply.py"
Task: "Create DeliveryTimelineEntry model in backend/app/models/delivery_timeline_entry.py"
Task: "Create EtaReviewItem model in backend/app/models/eta_review_item.py"
```

---

## Implementation Strategy

### MVP first (US1 only)

1. Phase 1 Setup.
2. Phase 2 Foundational (CRITICAL — blocks every story).
3. Phase 3 User Story 1.
4. **STOP and VALIDATE** with quickstart steps 1, 3, 4, 5, and 8 — agent autonomously updates a delivery and the action is reversible.
5. Demo: a single supplier email moves a delivery from `pending` → `confirmed` with the parsed date, end-to-end.

### Incremental delivery

1. Foundational complete → backend can boot, schema migrated.
2. Add US1 → demo: autonomous ETA update + undo. (MVP — releaseable.)
3. Add US2 → demo: admins see the timeline live in the UI.
4. Add US3 → demo: low-confidence parses surface in the Review Queue and admins resolve them.

### Parallel team strategy

With three developers post-Phase-2:

1. Developer A: US1 (T020–T031). Backend-heavy, owns the ingestor and the agent.
2. Developer B: US2 (T032–T043). Touches both backend (T035–T037) and the bulk of the frontend.
3. Developer C: US3 (T044–T054). Starts after T027 from US1 lands; otherwise fully independent.

---

## Notes

- [P] tasks = different files, no incomplete dependencies.
- [Story] labels are only on Phases 3/4/5 tasks — Phase 1/2/6 tasks carry none.
- Verify tests fail before implementing.
- Every backend mutation MUST write an `action_logs` row (constitution III). Anywhere the codebase mutates `expected_delivery_at` or `current_stage` without an action_log entry is a regression.
- Agent code MUST NOT fall back to deterministic date parsing when the LLM call fails — it MUST raise `LLMAgentError` and let the caller route to the review queue (constitution II).
- Light-theme UI is intentional (plan.md complexity tracking).
- Commit after each task or logical group; do NOT bundle a whole user story into one commit.
