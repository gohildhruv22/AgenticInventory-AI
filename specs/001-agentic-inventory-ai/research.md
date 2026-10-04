# Research: AgenticInventory AI

**Phase**: 0 — Outline & Research
**Date**: 2026-05-17
**Feature**: [spec.md](spec.md) | [plan.md](plan.md)

## 1. AutoGen Agent Orchestration Pattern

**Decision**: Use AutoGen `GroupChat` with a `GroupChatManager` as the primary orchestration pattern, with sequential agent handoffs for the procurement pipeline.

**Rationale**: The procurement pipeline is inherently sequential (monitor → forecast → decide → email → track → update), which maps naturally to AutoGen's `GroupChat` with ordered speaker selection. The `GroupChatManager` coordinates agent turns while allowing each agent to produce its reasoning trace independently. AutoGen 0.4+ supports custom speaker selection functions, enabling deterministic pipeline ordering while still allowing agents to communicate contextually.

**Alternatives Considered**:
- **AutoGen two-agent chat**: Too limited for 7-agent coordination. Would require nested conversations that obscure the pipeline flow.
- **AutoGen Swarm pattern**: Better for dynamic task routing, but our pipeline is deterministic — overkill complexity without benefit.
- **Custom orchestrator on top of AutoGen**: Would violate Constitution Principle I (AutoGen primitives only).

**Implementation Pattern**:
```
GroupChat(
  agents=[monitor, forecaster, decision_mgr, email_agent, tracker, undo_agent, reporter],
  speaker_selection_method=custom_pipeline_selector,
  max_round=10
)
```
Each agent registers as an `AssistantAgent` with Groq LLM config. The `custom_pipeline_selector` enforces the procurement pipeline order while allowing the Undo Agent to be invoked on-demand.

---

## 2. Groq LLM Integration with AutoGen

**Decision**: Configure Groq as a custom LLM provider in AutoGen using the OpenAI-compatible API endpoint with `llama-3.3-70b-versatile` as the primary model.

**Rationale**: Groq's API is OpenAI-compatible, which means AutoGen's built-in `OAI_CONFIG_LIST` mechanism works directly by pointing the `base_url` to `https://api.groq.com/openai/v1`. The `llama-3.3-70b-versatile` model provides the best balance of reasoning capability and speed on Groq's inference hardware. For simpler agent tasks (email formatting, status updates), `llama-3.1-8b-instant` can be used to reduce latency and token costs.

**Alternatives Considered**:
- **llama-3.1-70b-versatile**: Older generation, superseded by 3.3 with better instruction following.
- **mixtral-8x7b-32768**: Good for long-context tasks but weaker reasoning than Llama 3.3 70B.
- **Single model for all agents**: Simpler config but wasteful — small agents (email, tracking) don't need 70B parameters.

**Configuration**:
```python
GROQ_CONFIG = {
    "model": "llama-3.3-70b-versatile",  # Primary reasoning model
    "api_key": os.environ["GROQ_API_KEY"],
    "base_url": "https://api.groq.com/openai/v1",
    "api_type": "openai",
    "temperature": 0.3,  # Low temp for deterministic procurement decisions
    "max_tokens": 4096,
}
```

**Rate Limit Strategy**: Groq enforces rate limits per model. Use Redis-backed token bucket rate limiter with queue-based request serialization to avoid 429 errors during burst agent activity.

---

## 3. External Intelligence API Integration

**Decision**: Build an `IntelligenceAggregator` service that queries all 4 external APIs concurrently, caches results in Redis (TTL-based), and provides a unified intelligence payload to the Demand Forecast Agent.

**Rationale**: External API calls are the primary latency bottleneck in the forecast pipeline. Concurrent requests (via `asyncio.gather`) reduce total wait time to the slowest API response (~1-2s) rather than sequential (~4-6s). Redis caching (30-minute TTL for trends/news, 1-hour for weather, 24-hour for holidays) prevents redundant API calls and provides fallback data when APIs are unavailable.

**Alternatives Considered**:
- **Direct API calls from the agent**: Would couple the agent to HTTP concerns and make testing difficult.
- **Pre-fetching on schedule**: Would miss real-time demand signals. Hybrid approach (cache + on-demand refresh) is optimal.
- **Third-party aggregation service**: No suitable service exists that combines all four data types for procurement use cases.

**API Integration Details**:

| API | Endpoint | Cache TTL | Fallback |
|-----|----------|-----------|----------|
| Google Trends (pytrends) | `pytrends.interest_over_time()` | 30 min | Last cached result + "stale data" flag |
| News API | `newsapi.org/v2/everything` | 30 min | Last cached result + reduced confidence |
| Weather API (OpenWeatherMap) | `api.openweathermap.org/data/3.0` | 60 min | Last cached result + "weather unknown" flag |
| Holiday API (Calendarific) | `calendarific.com/api/v2/holidays` | 24 hr | Static holiday calendar fallback |

**Unified Intelligence Payload**:
```python
@dataclass
class IntelligenceSignals:
    trends_score: float        # 0-100 market interest
    trend_direction: str       # "rising", "stable", "declining"
    news_sentiment: float      # -1.0 to 1.0 supply chain sentiment
    news_headlines: list[str]  # Top 3 relevant headlines
    weather_impact: float      # 0-100 weather disruption risk
    weather_summary: str       # Human-readable weather context
    holiday_proximity: int     # Days to nearest relevant holiday
    holiday_name: str | None   # Name of upcoming holiday
    staleness_flags: list[str] # Which sources used cached/fallback data
    fetched_at: datetime
```

---

## 4. WebSocket Architecture

**Decision**: Use `python-socketio` (async mode) mounted on the FastAPI ASGI app, with `Redis` as the Socket.IO adapter for horizontal scaling. Frontend uses `socket.io-client`.

**Rationale**: Socket.IO provides automatic reconnection, room-based broadcasting, and fallback to long-polling if WebSockets are blocked by proxies — critical for enterprise deployments behind firewalls. The Redis adapter enables multiple backend instances to share WebSocket state, supporting horizontal scaling on Azure Container Apps. Native WebSocket protocol would require custom reconnection, room management, and scaling logic.

**Alternatives Considered**:
- **Native WebSockets (websockets library)**: Lighter weight but requires custom reconnection, room management, and no built-in Redis adapter.
- **FastAPI WebSocket endpoints**: Built-in but no Redis adapter, no auto-reconnection, no room broadcasting.
- **Separate Node.js WebSocket gateway**: Would add operational complexity (second runtime) without significant benefit since python-socketio is fully async.

**Event Architecture**:

| Channel | Direction | Purpose |
|---------|-----------|---------|
| `inventory:update` | Server → Client | Real-time stock level changes |
| `agent:status` | Server → Client | Agent activity status (processing, idle, error) |
| `agent:decision` | Server → Client | New agent decision created |
| `agent:reasoning` | Server → Client | Live reasoning trace streaming |
| `delivery:update` | Server → Client | Delivery stage transitions |
| `kpi:update` | Server → Client | KPI metric changes |
| `pipeline:progress` | Server → Client | Full pipeline progression (for workflow viz) |

**Scaling**: Redis pub/sub adapter ensures that a WebSocket event emitted by any backend instance is delivered to clients connected to any other instance.

---

## 5. Email Queue Architecture (SMTP)

**Decision**: Use Celery with Redis broker for asynchronous email delivery. Each email is a Celery task with built-in retry logic (3 attempts, exponential backoff). Use `aiosmtplib` for async SMTP connections and Jinja2 for HTML template rendering.

**Rationale**: Celery provides persistent task queues with guaranteed delivery — if the worker crashes, unacknowledged tasks are redelivered. This is critical for supplier purchase orders where email loss means lost revenue. Exponential backoff (30s, 120s, 480s) prevents SMTP server flooding during outages. Jinja2 templates enable the branded dark-theme email design required by Constitution Principle IX.

**Alternatives Considered**:
- **In-process async email**: Lost on server restart. No retry persistence.
- **FastAPI BackgroundTasks**: No persistence, no retry, no worker scaling.
- **Dedicated email service (SendGrid API)**: Would add a hard dependency on a specific vendor. SMTP is provider-agnostic per spec assumptions.

**Task Chain for Purchase Orders**:
```
render_email_template → send_email_smtp → record_email_status → emit_ws_notification
```

**Retry Policy**:
- Max retries: 3
- Backoff: exponential (base=30s, factor=4) → 30s, 120s, 480s
- On final failure: mark email as `failed`, emit admin notification via WebSocket, log for manual resolution

---

## 6. Delivery Simulation Engine

**Decision**: Implement a state machine-based simulation engine that runs as periodic Celery beat tasks, advancing delivery stages on configurable schedules.

**Rationale**: The simulation must feel realistic with configurable timing between stages. A state machine cleanly models the delivery lifecycle (ordered → confirmed → in_transit → out_for_delivery → delivered) with defined transitions and guards. Running as Celery beat tasks enables time-based stage progression without blocking the main application or requiring long-running processes.

**Alternatives Considered**:
- **Manual triggering**: Would require user intervention, defeating the "autonomous" requirement.
- **In-process timers**: Not persistent across restarts. Unreliable for multi-hour simulations.
- **External simulation service**: Unnecessary complexity for v1's built-in simulation.

**State Machine**:
```
ORDERED → CONFIRMED → IN_TRANSIT → OUT_FOR_DELIVERY → DELIVERED
     ↘ FAILED (from any state)
     ↘ PARTIAL_DELIVERY (from OUT_FOR_DELIVERY)
```

**Configurable Parameters**:
- `confirmation_delay`: time from order to supplier confirmation (default: 1-5 min)
- `transit_duration`: time in transit (default: 5-30 min for demo, configurable)
- `delivery_probability`: chance of successful delivery (default: 0.95)
- `partial_delivery_probability`: chance of partial when delivering (default: 0.1)

---

## 7. Undo & Rollback Strategy

**Decision**: Implement event-sourced rollback using an append-only action log. Each autonomous action records a `before_state` snapshot and a `compensating_action` definition. The Undo Agent reads these to reverse actions.

**Rationale**: Event sourcing provides complete auditability (Constitution Principle III) and deterministic rollback. Storing `before_state` snapshots avoids complex reverse-computation logic. The compensating action pattern (from saga pattern in distributed systems) handles cross-service rollbacks (e.g., send cancellation email after undoing an order).

**Alternatives Considered**:
- **Database transaction rollback**: Only works within a single request. Cannot undo across time or undo email sends.
- **CQRS with event replay**: Full CQRS is overkill for v1's scale. Simplified event log achieves the same rollback capability.
- **Soft deletes only**: Insufficient — doesn't handle email cancellation or inventory restoration.

**Action Log Schema**:
```python
class ActionLog:
    id: UUID
    agent_type: str
    action_type: str            # "reorder", "email_sent", "inventory_update"
    entity_type: str            # "inventory_item", "supplier_order"
    entity_id: UUID
    before_state: dict          # JSON snapshot of entity before action
    after_state: dict           # JSON snapshot of entity after action
    compensating_action: dict   # Instructions for reversal
    status: str                 # "executed", "rolled_back"
    reasoning_trace: dict       # Full agent reasoning for this action
    created_at: datetime
    rolled_back_at: datetime | None
    rolled_back_by: UUID | None  # User who initiated undo
```

**Rollback Flow**:
1. User clicks "Undo" on decision record
2. Undo Agent reads the `ActionLog` entry and all dependent actions
3. For each action in reverse chronological order:
   a. Execute `compensating_action` (e.g., send cancellation email)
   b. Restore `before_state` to the entity
   c. Mark action as `rolled_back`
4. Emit WebSocket events for all state changes
5. Log rollback audit trail

---

## 8. ChromaDB Agent Memory

**Decision**: Use ChromaDB as a vector store for agent session memory, storing conversation context and past decision outcomes as embeddings for retrieval-augmented agent reasoning.

**Rationale**: Agents need to reference past decisions to make contextually aware new decisions (e.g., "this item was reordered 3 days ago, skip"). ChromaDB provides simple vector similarity search without the operational overhead of a full vector database (Pinecone, Weaviate). Running ChromaDB as a sidecar container keeps the architecture self-contained.

**Alternatives Considered**:
- **PostgreSQL + pgvector**: Would work but couples AI memory to the relational schema. Migrations become complex when embedding dimensions change.
- **In-memory only**: Lost on restart. Spec requires agents to maintain context within sessions.
- **Redis vector search**: Redis Stack supports vector similarity but adds complexity to the Redis deployment.

**Collection Strategy**:
- `agent_decisions`: Past decision records with reasoning embeddings for similar-decision lookup
- `forecast_history`: Past forecasts with outcome accuracy for forecast calibration
- `inventory_patterns`: Historical consumption patterns for demand prediction context

---

## 9. Frontend Design System Architecture

**Decision**: Build a custom design system using ShadCN UI as the component primitive layer, extended with glassmorphism, gradient, and animation utilities via Tailwind CSS custom theme and Framer Motion animation presets.

**Rationale**: ShadCN UI provides accessible, unstyled component primitives (dialogs, dropdowns, tables, forms) that can be themed to match the futuristic dark aesthetic without fighting an opinionated design library. Tailwind CSS enables rapid visual iteration with custom theme tokens (colors, gradients, glass effects). Framer Motion provides declarative animation primitives that compose well with React component lifecycle.

**Design Tokens**:
```
Colors:
  --bg-primary: #0A0A0F (deep dark)
  --bg-secondary: #12121A (card background)
  --bg-glass: rgba(255, 255, 255, 0.05) (glassmorphism)
  --accent-primary: #8B5CF6 (purple-500)
  --accent-secondary: #EC4899 (pink-500)
  --gradient-primary: linear-gradient(135deg, #8B5CF6, #EC4899)
  --gradient-glow: radial-gradient(ellipse, rgba(139,92,246,0.15), transparent)
  --text-primary: #F8FAFC (slate-50)
  --text-secondary: #94A3B8 (slate-400)
  --border-glass: rgba(255, 255, 255, 0.1)
  --success: #10B981 (emerald-500)
  --warning: #F59E0B (amber-500)
  --error: #EF4444 (red-500)

Glassmorphism:
  backdrop-filter: blur(12px)
  background: var(--bg-glass)
  border: 1px solid var(--border-glass)
  border-radius: 16px

Animations (Framer Motion presets):
  fadeInUp: { initial: {opacity:0, y:20}, animate: {opacity:1, y:0} }
  scaleIn: { initial: {scale:0.95, opacity:0}, animate: {scale:1, opacity:1} }
  slideInLeft: { initial: {x:-20, opacity:0}, animate: {x:0, opacity:1} }
  pulseGlow: { animate: {boxShadow: ["0 0 20px rgba(139,92,246,0.3)", "0 0 40px rgba(139,92,246,0.6)", "0 0 20px rgba(139,92,246,0.3)"]}, transition: {repeat:Infinity, duration:2} }
```

**Component Hierarchy**:
- **Atoms**: GlassCard, GradientButton, AnimatedCounter, StatusIndicator, SkeletonLoader
- **Molecules**: KPICard, AgentNode, DecisionCard, DeliveryTimelineStep, InventoryRow
- **Organisms**: Dashboard grid, Inventory table, Agent flowchart, KPI chart panel
- **Pages**: 9 route-level pages composing organisms with page-level animations

---

## 10. Azure Deployment Architecture

**Decision**: Deploy on Azure Container Apps with Azure Database for PostgreSQL Flexible Server, Azure Cache for Redis, and Azure Container Registry. Use Azure Bicep for infrastructure-as-code.

**Rationale**: Azure Container Apps provides serverless container hosting with built-in autoscaling, ingress, and revision management — ideal for the 4-container architecture (frontend, backend, celery worker, chromadb). It avoids the operational overhead of AKS while supporting custom containers, environment variables, and inter-service networking. Bicep templates enable repeatable deployment across environments.

**Alternatives Considered**:
- **Azure Kubernetes Service (AKS)**: Full Kubernetes is overkill for 4 containers at v1 scale.
- **Azure App Service**: Limited container orchestration, no sidecar support for ChromaDB.
- **Azure Functions**: Unsuitable for long-running WebSocket connections and Celery workers.

**Container Architecture**:
```
Azure Container Apps Environment
├── frontend (React/Nginx, min: 1, max: 3 replicas)
├── backend (FastAPI + Socket.IO, min: 1, max: 5 replicas)
├── celery-worker (Celery, min: 1, max: 3 replicas)
└── chromadb (ChromaDB server, 1 replica)

Azure Database for PostgreSQL Flexible Server (managed)
Azure Cache for Redis (managed, Premium tier for pub/sub)
Azure Container Registry (container images)
Azure Key Vault (secrets: API keys, SMTP credentials)
```

---

## 11. Security Practices

**Decision**: JWT-based authentication with httpOnly cookies, bcrypt password hashing, CORS whitelist, rate limiting, input validation via Pydantic, and secrets management via environment variables (Azure Key Vault in production).

**Rationale**: JWT in httpOnly cookies prevents XSS-based token theft. Bcrypt with work factor 12 provides adequate password security. Pydantic schemas validate all API inputs at the boundary. Rate limiting prevents brute-force attacks on auth endpoints.

**Key Measures**:
- Authentication: JWT tokens (30-min access, 7-day refresh) in httpOnly, Secure, SameSite=Strict cookies
- Password storage: bcrypt with work factor 12
- API input validation: Pydantic models on all endpoints
- CORS: Explicit origin whitelist (no wildcards in production)
- Rate limiting: 5 login attempts per minute per IP
- Secrets: Environment variables, Azure Key Vault in production
- WebSocket auth: JWT verification on connection handshake
- SMTP credentials: Encrypted at rest in PostgreSQL, loaded to env at runtime
