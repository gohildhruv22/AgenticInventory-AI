# WebSocket Event Contract — Supplier Delivery ETA Agent

**Feature**: 004-supplier-delivery-eta-agent
**Channel**: `/ws` (existing — no new socket introduced)
**Auth**: existing cookie-session — events are scoped to authenticated admin clients only.

The feature introduces three new event types. They follow the existing envelope shape used by every other broadcast in the app:

```json
{
  "event": "<event_name>",
  "timestamp": "2026-05-21T10:15:30.123Z",
  "data": { ... }
}
```

---

## 1. `delivery.timeline.appended`

Published immediately after a `DeliveryTimelineEntry` row is committed — whether the source is the ETA agent, an admin resolution, the simulator, or a manual override.

**Payload `data`**:

| Field | Type | Notes |
|---|---|---|
| `delivery_id` | UUID | Delivery whose timeline grew. |
| `entry` | `DeliveryTimelineEntry` | Full entry as defined in `deliveries-timeline.openapi.yaml`. |
| `delivery_summary` | object | Convenience snapshot: `{ current_stage, expected_delivery_at, has_pending_review }` so the deliveries-list cache can be patched in place without a follow-up fetch. |

**Frontend handling**: invalidates `queryKeys.deliveries.timeline(delivery_id)` and `queryKeys.deliveries.list`. If the entry is from a different delivery than the one currently expanded, only the list cache is touched.

---

## 2. `eta_review.raised`

Published when the ingestor creates an `EtaReviewItem` (low confidence, unmatched order, ambiguous match, negative intent, past date, or non-English).

**Payload `data`**:

| Field | Type | Notes |
|---|---|---|
| `review` | `EtaReviewSummary` | As defined in `eta-reviews.openapi.yaml`. |
| `candidate_delivery_id` | UUID \| null | Mirrors the field on the review item; convenience for the UI badge. |

**Frontend handling**: invalidates `queryKeys.etaReviews.list({ state: 'pending' })`. If `candidate_delivery_id` is set, also flips `has_pending_review` on the cached delivery and shows a toast linking to the review queue.

---

## 3. `eta_review.resolved`

Published when an admin approves, corrects, or dismisses a review item.

**Payload `data`**:

| Field | Type | Notes |
|---|---|---|
| `review` | `EtaReviewDetailResponse` | Final state of the review item, including `resolved_by`, `resolved_at`, `resolution_payload`. |
| `delivery_id` | UUID \| null | The delivery affected by the resolution, if any. |
| `delivery_summary` | object \| null | `{ current_stage, expected_delivery_at, has_pending_review }` for cache patching. |

**Frontend handling**: invalidates the review queue caches and (if `delivery_id` is set) the affected delivery's timeline + summary.

---

## Ordering guarantees

- `eta_review.raised` is published BEFORE `delivery.timeline.appended` for the `acknowledged`/`at_risk` entry written by the same ingestor cycle (so the badge appears before the timeline entry it explains).
- `eta_review.resolved` is published AFTER the corresponding `delivery.timeline.appended` for the resolution entry (so the timeline is consistent the moment the toast/inbox refresh fires).

## Backwards compatibility

- No existing event payload is changed.
- The existing `DeliveryResponse` payload gains two NEW fields (`has_pending_review`, `latest_timeline_entry`); both are nullable / boolean-default, so older clients that ignore unknown fields continue to render.

## At-least-once semantics

The WebSocket dispatcher already retries delivery on reconnect by streaming any events with `event_id > last_acked_id`. The new event types reuse the same envelope and are subject to the same at-least-once guarantee. Frontend handlers MUST be idempotent — keying off `entry.id` / `review.id` deduplicates safely.
