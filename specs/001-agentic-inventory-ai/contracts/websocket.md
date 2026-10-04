# WebSocket Contracts: AgenticInventory AI

**Phase**: 1 — Design & Contracts
**Date**: 2026-05-17
**Transport**: Socket.IO (WebSocket with long-polling fallback)
**Adapter**: Redis (for horizontal scaling)

## Connection

**URL**: `ws://{host}/socket.io/`
**Auth**: JWT token passed in `auth` handshake parameter.

```typescript
const socket = io("ws://localhost:8000", {
  auth: { token: getAccessToken() },
  reconnection: true,
  reconnectionAttempts: Infinity,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 30000,
  timeout: 10000,
});
```

**On connect**: Server emits `connected` with initial state snapshot.
**On auth failure**: Server emits `connect_error` with `{ message: "Authentication failed" }`.
**Heartbeat**: Socket.IO built-in ping/pong (25s interval, 20s timeout).

---

## Server → Client Events

### `inventory:update`

Emitted when inventory item stock levels change.

**Payload**:
```json
{
  "item_id": "uuid",
  "sku": "WGT-001",
  "name": "Widget A",
  "current_stock": 5,
  "previous_stock": 12,
  "status": "low_stock",
  "updated_at": "2026-05-17T14:00:00Z",
  "trigger": "consumption"
}
```

**Frequency**: On every stock change (reorder receipt, manual update, consumption simulation).

---

### `inventory:batch_update`

Emitted when multiple inventory items change at once (e.g., delivery receipt).

**Payload**:
```json
{
  "items": [
    { "item_id": "uuid", "sku": "WGT-001", "current_stock": 55, "previous_stock": 5, "status": "normal" },
    { "item_id": "uuid", "sku": "WGT-002", "current_stock": 30, "previous_stock": 2, "status": "normal" }
  ],
  "trigger": "delivery_receipt",
  "delivery_id": "uuid",
  "updated_at": "2026-05-17T14:30:00Z"
}
```

---

### `agent:status`

Emitted when any agent's operational status changes.

**Payload**:
```json
{
  "agent_type": "demand_forecast",
  "status": "processing",
  "pipeline_id": "uuid",
  "item_id": "uuid",
  "message": "Analyzing market trends for Widget A",
  "timestamp": "2026-05-17T14:00:01Z"
}
```

**Status values**: `idle`, `processing`, `completed`, `error`

---

### `agent:decision`

Emitted when an agent makes a new decision.

**Payload**:
```json
{
  "decision": {
    "id": "uuid",
    "agent_type": "decision_manager",
    "action_type": "approve_reorder",
    "inventory_item": { "id": "uuid", "name": "Widget A", "sku": "WGT-001" },
    "confidence_level": 82.5,
    "status": "executed",
    "reasoning_summary": "Stock below threshold. Forecast confidence 82.5% exceeds 75% threshold. Approving reorder of 55 units.",
    "can_undo": true,
    "created_at": "2026-05-17T14:00:03Z"
  }
}
```

---

### `agent:reasoning`

Emitted during agent processing to stream reasoning trace in real time (for workflow visualization).

**Payload**:
```json
{
  "pipeline_id": "uuid",
  "agent_type": "demand_forecast",
  "step": "analyzing_trends",
  "message": "Google Trends shows 15% increase in demand for electronics category",
  "progress": 0.4,
  "timestamp": "2026-05-17T14:00:01.500Z"
}
```

**Frequency**: Multiple events per agent during processing (typically 3-5 per agent).

---

### `pipeline:progress`

Emitted as the full pipeline progresses through agents (for Agent Workflow Visualization page).

**Payload**:
```json
{
  "pipeline_id": "uuid",
  "item_id": "uuid",
  "item_name": "Widget A",
  "stages": [
    { "agent": "inventory_monitor", "status": "completed", "duration_ms": 1200, "summary": "Low stock detected: 5 units remaining" },
    { "agent": "demand_forecast", "status": "completed", "duration_ms": 3500, "summary": "Confidence: 82.5%, Suggest 55 units" },
    { "agent": "decision_manager", "status": "processing", "started_at": "2026-05-17T14:00:05Z", "summary": null },
    { "agent": "supplier_email", "status": "pending", "summary": null },
    { "agent": "delivery_tracker", "status": "pending", "summary": null }
  ],
  "current_agent": "decision_manager",
  "started_at": "2026-05-17T14:00:00Z",
  "timestamp": "2026-05-17T14:00:05Z"
}
```

---

### `delivery:update`

Emitted when a delivery transitions to a new stage.

**Payload**:
```json
{
  "delivery_id": "uuid",
  "order_id": "uuid",
  "supplier_name": "ElecSupply Inc.",
  "current_stage": "in_transit",
  "previous_stage": "confirmed",
  "items_summary": "3 items, 55 units total",
  "expected_delivery_at": "2026-05-17T16:00:00Z",
  "timestamp": "2026-05-17T10:30:00Z"
}
```

---

### `kpi:update`

Emitted when KPI metrics change (new decision, delivery completed, etc.).

**Payload**:
```json
{
  "metric": "order_volume",
  "value": 6,
  "previous_value": 5,
  "timestamp": "2026-05-17T14:00:05Z"
}
```

Or batch update:
```json
{
  "metrics": {
    "order_volume": 6,
    "total_spend": 9680.00,
    "avg_confidence": 84.1,
    "decisions_approved": 5,
    "active_deliveries": 4
  },
  "timestamp": "2026-05-17T14:00:05Z"
}
```

---

### `email:status`

Emitted when an email's delivery status changes.

**Payload**:
```json
{
  "order_id": "uuid",
  "email_status": "sent",
  "previous_status": "queued",
  "supplier_email": "orders@elec-supplier.com",
  "retry_count": 0,
  "timestamp": "2026-05-17T14:00:04Z"
}
```

---

### `rollback:progress`

Emitted during an undo/rollback operation.

**Payload**:
```json
{
  "decision_id": "uuid",
  "status": "in_progress",
  "actions_total": 3,
  "actions_completed": 1,
  "current_action": "Sending cancellation email to supplier",
  "timestamp": "2026-05-17T14:10:01Z"
}
```

Final event when rollback completes:
```json
{
  "decision_id": "uuid",
  "status": "completed",
  "actions_total": 3,
  "actions_completed": 3,
  "summary": "All actions reversed successfully",
  "timestamp": "2026-05-17T14:10:05Z"
}
```

---

### `notification`

General admin/user notifications.

**Payload**:
```json
{
  "type": "warning",
  "title": "SMTP Connection Failed",
  "message": "Email to supplier@example.com failed after 3 retries. Manual intervention required.",
  "action_url": "/decisions/uuid",
  "timestamp": "2026-05-17T14:00:30Z"
}
```

**Type values**: `info`, `success`, `warning`, `error`

---

## Client → Server Events

### `subscribe:room`

Subscribe to a specific room for filtered updates.

**Payload**:
```json
{
  "room": "inventory:WGT-001"
}
```

**Rooms available**: `inventory:{sku}`, `pipeline:{pipeline_id}`, `delivery:{delivery_id}`

---

### `unsubscribe:room`

Leave a room.

**Payload**:
```json
{
  "room": "inventory:WGT-001"
}
```

---

## Connection Lifecycle

1. **Connect**: Client sends JWT in `auth` parameter
2. **Server validates JWT**: On failure, emits `connect_error`
3. **On success**: Server emits `connected` with:
   ```json
   {
     "user_id": "uuid",
     "active_pipelines": [],
     "active_deliveries": 3,
     "items_low_stock": 7
   }
   ```
4. **Client subscribes to rooms** as needed based on current page
5. **Heartbeat**: Automatic Socket.IO ping/pong
6. **Disconnect**: Client auto-reconnects with exponential backoff
7. **Reconnect**: Server resends current state snapshot for subscribed rooms
