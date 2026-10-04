# AgenticInventory AI - Project Explanation

This document is prepared for project presentation and technical review. It explains the purpose, architecture, workflows, and implementation approach of AgenticInventory AI in a structured professional format.

## 1. Executive Summary

AgenticInventory AI is an autonomous procurement and inventory intelligence platform. It continuously monitors inventory risk, uses AI agents to forecast demand and decide on reorders, executes supplier communication, and tracks downstream delivery updates in real time.

The platform is designed to reduce manual intervention in procurement operations while preserving trust through:

- explainable decision traces
- review workflows for uncertain AI outputs
- rollback support for autonomous actions
- real-time visibility through live event streaming

## 2. Business Problem and Value

### Problem

Operations teams typically rely on spreadsheets, delayed reports, and manual supplier follow-ups. This creates stockout risk, slower response time, and inconsistent decision quality.

### Solution Value

AgenticInventory AI provides:

- proactive detection of low inventory
- structured AI-driven reorder decisions
- automated supplier order communication
- transparent timeline of delivery and ETA updates
- lower operational overhead with stronger control and auditability

## 3. Product Scope

The current implementation includes:

- authenticated web application for operations/admin users
- inventory management and visibility pages
- autonomous and manually triggerable AI pipeline
- supplier order email generation/sending
- delivery tracking and timeline records
- supplier reply ETA ingestion with confidence routing
- review queue for low-confidence ETA extraction
- decision undo/rollback support
- analytics/reporting interfaces and APIs

## 4. High-Level Architecture

```text
[React Frontend]
    |
    | REST + WebSocket
    v
[FastAPI Backend]
    |- API Routers
    |- Agent + Service Layer
    |- Monitoring Loop
    |- WebSocket Event Manager
    |
    v
[PostgreSQL + Redis]
```

### Frontend Layer

- React + TypeScript SPA with route-based pages
- TanStack Query for server-state synchronization
- Zustand for local app state
- Native WebSocket client for live updates and reconnect handling

### Backend Layer

- FastAPI APIs grouped by bounded domains
- Async SQLAlchemy service-oriented business logic
- Agent modules for monitoring, forecasting, decisioning, email, and ETA handling
- Autonomous monitoring loop running on startup (config-driven)
- WebSocket manager broadcasting stage/status/timeline/review events

### Data Layer

- PostgreSQL as source of truth for domain entities
- Redis for runtime support and fast operations
- Alembic migrations to manage schema evolution

## 5. Core Domain Components

Primary entities:

- Inventory Item
- Forecast
- Agent Decision
- Supplier Order
- Delivery
- Delivery Timeline Entry
- Supplier Reply
- ETA Review Item
- Action Log (for reversibility/audit trail)
- Email Configuration
- KPI Report

These entities support full operational traceability from stock risk detection to delivery update.

## 6. Agentic Workflow (Main Autonomous Flow)

### Stage 1: Inventory Monitoring

The monitoring loop scans active inventory items and identifies threshold breaches.

### Stage 2: Demand Forecasting

For each breached item, the forecast service/agent derives predicted demand, confidence, and suggested reorder quantity using contextual intelligence.

### Stage 3: Decision Evaluation

Decision logic compares confidence and policy thresholds to classify outcomes (approved, flagged, etc.) with reasoning traces.

### Stage 4: Supplier Ordering

Approved decisions generate supplier orders, compose purchase emails, and record send status.

### Stage 5: Delivery Tracking

Each order is paired with delivery tracking records and stage history for visibility.

### Stage 6: ETA Ingestion and Review

Supplier email replies are polled from IMAP, parsed for intent/date/confidence, and then:

- auto-applied when confidence is high and safe
- routed to review queue when ambiguous, risky, unmatched, or low confidence

### Stage 7: Real-Time UI Synchronization

WebSocket events propagate operational state changes to frontend pages (pipeline progress, timeline updates, review signals).

## 7. ETA Agent Workflow (Feature Highlight)

The Supplier Delivery ETA capability closes the post-order visibility gap:

1. Ingest inbound supplier reply
2. Match to delivery/order context
3. Extract ETA intent/date/excerpt with confidence
4. Apply update (safe path) or raise review item (guard path)
5. Append timeline event and update delivery summary
6. Broadcast `delivery.timeline.appended`, `eta_review.raised`, or `eta_review.resolved`

This design balances automation speed with operational safety.

## 8. Reversibility and Governance

The system is intentionally designed with reversible autonomous actions:

- mutation paths create action logs with before/after state
- rollback service can undo supported actions
- decision pages expose undo trails and outcomes
- audit metadata preserves actor, timestamp, and source references

This is critical for production trust in autonomous workflows.

## 9. Frontend Experience and Operational UX

Key UI modules:

- Dashboard: high-level operational KPIs
- Inventory: stock health, filtering, and updates
- Agents: live pipeline flow and activity feed
- Decisions: decision history and undo interactions
- Deliveries: timeline-first shipment tracking
- Analytics/Reports: performance and reporting visibility
- Settings: SMTP/IMAP, thresholds, and supplier mappings

The interface is optimized for decision speed and explainability visibility.

## 10. Deployment and Runtime Model

Local runtime (no Docker):

- SQLite or remote PostgreSQL via `DATABASE_URL`
- FastAPI backend (`uvicorn`) and Vite frontend dev server
- Optional local Redis

Azure production target (infrastructure ready in `infrastructure/azure/`):

| Layer | Service |
|-------|---------|
| Frontend | Azure Static Web Apps |
| Backend API + WebSocket | Azure App Service (Linux, Python 3.11) |
| Database | Azure Database for PostgreSQL Flexible Server 16 |
| Cache | Azure Cache for Redis |

Deployment approach:

- Bicep templates provision resources
- App Service zip deploy for backend (no container images in repo)
- Static Web App deploy for frontend build artifacts
- Secrets and API keys via App Service configuration
- Alembic migrations before or after first deploy
- Azure Pipelines template with deploy stage disabled until you enable it

## 11. Risks and Mitigations

- LLM ambiguity in supplier replies  
  Mitigation: confidence threshold + review queue + no silent risky updates

- External dependency outages (APIs, email, mailbox)  
  Mitigation: retries, logging, graceful degradation paths

- Wrong autonomous actions  
  Mitigation: explainability traces + rollback + admin oversight

- Real-time connection instability  
  Mitigation: frontend reconnect strategy with exponential backoff

## 12. Suggested Presentation Narrative

For senior stakeholder presentation:

1. Start with procurement pain points and why autonomy matters.
2. Show architecture slide (frontend, backend, data, event flow).
3. Walk through one complete item journey: low stock to supplier order.
4. Highlight ETA reply ingestion and review-queue safety model.
5. Demonstrate rollback as trust and governance mechanism.
6. Close with measurable value: response speed, transparency, reduced manual workload.

## 13. Conclusion

AgenticInventory AI is a practical autonomous operations platform that combines AI-driven execution with enterprise safety controls. It is not only automation-oriented, but also explainable, reviewable, and reversible, which makes it suitable for real procurement workflows and leadership-level confidence.
