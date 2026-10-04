# AgenticInventory AI — Backend

FastAPI + SQLAlchemy 2.x async backend powering the AgenticInventory AI platform.

See the root [README](../README.md) for architecture and local setup.

Azure deployment (App Service zip deploy, PostgreSQL, migrations): [infrastructure/azure/README.md](../infrastructure/azure/README.md).

## Supplier ETA Agent (Feature 004)

The backend hosts the **Supplier ETA Agent** — an IMAP-driven ingestor that
polls a supplier mailbox, runs each reply through an LLM extractor
(`backend/app/agents/eta_extractor.py`), and either auto-applies the new ETA
to the matched delivery or files a review item for an admin to resolve.

Key components:

| Module | Purpose |
| --- | --- |
| `app/agents/eta_ingestor.py` | IMAP polling loop, dedupe, supplier matching. |
| `app/agents/eta_extractor.py` | Few-shot LLM prompt that returns `EtaExtraction`. |
| `app/services/delivery_service.py::apply_eta_update` | Mutates a delivery + appends a timeline entry. |
| `app/services/eta_review_service.py` | Raises / approves / corrects / dismisses review items. |
| `app/api/deliveries.py` | Delivery list + timeline endpoints. |
| `app/api/eta_reviews.py` | Review-queue REST API. |
| `app/websocket/events.py` | `delivery.timeline.appended`, `eta_review.raised`, `eta_review.resolved`. |

Follow the end-to-end smoke script in
[`specs/004-supplier-delivery-eta-agent/quickstart.md`](../specs/004-supplier-delivery-eta-agent/quickstart.md)
to verify the feature locally.

Settings persisted in the `email_configurations` row (configurable in the
Settings page):

- `imap_host`, `imap_port` — IMAP mailbox the ingestor polls. Leave blank to
  disable.
- `eta_auto_apply_threshold` — confidence (0–100) at or above which the
  extracted ETA is applied without admin review.

## Running tests

```pwsh
cd backend
python -m pytest -q
```
