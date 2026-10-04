# REST API Contracts: AgenticInventory AI

**Phase**: 1 — Design & Contracts
**Date**: 2026-05-17
**Base URL**: `/api/v1`

## Authentication

### POST `/api/v1/auth/register`

Register a new user account.

**Request Body**:
```json
{
  "email": "admin@company.com",
  "password": "securePassword123",
  "name": "Jane Smith"
}
```

**Response 201**:
```json
{
  "id": "uuid",
  "email": "admin@company.com",
  "name": "Jane Smith",
  "role": "admin",
  "created_at": "2026-05-17T10:00:00Z"
}
```
Sets httpOnly cookie: `access_token` (JWT, 30 min) and `refresh_token` (JWT, 7 days).

**Response 409**: `{ "detail": "Email already registered" }`
**Response 422**: Validation error (invalid email format, password too short)

---

### POST `/api/v1/auth/login`

Authenticate and create session.

**Request Body**:
```json
{
  "email": "admin@company.com",
  "password": "securePassword123"
}
```

**Response 200**:
```json
{
  "id": "uuid",
  "email": "admin@company.com",
  "name": "Jane Smith",
  "role": "admin"
}
```
Sets httpOnly cookies.

**Response 401**: `{ "detail": "Invalid credentials" }`
**Rate Limit**: 5 attempts per minute per IP.

---

### POST `/api/v1/auth/logout`

Clear session cookies.

**Response 200**: `{ "message": "Logged out" }`

---

### GET `/api/v1/auth/me`

Get current authenticated user.

**Response 200**: User object (same as register response).
**Response 401**: Not authenticated.

---

## Inventory

### GET `/api/v1/inventory`

List all inventory items with filtering and pagination.

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| page | int | 1 | Page number |
| per_page | int | 50 | Items per page (max 100) |
| category | string | null | Filter by category |
| status | string | null | 'normal', 'low_stock', 'out_of_stock', 'reorder_pending' |
| search | string | null | Search by name or SKU |
| sort_by | string | 'name' | Sort field |
| sort_order | string | 'asc' | 'asc' or 'desc' |

**Response 200**:
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Widget A",
      "sku": "WGT-001",
      "category": "Electronics",
      "current_stock": 5,
      "reorder_threshold": 10,
      "safety_stock": 3,
      "lead_time_days": 7,
      "unit_cost": 25.99,
      "status": "low_stock",
      "is_active": true,
      "last_checked_at": "2026-05-17T14:00:00Z",
      "updated_at": "2026-05-17T14:00:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "per_page": 50,
  "pages": 3
}
```

---

### GET `/api/v1/inventory/{id}`

Get single inventory item with latest forecast.

**Response 200**:
```json
{
  "id": "uuid",
  "name": "Widget A",
  "sku": "WGT-001",
  "category": "Electronics",
  "current_stock": 5,
  "reorder_threshold": 10,
  "safety_stock": 3,
  "lead_time_days": 7,
  "unit_cost": 25.99,
  "status": "low_stock",
  "is_active": true,
  "latest_forecast": {
    "id": "uuid",
    "predicted_demand": 50,
    "confidence_score": 82.5,
    "suggested_order_qty": 55,
    "reasoning": "...",
    "created_at": "2026-05-17T14:00:00Z"
  },
  "pending_orders": [],
  "active_deliveries": []
}
```

---

### POST `/api/v1/inventory`

Create a new inventory item.

**Request Body**:
```json
{
  "name": "Widget A",
  "sku": "WGT-001",
  "category": "Electronics",
  "current_stock": 100,
  "reorder_threshold": 10,
  "safety_stock": 3,
  "lead_time_days": 7,
  "unit_cost": 25.99
}
```

**Response 201**: Created item object.
**Response 409**: `{ "detail": "SKU already exists" }`

---

### PATCH `/api/v1/inventory/{id}`

Update inventory item fields.

**Request Body** (partial update):
```json
{
  "current_stock": 50,
  "reorder_threshold": 15
}
```

**Response 200**: Updated item object.

---

### DELETE `/api/v1/inventory/{id}`

Soft-delete (deactivate) inventory item.

**Response 200**: `{ "message": "Item deactivated" }`

---

### POST `/api/v1/inventory/seed`

Seed demo inventory data for demonstrations.

**Response 201**: `{ "message": "Seeded 25 demo items", "count": 25 }`

---

## Agent Decisions

### GET `/api/v1/decisions`

List agent decisions with filtering.

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| page | int | 1 | Page number |
| per_page | int | 20 | Items per page |
| agent_type | string | null | Filter by agent type |
| status | string | null | 'executed', 'pending_review', 'rolled_back' |
| item_id | uuid | null | Filter by inventory item |
| date_from | datetime | null | Start date filter |
| date_to | datetime | null | End date filter |

**Response 200**:
```json
{
  "decisions": [
    {
      "id": "uuid",
      "agent_type": "decision_manager",
      "action_type": "approve_reorder",
      "inventory_item": { "id": "uuid", "name": "Widget A", "sku": "WGT-001" },
      "forecast": { "confidence_score": 82.5, "suggested_order_qty": 55 },
      "reasoning_trace": { "...": "..." },
      "confidence_level": 82.5,
      "alternatives_considered": [],
      "status": "executed",
      "can_undo": true,
      "created_at": "2026-05-17T14:00:00Z"
    }
  ],
  "total": 45,
  "page": 1,
  "per_page": 20,
  "pages": 3
}
```

---

### GET `/api/v1/decisions/{id}`

Get single decision with full reasoning trace and related entities.

**Response 200**: Full decision object with expanded forecast, order, delivery, and action log.

---

### POST `/api/v1/decisions/{id}/undo`

Initiate undo/rollback for a decision.

**Response 200**:
```json
{
  "message": "Rollback initiated",
  "decision_id": "uuid",
  "actions_reversed": 3,
  "rollback_summary": [
    { "action": "cancellation_email_sent", "entity": "supplier_order", "entity_id": "uuid" },
    { "action": "stock_restored", "entity": "inventory_item", "entity_id": "uuid", "restored_to": 100 },
    { "action": "delivery_cancelled", "entity": "delivery", "entity_id": "uuid" }
  ]
}
```

**Response 409**: `{ "detail": "Action cannot be undone", "reason": "Supplier has already shipped" }`
**Response 422**: `{ "detail": "Action already rolled back" }`

---

## Deliveries

### GET `/api/v1/deliveries`

List deliveries with filtering.

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| page | int | 1 | |
| per_page | int | 20 | |
| stage | string | null | Filter by current stage |
| order_id | uuid | null | Filter by order |

**Response 200**:
```json
{
  "deliveries": [
    {
      "id": "uuid",
      "order": { "id": "uuid", "supplier_name": "ElecSupply Inc.", "total_cost": 1429.45 },
      "current_stage": "in_transit",
      "stage_history": [
        { "stage": "ordered", "timestamp": "2026-05-17T10:00:00Z" },
        { "stage": "confirmed", "timestamp": "2026-05-17T10:05:00Z" },
        { "stage": "in_transit", "timestamp": "2026-05-17T10:30:00Z" }
      ],
      "expected_delivery_at": "2026-05-17T16:00:00Z",
      "items_count": 3,
      "created_at": "2026-05-17T10:00:00Z"
    }
  ],
  "total": 12,
  "page": 1,
  "per_page": 20,
  "pages": 1
}
```

---

### GET `/api/v1/deliveries/{id}`

Get single delivery with full stage history and order details.

---

## Reports

### GET `/api/v1/reports`

List KPI reports.

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| page | int | 1 | |
| per_page | int | 30 | |
| date_from | date | null | Start date |
| date_to | date | null | End date |

**Response 200**:
```json
{
  "reports": [
    {
      "id": "uuid",
      "report_date": "2026-05-16",
      "order_volume": 12,
      "total_spend": 15420.50,
      "forecast_accuracy": 87.3,
      "decisions_approved": 10,
      "decisions_flagged": 2,
      "deliveries_completed": 8,
      "email_sent": true,
      "created_at": "2026-05-17T00:05:00Z"
    }
  ],
  "total": 30,
  "page": 1,
  "per_page": 30,
  "pages": 1
}
```

---

### GET `/api/v1/reports/{id}`

Get full KPI report with all metrics and chart data.

**Response 200**: Full report object with `report_data` containing chart-ready datasets.

---

### GET `/api/v1/reports/dashboard`

Get real-time KPI dashboard metrics (today's running totals).

**Response 200**:
```json
{
  "today": {
    "order_volume": 5,
    "total_spend": 8250.00,
    "forecast_accuracy": 91.2,
    "avg_confidence": 83.7,
    "decisions_approved": 4,
    "decisions_flagged": 1,
    "active_deliveries": 3,
    "items_low_stock": 7,
    "items_out_of_stock": 1
  },
  "trends": {
    "order_volume_7d": [3, 5, 8, 4, 7, 6, 5],
    "spend_7d": [4200, 6100, 9800, 5500, 8100, 7200, 8250],
    "accuracy_7d": [85.1, 88.3, 82.7, 90.1, 87.5, 89.2, 91.2]
  },
  "agent_activity": {
    "inventory_monitor": 142,
    "demand_forecast": 12,
    "decision_manager": 12,
    "supplier_email": 4,
    "delivery_tracker": 8,
    "undo_rollback": 1,
    "reporting_kpi": 1
  }
}
```

---

## Settings

### GET `/api/v1/settings/email`

Get current email configuration (SMTP password excluded).

**Response 200**:
```json
{
  "smtp_host": "smtp.sendgrid.net",
  "smtp_port": 587,
  "smtp_username": "apikey",
  "smtp_use_tls": true,
  "from_email": "inventory@company.com",
  "from_name": "AgenticInventory AI",
  "supplier_mappings": {
    "Electronics": { "email": "orders@elec-supplier.com", "name": "ElecSupply Inc." }
  },
  "confidence_threshold": 75.00,
  "daily_report_enabled": true,
  "daily_report_time": "00:00",
  "daily_report_recipients": ["director@company.com"],
  "admin_notification_email": "admin@company.com"
}
```

---

### PUT `/api/v1/settings/email`

Update email configuration.

**Request Body**: Full email config object (including `smtp_password` when changing).

**Response 200**: Updated config (password excluded).

---

### POST `/api/v1/settings/email/test`

Send a test email to verify SMTP configuration.

**Request Body**:
```json
{
  "recipient": "test@company.com"
}
```

**Response 200**: `{ "message": "Test email sent successfully" }`
**Response 502**: `{ "detail": "SMTP connection failed", "error": "..." }`

---

## Pipeline

### POST `/api/v1/pipeline/trigger`

Manually trigger the agent pipeline for a specific item (for demos).

**Request Body**:
```json
{
  "inventory_item_id": "uuid"
}
```

**Response 202**: `{ "message": "Pipeline triggered", "pipeline_id": "uuid" }`

---

### GET `/api/v1/pipeline/{id}/status`

Get pipeline execution status.

**Response 200**:
```json
{
  "pipeline_id": "uuid",
  "status": "in_progress",
  "current_agent": "demand_forecast",
  "stages": [
    { "agent": "inventory_monitor", "status": "completed", "duration_ms": 1200 },
    { "agent": "demand_forecast", "status": "in_progress", "started_at": "2026-05-17T14:00:02Z" }
  ]
}
```

---

## Health

### GET `/api/v1/health`

Health check endpoint.

**Response 200**:
```json
{
  "status": "healthy",
  "services": {
    "database": "connected",
    "redis": "connected",
    "chromadb": "connected",
    "celery": "connected"
  },
  "version": "1.0.0"
}
```

---

## Common Response Patterns

**Pagination Envelope**:
```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "per_page": 20,
  "pages": 0
}
```

**Error Response**:
```json
{
  "detail": "Human-readable error message",
  "error_code": "MACHINE_READABLE_CODE",
  "field_errors": {
    "email": "Invalid email format"
  }
}
```

**Authentication**: All endpoints except `/auth/register`, `/auth/login`, and `/health` require valid JWT cookie. Returns 401 if missing/expired.
