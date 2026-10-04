# Data Model: AgenticInventory AI

**Phase**: 1 — Design & Contracts
**Date**: 2026-05-17
**Feature**: [spec.md](spec.md) | [plan.md](plan.md) | [research.md](research.md)

## Entity Relationship Overview

```
User ──────────────────────── EmailConfiguration (1:1)
  │
  ├──> InventoryItem ───────── Forecast (1:N)
  │         │                     │
  │         │                     ▼
  │         │              AgentDecision (1:N from Forecast)
  │         │                     │
  │         │                     ▼
  │         │              SupplierOrder (1:1 from Decision)
  │         │                     │
  │         │                     ▼
  │         │               Delivery (1:1 from Order)
  │         │                     │
  │         ◄─────────────────────┘ (inventory auto-update on delivery)
  │
  └──> ActionLog (audit trail for all agent actions)
  │
  └──> KPIReport (daily generated reports)
```

## Entities

### User

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | Unique user identifier |
| email | VARCHAR(255) | UNIQUE, NOT NULL, indexed | Login email address |
| password_hash | VARCHAR(255) | NOT NULL | Bcrypt-hashed password |
| name | VARCHAR(100) | NOT NULL | Display name |
| role | ENUM('admin','viewer') | NOT NULL, default 'admin' | Access role |
| is_active | BOOLEAN | NOT NULL, default TRUE | Account status |
| created_at | TIMESTAMP WITH TZ | NOT NULL, default NOW() | Registration time |
| updated_at | TIMESTAMP WITH TZ | NOT NULL, auto-update | Last modification |

**Validation Rules**:
- Email must be a valid email format
- Password must be >= 8 characters (validated before hashing)
- Role must be 'admin' or 'viewer'

---

### InventoryItem

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | Unique item identifier |
| name | VARCHAR(200) | NOT NULL | Product display name |
| sku | VARCHAR(50) | UNIQUE, NOT NULL, indexed | Stock Keeping Unit code |
| category | VARCHAR(100) | NOT NULL, indexed | Product category (maps to supplier) |
| current_stock | INTEGER | NOT NULL, default 0, >= 0 | Current stock level |
| reorder_threshold | INTEGER | NOT NULL, >= 0 | Stock level that triggers reorder |
| safety_stock | INTEGER | NOT NULL, default 0, >= 0 | Minimum safety stock buffer |
| lead_time_days | INTEGER | NOT NULL, default 7, >= 1 | Supplier lead time in days |
| unit_cost | DECIMAL(12,2) | NOT NULL, >= 0 | Cost per unit |
| supplier_email | VARCHAR(255) | NULL | Override supplier email (falls back to category mapping) |
| is_active | BOOLEAN | NOT NULL, default TRUE | Whether item is actively monitored |
| last_checked_at | TIMESTAMP WITH TZ | NULL | Last time monitoring agent checked this item |
| created_at | TIMESTAMP WITH TZ | NOT NULL, default NOW() | |
| updated_at | TIMESTAMP WITH TZ | NOT NULL, auto-update | |

**Validation Rules**:
- SKU must be alphanumeric with dashes/underscores only
- current_stock, reorder_threshold, safety_stock must be non-negative integers
- unit_cost must be non-negative
- lead_time_days must be >= 1

**State Transitions**:
- `NORMAL` (current_stock > reorder_threshold)
- `LOW_STOCK` (current_stock <= reorder_threshold AND current_stock > 0)
- `OUT_OF_STOCK` (current_stock == 0)
- `REORDER_PENDING` (reorder triggered, awaiting delivery)

---

### Forecast

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | |
| inventory_item_id | UUID | FK → InventoryItem.id, NOT NULL, indexed | Item being forecasted |
| predicted_demand | INTEGER | NOT NULL, >= 0 | Predicted demand quantity |
| confidence_score | DECIMAL(5,2) | NOT NULL, 0-100 | AI confidence score |
| suggested_order_qty | INTEGER | NOT NULL, >= 0 | Recommended order quantity |
| reasoning | TEXT | NOT NULL | Human-readable reasoning explanation |
| trends_score | DECIMAL(5,2) | NULL | Google Trends interest score |
| trend_direction | VARCHAR(20) | NULL | 'rising', 'stable', 'declining' |
| news_sentiment | DECIMAL(4,2) | NULL | News sentiment -1.0 to 1.0 |
| weather_impact | DECIMAL(5,2) | NULL | Weather disruption risk 0-100 |
| holiday_proximity | INTEGER | NULL | Days to nearest holiday |
| holiday_name | VARCHAR(100) | NULL | Name of upcoming holiday |
| staleness_flags | JSONB | NOT NULL, default '[]' | Which data sources used fallback |
| raw_signals | JSONB | NOT NULL | Full intelligence payload snapshot |
| created_at | TIMESTAMP WITH TZ | NOT NULL, default NOW(), indexed | |

**Validation Rules**:
- confidence_score must be between 0.00 and 100.00
- news_sentiment must be between -1.00 and 1.00
- reasoning must not be empty

---

### AgentDecision

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | |
| agent_type | VARCHAR(50) | NOT NULL, indexed | Agent that made the decision |
| action_type | VARCHAR(50) | NOT NULL, indexed | 'approve_reorder', 'flag_review', 'send_email', etc. |
| inventory_item_id | UUID | FK → InventoryItem.id, NULL, indexed | Associated item (if applicable) |
| forecast_id | UUID | FK → Forecast.id, NULL | Associated forecast (if applicable) |
| reasoning_trace | JSONB | NOT NULL | Full explainability payload |
| confidence_level | DECIMAL(5,2) | NULL | Decision confidence |
| alternatives_considered | JSONB | NOT NULL, default '[]' | Alternative actions evaluated |
| status | VARCHAR(20) | NOT NULL, default 'executed', indexed | 'executed', 'pending_review', 'rolled_back' |
| metadata | JSONB | NOT NULL, default '{}' | Additional context data |
| created_at | TIMESTAMP WITH TZ | NOT NULL, default NOW(), indexed | |
| updated_at | TIMESTAMP WITH TZ | NOT NULL, auto-update | |

**Validation Rules**:
- agent_type must be one of: 'inventory_monitor', 'demand_forecast', 'decision_manager', 'supplier_email', 'delivery_tracker', 'undo_rollback', 'reporting_kpi'
- status must be one of: 'executed', 'pending_review', 'rolled_back'
- reasoning_trace must contain: input_context, rationale, confidence, alternatives

**Reasoning Trace Schema** (JSONB):
```json
{
  "input_context": "Item SKU-001 stock at 5 units, threshold 10",
  "rationale": "Stock below threshold. Forecast confidence 82% exceeds 75% threshold. Market trends rising, no supply chain disruptions detected.",
  "confidence": 82.5,
  "alternatives": [
    {"action": "flag_for_review", "reason": "Conservative approach", "rejected_because": "Confidence exceeds threshold"},
    {"action": "delay_24h", "reason": "Wait for more data", "rejected_because": "Stock critically low"}
  ],
  "data_sources": ["google_trends", "news_api", "weather_api", "holiday_api"]
}
```

---

### SupplierOrder

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | |
| decision_id | UUID | FK → AgentDecision.id, NOT NULL, UNIQUE | Decision that triggered this order |
| supplier_name | VARCHAR(200) | NOT NULL | Supplier company name |
| supplier_email | VARCHAR(255) | NOT NULL | Email address order was sent to |
| items | JSONB | NOT NULL | Array of {item_id, sku, name, quantity, unit_cost} |
| total_cost | DECIMAL(14,2) | NOT NULL, >= 0 | Total order cost |
| email_status | VARCHAR(20) | NOT NULL, default 'queued', indexed | 'queued', 'sent', 'delivered', 'failed', 'cancelled' |
| email_message_id | VARCHAR(255) | NULL | SMTP message ID for tracking |
| retry_count | INTEGER | NOT NULL, default 0 | Number of send attempts |
| last_retry_at | TIMESTAMP WITH TZ | NULL | Time of last retry |
| cancellation_email_id | VARCHAR(255) | NULL | Message ID of cancellation email (if undone) |
| created_at | TIMESTAMP WITH TZ | NOT NULL, default NOW(), indexed | |
| updated_at | TIMESTAMP WITH TZ | NOT NULL, auto-update | |

**Validation Rules**:
- items must be a non-empty array
- total_cost must equal sum of (quantity * unit_cost) for all items
- email_status transitions: queued → sent → delivered; queued → failed; any → cancelled

---

### Delivery

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | |
| order_id | UUID | FK → SupplierOrder.id, NOT NULL, UNIQUE, indexed | Associated supplier order |
| current_stage | VARCHAR(30) | NOT NULL, default 'ordered' | Current delivery stage |
| stage_history | JSONB | NOT NULL, default '[]' | Array of {stage, timestamp, notes} |
| expected_delivery_at | TIMESTAMP WITH TZ | NULL | Estimated delivery time |
| actual_delivery_at | TIMESTAMP WITH TZ | NULL | Actual delivery time |
| items_received | JSONB | NULL | Items received (for partial delivery) |
| simulation_config | JSONB | NOT NULL, default '{}' | Simulation parameters used |
| created_at | TIMESTAMP WITH TZ | NOT NULL, default NOW() | |
| updated_at | TIMESTAMP WITH TZ | NOT NULL, auto-update | |

**Validation Rules**:
- current_stage must be one of: 'ordered', 'confirmed', 'in_transit', 'out_for_delivery', 'delivered', 'partial_delivery', 'failed'
- Stage transitions follow state machine (see research.md §6)

**Stage History Entry Schema** (JSONB array element):
```json
{
  "stage": "in_transit",
  "timestamp": "2026-05-17T14:30:00Z",
  "notes": "Shipment picked up by carrier"
}
```

---

### ActionLog

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | |
| agent_type | VARCHAR(50) | NOT NULL, indexed | Agent that performed the action |
| action_type | VARCHAR(50) | NOT NULL, indexed | Type of action performed |
| entity_type | VARCHAR(50) | NOT NULL | 'inventory_item', 'supplier_order', 'delivery' |
| entity_id | UUID | NOT NULL, indexed | ID of affected entity |
| before_state | JSONB | NOT NULL | Snapshot of entity before action |
| after_state | JSONB | NOT NULL | Snapshot of entity after action |
| compensating_action | JSONB | NOT NULL | Instructions for reversal |
| decision_id | UUID | FK → AgentDecision.id, NULL | Associated decision record |
| status | VARCHAR(20) | NOT NULL, default 'executed' | 'executed', 'rolled_back' |
| reasoning_trace | JSONB | NOT NULL | Agent reasoning for this action |
| rolled_back_at | TIMESTAMP WITH TZ | NULL | When rollback occurred |
| rolled_back_by | UUID | FK → User.id, NULL | User who initiated rollback |
| created_at | TIMESTAMP WITH TZ | NOT NULL, default NOW(), indexed | |

**Compensating Action Schema** (JSONB):
```json
{
  "type": "send_cancellation_email",
  "params": {
    "supplier_email": "supplier@example.com",
    "order_id": "uuid-here",
    "template": "cancellation"
  },
  "restore_entity": true
}
```

---

### KPIReport

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | |
| report_date | DATE | NOT NULL, UNIQUE, indexed | Date this report covers |
| order_volume | INTEGER | NOT NULL, default 0 | Total orders placed |
| total_spend | DECIMAL(14,2) | NOT NULL, default 0 | Total procurement spend |
| forecast_accuracy | DECIMAL(5,2) | NULL | Accuracy rate 0-100% |
| avg_confidence_score | DECIMAL(5,2) | NULL | Average forecast confidence |
| decisions_approved | INTEGER | NOT NULL, default 0 | Auto-approved decisions |
| decisions_flagged | INTEGER | NOT NULL, default 0 | Flagged for human review |
| decisions_rolled_back | INTEGER | NOT NULL, default 0 | Undone decisions |
| deliveries_completed | INTEGER | NOT NULL, default 0 | Successful deliveries |
| deliveries_failed | INTEGER | NOT NULL, default 0 | Failed deliveries |
| supplier_performance | JSONB | NOT NULL, default '{}' | Per-supplier metrics |
| agent_activity | JSONB | NOT NULL, default '{}' | Per-agent action counts |
| email_delivery_rate | DECIMAL(5,2) | NULL | Email delivery success % |
| cost_savings_estimate | DECIMAL(14,2) | NULL | Estimated savings from AI |
| email_sent | BOOLEAN | NOT NULL, default FALSE | Whether email report was sent |
| email_sent_at | TIMESTAMP WITH TZ | NULL | When email was sent |
| email_recipients | JSONB | NOT NULL, default '[]' | List of email recipients |
| report_data | JSONB | NOT NULL | Full report payload for rendering |
| created_at | TIMESTAMP WITH TZ | NOT NULL, default NOW() | |

---

### EmailConfiguration

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | |
| user_id | UUID | FK → User.id, NOT NULL, UNIQUE | Owner of this config |
| smtp_host | VARCHAR(255) | NOT NULL | SMTP server hostname |
| smtp_port | INTEGER | NOT NULL, default 587 | SMTP server port |
| smtp_username | VARCHAR(255) | NOT NULL | SMTP login username |
| smtp_password_encrypted | TEXT | NOT NULL | Encrypted SMTP password |
| smtp_use_tls | BOOLEAN | NOT NULL, default TRUE | Use TLS for SMTP |
| from_email | VARCHAR(255) | NOT NULL | Sender email address |
| from_name | VARCHAR(100) | NOT NULL, default 'AgenticInventory AI' | Sender display name |
| supplier_mappings | JSONB | NOT NULL, default '{}' | Category → supplier email mapping |
| confidence_threshold | DECIMAL(5,2) | NOT NULL, default 75.00 | Auto-order confidence threshold |
| daily_report_enabled | BOOLEAN | NOT NULL, default TRUE | Send daily KPI reports |
| daily_report_time | TIME | NOT NULL, default '00:00' | Time to send daily report |
| daily_report_recipients | JSONB | NOT NULL, default '[]' | Email addresses for daily reports |
| admin_notification_email | VARCHAR(255) | NULL | Email for admin alerts |
| created_at | TIMESTAMP WITH TZ | NOT NULL, default NOW() | |
| updated_at | TIMESTAMP WITH TZ | NOT NULL, auto-update | |

**Supplier Mappings Schema** (JSONB):
```json
{
  "Electronics": {"email": "orders@elec-supplier.com", "name": "ElecSupply Inc."},
  "Office Supplies": {"email": "bulk@officesupplier.com", "name": "OfficeMax Pro"},
  "Raw Materials": {"email": "procurement@rawmats.com", "name": "RawMats Global"}
}
```

## Indexes

| Table | Index | Columns | Purpose |
|-------|-------|---------|---------|
| inventory_item | ix_inventory_category | category | Category-based supplier lookup |
| inventory_item | ix_inventory_sku | sku (UNIQUE) | SKU lookup |
| inventory_item | ix_inventory_stock_check | is_active, current_stock, reorder_threshold | Monitoring query optimization |
| forecast | ix_forecast_item_date | inventory_item_id, created_at DESC | Latest forecast per item |
| agent_decision | ix_decision_status | status, created_at DESC | Decision page filtering |
| agent_decision | ix_decision_agent | agent_type, created_at DESC | Per-agent decision history |
| supplier_order | ix_order_email_status | email_status | Email queue processing |
| delivery | ix_delivery_stage | current_stage | Active delivery filtering |
| action_log | ix_actionlog_entity | entity_type, entity_id | Rollback lookup by entity |
| action_log | ix_actionlog_decision | decision_id | Rollback lookup by decision |
| kpi_report | ix_kpi_date | report_date (UNIQUE) | Daily report lookup |

## Post-Design Constitution Re-check

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. AutoGen-Only | ✅ PASS | Agent types map to AutoGen AssistantAgent instances |
| II. Groq-Exclusive | ✅ PASS | LLM config centralized, no alternative providers |
| III. Explainability & Reversibility | ✅ PASS | reasoning_trace on AgentDecision, ActionLog with before/after state + compensating actions |
| IV. UI/UX | ✅ PASS | Data model supports all 9 pages with rich query patterns |
| V. WebSockets | ✅ PASS | All entities have indexed timestamps for change detection |
| VI. External APIs | ✅ PASS | Forecast entity stores all intelligence signals |
| VII. Delivery Simulation | ✅ PASS | Delivery entity with state machine stages and simulation config |
| VIII. Reporting | ✅ PASS | KPIReport entity with full metrics and email tracking |
| IX. Email | ✅ PASS | EmailConfiguration entity with SMTP settings, SupplierOrder tracks email status |
| X. Architecture | ✅ PASS | Clean entity separation, all entities are ORM-mappable, migrations via Alembic |
