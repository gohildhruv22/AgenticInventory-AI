# Phase 1 — Data Model: Supplier Delivery ETA Agent

**Feature**: 004-supplier-delivery-eta-agent
**Date**: 2026-05-21

This document defines the persistent shape of every entity introduced or extended by this feature. All entities are SQLAlchemy 2.x async mapped classes living under `backend/app/models/`. Field types use the project's existing portable type aliases (`UUIDType`, `JSONType`) so PostgreSQL (Azure target) and SQLite (dev) share one schema.

---

## 1. Entity: `SupplierReply` (NEW)

Table: `supplier_replies`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUIDType` | PK, default uuid4 | Internal identifier. |
| `message_id` | `String(512)` | UNIQUE, NOT NULL | RFC-5322 Message-ID header or content-hash fallback. Dedupe key. |
| `from_address` | `String(255)` | NOT NULL, indexed | Lower-cased sender email. |
| `subject` | `String(998)` | NOT NULL | Raw subject (RFC-5322 max). |
| `received_at` | `DateTime(tz=True)` | NOT NULL, indexed | Date header from the message; falls back to ingestion time if missing. |
| `body_excerpt` | `Text` | NOT NULL | First 8 KB of plain-text body, used by the agent and stored for audit. |
| `raw_headers` | `JSONType` | NOT NULL, default `{}` | Selected headers (`In-Reply-To`, `References`, `Auto-Submitted`, `X-Auto-Response-Suppress`). |
| `matched_order_id` | `UUIDType` | nullable, FK→`supplier_orders.id` | Resolved purchase order, if any. |
| `matched_delivery_id` | `UUIDType` | nullable, FK→`deliveries.id` | Resolved delivery, if any. |
| `processing_status` | `String(20)` | NOT NULL, indexed, default `'new'` | `new` → `parsed` → (`applied` ∣ `in_review` ∣ `ignored` ∣ `failed`). |
| `agent_response` | `JSONType` | nullable | Full `EtaExtraction` JSON returned by the agent. |
| `error_detail` | `Text` | nullable | Populated when `processing_status='failed'`. |
| `created_at` | `DateTime(tz=True)` | NOT NULL, server default `now()` | Ingestion time. |
| `updated_at` | `DateTime(tz=True)` | NOT NULL, on-update `now()` | Last status change. |

**Validation rules**:
- `message_id` MUST be unique; insert path uses `INSERT … ON CONFLICT DO NOTHING`.
- `processing_status` transitions allowed: `new→parsed→applied`, `new→parsed→in_review`, `new→ignored`, `new→failed`, `in_review→applied`, `in_review→ignored`. All other transitions raise `ValueError`.
- Filter at ingest: messages whose `raw_headers.Auto-Submitted` is present and not `no`, or whose `from_address` matches the `mailer-daemon` / `postmaster` patterns, are stored with `processing_status='ignored'` and excluded from agent calls (FR-008).

**Indexes**:
- `(processing_status, created_at)` for the ingestor's "find next batch" query.
- `(matched_delivery_id)` for the delivery-timeline join.

---

## 2. Entity: `DeliveryTimelineEntry` (NEW)

Table: `delivery_timeline_entries`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUIDType` | PK, default uuid4 | |
| `delivery_id` | `UUIDType` | NOT NULL, FK→`deliveries.id`, indexed | Owning delivery. |
| `event_type` | `String(30)` | NOT NULL | One of: `eta_confirmed`, `eta_revised`, `acknowledged`, `at_risk`, `delivered`, `manual_override`, `note`. |
| `occurred_at` | `DateTime(tz=True)` | NOT NULL, indexed | Time the event represents (not always insert time — e.g. a simulator can backfill). |
| `actor_type` | `String(10)` | NOT NULL | `agent`, `admin`, `simulator`. |
| `actor_id` | `String(128)` | nullable | Admin user id when `actor_type='admin'`; agent name otherwise. |
| `parsed_date` | `DateTime(tz=True)` | nullable | Present for `eta_confirmed` / `eta_revised`. |
| `confidence` | `Numeric(5,2)` | nullable | 0.00–100.00 when produced by an agent. |
| `supplier_excerpt` | `Text` | nullable | Verbatim quote that justified the entry. |
| `source_reply_id` | `UUIDType` | nullable, FK→`supplier_replies.id` | Set when produced by the ingestor. |
| `source_review_id` | `UUIDType` | nullable, FK→`eta_review_items.id` | Set when produced by an admin resolution. |
| `note` | `Text` | nullable | Free-text notes from admin overrides. |
| `created_at` | `DateTime(tz=True)` | NOT NULL, server default `now()` | |

**Validation rules**:
- For `event_type ∈ {eta_confirmed, eta_revised}`: `parsed_date IS NOT NULL` and (`source_reply_id IS NOT NULL` OR `source_review_id IS NOT NULL` OR `actor_type='admin'`).
- For `event_type='at_risk'`: `supplier_excerpt IS NOT NULL`.
- For `event_type='note'`: `note IS NOT NULL`.
- Entries are append-only — no UPDATE or DELETE is permitted by application code (enforced in the service layer).

**Indexes**:
- `(delivery_id, occurred_at DESC)` — primary timeline read pattern.
- `(source_reply_id)` — audit trace from a reply back to its effect.

---

## 3. Entity: `EtaReviewItem` (NEW)

Table: `eta_review_items`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUIDType` | PK, default uuid4 | |
| `supplier_reply_id` | `UUIDType` | NOT NULL UNIQUE, FK→`supplier_replies.id` | One open review per reply. |
| `candidate_delivery_id` | `UUIDType` | nullable, FK→`deliveries.id` | The ingestor's best-guess match (may be empty for unmatched messages). |
| `candidate_order_ids` | `JSONType` | NOT NULL, default `[]` | All viable order matches when the primary match is ambiguous. |
| `agent_intent` | `String(20)` | NOT NULL | `confirm`, `delay`, `cancel`, `acknowledge`, `unclear`. |
| `agent_parsed_date` | `DateTime(tz=True)` | nullable | Agent's best-effort date. |
| `agent_confidence` | `Numeric(5,2)` | NOT NULL | 0.00–100.00. |
| `agent_reasoning` | `Text` | NOT NULL | Agent's natural-language justification. |
| `raised_reason` | `String(40)` | NOT NULL | `low_confidence`, `unmatched_order`, `ambiguous_match`, `negative_intent`, `past_date`, `non_english`. |
| `resolution_state` | `String(15)` | NOT NULL, default `'pending'` | `pending`, `approved`, `corrected`, `dismissed`. |
| `resolved_by` | `String(128)` | nullable | Admin user id. |
| `resolution_payload` | `JSONType` | nullable | Admin-supplied override: `{ delivery_id, parsed_date, intent }`. |
| `resolved_at` | `DateTime(tz=True)` | nullable | |
| `raised_at` | `DateTime(tz=True)` | NOT NULL, server default `now()` | |

**Validation rules**:
- `resolution_state` transitions allowed: `pending → {approved, corrected, dismissed}`. Terminal once resolved.
- When transitioning to `approved` or `corrected`, `resolution_payload.delivery_id IS NOT NULL` and `resolution_payload.parsed_date IS NOT NULL`.
- `resolved_by` and `resolved_at` MUST be set together with any non-pending state.

**Indexes**:
- `(resolution_state, raised_at)` — the queue read pattern.
- `(candidate_delivery_id)` — used to compute `delivery.has_pending_review` on the fly.

---

## 4. Entity: `Delivery` (EXTENDED — existing table)

The existing `deliveries` table is extended (no destructive change to existing rows):

| Column | Change | Description |
|---|---|---|
| `current_stage` | Value set extended | Adds `confirmed`, `at_risk` to the existing set (`ordered`, `pending`, `in_transit`, `delivered`, etc.). No schema change to the column itself. |
| `has_pending_review` | NEW, `Boolean`, NOT NULL, default `false`, indexed | Materialised flag synchronised by the `eta_review` service whenever a review item is raised or resolved. Allows the deliveries list query to filter "needs attention" without a join. |

**State transitions for `current_stage` (new edges only)**:

```
pending ──(agent: eta_confirmed, conf ≥ threshold)──▶ confirmed
pending ──(agent: at_risk OR admin override)─────────▶ at_risk
confirmed ──(agent: eta_revised)──▶ confirmed         (date updated, stage unchanged)
confirmed ──(agent: at_risk)──────▶ at_risk
at_risk   ──(admin: approve with new date)──▶ confirmed
any       ──(physical receipt event)──▶ delivered
delivered ──────────────────────────▶ (terminal; further replies append `note` entries only)
```

**Invariant**: `current_stage='delivered'` AND `actual_delivery_at IS NULL` MUST never coexist (already enforced).

---

## 5. Relationships

```
SupplierOrder 1───1 Delivery
       │                 │
       │ matched_order   │ delivery
       ▼                 ▼
SupplierReply 1───0..1 EtaReviewItem
       │
       │ source_reply
       ▼
DeliveryTimelineEntry  ◀── source_review ── EtaReviewItem
```

- One `SupplierReply` ↔ at most one `EtaReviewItem` (UNIQUE).
- One `SupplierReply` MAY produce many `DeliveryTimelineEntry` rows over its lifecycle (e.g., ingest creates `acknowledged`; admin resolution later creates `eta_confirmed`).
- One `EtaReviewItem` produces at most one `DeliveryTimelineEntry` on resolution.

---

## 6. Migration plan

A single Alembic migration `2026_05_xx_eta_agent_init.py`:
1. Create `supplier_replies`, `delivery_timeline_entries`, `eta_review_items` with all indexes.
2. `ALTER TABLE deliveries ADD COLUMN has_pending_review BOOLEAN NOT NULL DEFAULT FALSE`.
3. Backfill: for every existing delivery, copy `stage_history` JSON entries (the legacy format) into `delivery_timeline_entries` as `actor_type='simulator'`, `event_type` mapped from the legacy stage name, `occurred_at` from the legacy timestamp. Original `stage_history` column is left in place (read-only) for one release as a safety net.
4. Add new columns `imap_host`, `imap_port`, `eta_auto_apply_threshold` to `email_config`.

---

**Phase 1 data model status**: COMPLETE.
