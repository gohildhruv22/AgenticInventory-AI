# Quickstart — Supplier Delivery ETA Agent (Feature 004)

**Audience**: developers running the AgenticInventory AI stack locally who want to exercise the new ETA-agent path end-to-end.

**Prerequisites**:
- The standard local stack already runs (`backend` on `http://127.0.0.1:8765`, `frontend` on `http://127.0.0.1:5173`), per plan 001.
- A Groq API key is configured in `.env` (`GROQ_API_KEY=…`) — required by every agent in the system.
- You can log in as an admin (e.g., `smoke+<id>@example.com` / `SmokePass123!` per the session smoke test).

---

## 1. Apply the schema migration

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

Expected: three new tables (`supplier_replies`, `delivery_timeline_entries`, `eta_review_items`) and a `has_pending_review` column on `deliveries`. The existing `stage_history` data is backfilled into `delivery_timeline_entries` as `actor_type='simulator'`.

## 2. Configure the IMAP source

In the running app, navigate to **Settings → Email**. Fill in:

- IMAP host: `imap.gmail.com` (or your provider).
- IMAP port: `993`.
- Username / password: the same identity already used to send outbound mail.
- ETA auto-apply confidence threshold: leave at the default `0.80`.

Save. The backend logs should print `EtaIngestor configured: host=imap.gmail.com poll_interval=300s`.

## 3. Seed a test purchase order

Either let the autonomous pipeline tick produce one organically (wait one cycle and watch the logs), or POST directly:

```powershell
$base = "http://127.0.0.1:8765"
# (uses the cookie session captured by the smoke flow)
Invoke-WebRequest -Uri "$base/api/v1/pipeline/tick" -Method POST -WebSession $s -UseBasicParsing
```

Capture the resulting `order_id` from the logs or from `GET /api/v1/decisions`.

## 4. Send a synthetic supplier reply

From any external mail client, reply to the outbound PO email keeping the subject (so it still contains `Order #<order_id>`). Example body:

> Thanks — we'll ship on Tuesday May 26 and you should receive it by May 29.

The same message can be injected directly into the test database during integration tests via the `FakeImapClient` fixture; see `tests/integration/test_eta_ingestor.py`.

## 5. Verify auto-apply (User Story 1)

Within one ingestor cycle (≤5 min on default settings):

```powershell
Invoke-WebRequest -Uri "$base/api/v1/deliveries/$delivery_id/timeline" -WebSession $s -UseBasicParsing
```

Expected:
- One new entry with `event_type='eta_confirmed'`, `parsed_date='2026-05-29T…'`, `confidence ≥ 80`, and `supplier_excerpt` containing the exact sentence.
- `GET /api/v1/deliveries/{delivery_id}` shows `current_stage='confirmed'`, `expected_delivery_at='2026-05-29T…'`, `has_pending_review=false`.
- Backend logs include: `EtaIngestor applied: delivery=<id> conf=92 date=2026-05-29` and `WebSocket broadcast: event=delivery.timeline.appended`.

## 6. Verify timeline UI (User Story 2)

In the frontend:
1. Open **Deliveries**.
2. Click the chevron on the delivery row. A timeline panel expands.
3. The latest entry shows the quoted supplier sentence, the parsed date, "auto-applied" badge with the confidence.
4. Trigger a second reply with a new date ("actually we'll ship May 30 instead"). After the next poll, the timeline gains a second entry tagged `eta_revised`, and the row's "expected" column updates.

## 7. Verify review queue (User Story 3)

Send a deliberately ambiguous reply, e.g., one without an order ID:

> Hey, we're going to be a few days late on the recent batch.

Within one cycle:
- `GET /api/v1/eta-reviews?state=pending` lists a new item with `raised_reason='unmatched_order'`.
- The Deliveries page does NOT silently update — instead, a red dot indicator appears in the navigation badge for "Review Queue".
- In the Review Queue page, open the item. Approve with a chosen delivery and date. The corresponding delivery row updates, and the review row moves to `resolution_state='approved'`.

## 8. Verify reversibility (constitution III)

After any auto-apply, hit the existing undo endpoint:

```powershell
Invoke-WebRequest -Uri "$base/api/v1/actions/$action_id/undo" -Method POST -WebSession $s -UseBasicParsing
```

Where `$action_id` is the most recent `action_logs` row of type `delivery.eta_update`. Expected: `expected_delivery_at` and `current_stage` are restored to their previous values, and a new timeline entry of type `manual_override` records the rollback with `actor_type='admin'`.

## 9. Tear down

The ingestor task stops automatically with the FastAPI lifespan when you kill the backend. To wipe test data:

```powershell
sqlite3 backend\agenticinventory.db "DELETE FROM eta_review_items; DELETE FROM delivery_timeline_entries; DELETE FROM supplier_replies;"
```

---

## Smoke-script summary

A green run touches every functional requirement at least once:

| FR | Verified by step |
|---|---|
| FR-001 mailbox polling | 4–5 |
| FR-002 order matching | 4–5, 7 |
| FR-003 date+intent extraction | 5, 6 |
| FR-004 confidence routing | 7 |
| FR-005 mutate + timeline | 5, 6 |
| FR-006 no overwrite of delivered | (test fixture in `test_eta_ingestor.py`) |
| FR-007 dedupe | (test fixture: send the same message twice) |
| FR-008 ignore auto-replies | (test fixture: `Auto-Submitted: auto-replied`) |
| FR-009 timeline UI | 6 |
| FR-010 review queue UI | 7 |
| FR-011 at-risk handling | 7 (with "cannot fulfill" body) |
| FR-012 audit actor + source | 5, 7, 8 |
| FR-013 unresolved-review indicator | 7 |
| FR-014 date-range handling | (test fixture: "between June 5 and June 9") |
| FR-015 retry on transient failure | (test fixture: IMAP raises once, succeeds on retry) |
