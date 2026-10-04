# Implementation Plan: AgenticInventory AI — Autonomous Procurement Platform

**Branch**: `feature/001-agentic-inventory-ai` | **Date**: 2026-05-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-agentic-inventory-ai/spec.md`

## Summary

Build a fully autonomous AI inventory procurement and forecasting platform that monitors inventory levels, predicts demand using external intelligence APIs (Google Trends, News, Weather, Holiday), makes confidence-scored ordering decisions, sends supplier purchase order emails, tracks deliveries, auto-updates inventory, and generates daily KPI reports — all orchestrated by 7 Microsoft AutoGen agents powered by Groq LLM inference. The platform features a premium futuristic SaaS UI with glassmorphism dark theme, real-time WebSocket updates, full undo/rollback support, and Azure-ready deployment architecture.

## Technical Context

**Language/Version**: Python 3.11+ (backend/AI), TypeScript 5.x (frontend)

**Primary Dependencies**:
- **Frontend**: React 18, Vite 5, Tailwind CSS 3, ShadCN UI, Framer Motion, Zustand, React Query (TanStack Query v5), Recharts, Socket.IO Client
- **Backend**: FastAPI 0.110+, Celery 5, Socket.IO (python-socketio), SQLAlchemy 2, Alembic, Jinja2 (email templates), aiosmtplib
- **AI/ML**: Microsoft AutoGen 0.4+, Groq Python SDK, ChromaDB

**Storage**: PostgreSQL 16 (persistent data), Redis 7 (caching, pub/sub, Celery broker, session store), ChromaDB (agent vector memory)

**Testing**: pytest + pytest-asyncio (backend), Vitest + React Testing Library (frontend), Playwright (E2E)

**Target Platform**: Linux containers (Docker), Azure Container Apps / Azure Kubernetes Service

**Project Type**: Full-stack web application (frontend + backend + AI agent services)

**Performance Goals**: <200ms API response p95, <5s real-time update latency, <2s page load, 60fps UI animations, full pipeline completion <2 minutes

**Constraints**: <500MB container memory per service, stateless backend services, horizontal scaling support, WebSocket persistence via Redis adapter

**Scale/Scope**: 50 concurrent users, 10,000 inventory items, 100 suppliers, 9 pages, 7 AI agents

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. AutoGen-Only Orchestration | ✅ PASS | All 7 agents use AutoGen. No alternative frameworks. |
| II. Groq-Exclusive LLM | ✅ PASS | Groq SDK configured as sole LLM provider for all agents. |
| III. Explainability & Reversibility | ✅ PASS | Every agent produces reasoning traces. Undo & Rollback Agent handles rollback for all actions. Audit trail maintained. |
| IV. UI/UX Excellence | ✅ PASS | Dark theme, glassmorphism, purple/pink gradients, Framer Motion animations, ShadCN UI, Recharts. Zepto/Stripe/Linear inspired. |
| V. Real-Time WebSockets | ✅ PASS | Socket.IO throughout. No polling. Reconnection + heartbeat + state resync. |
| VI. External Intelligence APIs | ✅ PASS | Google Trends, News API, Weather API, Holiday API integrated with caching and fallback. |
| VII. Delivery Simulation | ✅ PASS | Built-in simulation engine with configurable parameters (delays, partials, failures). |
| VIII. Reporting & Analytics | ✅ PASS | Interactive Recharts dashboards + daily KPI email reports. Real-time metric updates. |
| IX. Production-Grade Email | ✅ PASS | Celery-backed SMTP queue with retry logic, HTML templates, delivery tracking. |
| X. Clean Architecture & Azure | ✅ PASS | Domain-driven backend layers. Docker containers. Azure Container Apps deployment. |

**Gate Result**: ALL 10 PRINCIPLES PASS — proceeding to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/001-agentic-inventory-ai/
├── plan.md              # This file
├── research.md          # Phase 0: Technology decisions and research
├── data-model.md        # Phase 1: Database schema and entity relationships
├── quickstart.md        # Phase 1: Developer setup guide
├── contracts/           # Phase 1: API and WebSocket contracts
│   ├── rest-api.md      # REST API endpoint contracts
│   └── websocket.md     # WebSocket event contracts
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
├── frontend/                          # React + Vite + TypeScript
│   ├── public/
│   │   └── assets/                    # Static assets (logos, icons, fonts)
│   ├── src/
│   │   ├── app/                       # App shell, router, providers
│   │   │   ├── App.tsx
│   │   │   ├── router.tsx
│   │   │   └── providers.tsx
│   │   ├── components/                # Shared UI components
│   │   │   ├── ui/                    # ShadCN UI primitives
│   │   │   ├── layout/               # Shell, sidebar, header, footer
│   │   │   │   ├── AppShell.tsx
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   └── Header.tsx
│   │   │   ├── charts/               # Recharts wrappers (KPI, trends, etc.)
│   │   │   │   ├── KPICard.tsx
│   │   │   │   ├── TrendChart.tsx
│   │   │   │   ├── ConfidenceGauge.tsx
│   │   │   │   └── SupplierPerfChart.tsx
│   │   │   ├── agents/               # Agent workflow visualization components
│   │   │   │   ├── AgentFlowChart.tsx
│   │   │   │   ├── AgentNode.tsx
│   │   │   │   └── ReasoningTooltip.tsx
│   │   │   ├── inventory/            # Inventory-specific components
│   │   │   │   ├── InventoryTable.tsx
│   │   │   │   ├── StockLevelBadge.tsx
│   │   │   │   └── ReorderAlert.tsx
│   │   │   ├── decisions/            # Agent decision components
│   │   │   │   ├── DecisionCard.tsx
│   │   │   │   ├── ReasoningTrace.tsx
│   │   │   │   └── UndoButton.tsx
│   │   │   ├── delivery/             # Delivery tracking components
│   │   │   │   ├── DeliveryTimeline.tsx
│   │   │   │   └── DeliveryStatusBadge.tsx
│   │   │   └── common/               # Shared atoms (loaders, badges, etc.)
│   │   │       ├── GlassCard.tsx
│   │   │       ├── GradientButton.tsx
│   │   │       ├── AnimatedCounter.tsx
│   │   │       └── StatusIndicator.tsx
│   │   ├── pages/                     # Route-level page components
│   │   │   ├── LandingPage.tsx
│   │   │   ├── LoginPage.tsx
│   │   │   ├── RegisterPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── InventoryPage.tsx
│   │   │   ├── AgentDecisionsPage.tsx
│   │   │   ├── AnalyticsPage.tsx
│   │   │   ├── ReportsPage.tsx
│   │   │   ├── EmailSettingsPage.tsx
│   │   │   └── AgentWorkflowPage.tsx
│   │   ├── hooks/                     # Custom React hooks
│   │   │   ├── useWebSocket.ts
│   │   │   ├── useInventory.ts
│   │   │   ├── useAgentDecisions.ts
│   │   │   ├── useKPIMetrics.ts
│   │   │   └── useDeliveryTracking.ts
│   │   ├── stores/                    # Zustand state stores
│   │   │   ├── authStore.ts
│   │   │   ├── inventoryStore.ts
│   │   │   ├── agentStore.ts
│   │   │   ├── deliveryStore.ts
│   │   │   └── settingsStore.ts
│   │   ├── services/                  # API client and WebSocket service
│   │   │   ├── api.ts                 # Axios/fetch REST client
│   │   │   ├── socket.ts             # Socket.IO client singleton
│   │   │   └── queryKeys.ts          # React Query key constants
│   │   ├── lib/                       # Utilities, constants, types
│   │   │   ├── utils.ts
│   │   │   ├── constants.ts
│   │   │   └── animations.ts         # Framer Motion variant presets
│   │   ├── types/                     # TypeScript type definitions
│   │   │   ├── inventory.ts
│   │   │   ├── agent.ts
│   │   │   ├── delivery.ts
│   │   │   ├── report.ts
│   │   │   └── settings.ts
│   │   ├── styles/                    # Global styles and Tailwind config
│   │   │   └── globals.css
│   │   └── main.tsx                   # Entry point
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── Dockerfile
│
├── backend/                           # Python FastAPI + Celery
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app factory + Socket.IO mount
│   │   ├── config.py                  # Settings (Pydantic BaseSettings)
│   │   ├── database.py                # SQLAlchemy engine + session factory
│   │   ├── api/                       # REST API routes
│   │   │   ├── __init__.py
│   │   │   ├── deps.py                # Dependency injection (auth, db session)
│   │   │   ├── auth.py                # Login, register, session endpoints
│   │   │   ├── inventory.py           # Inventory CRUD endpoints
│   │   │   ├── agents.py              # Agent decision endpoints
│   │   │   ├── deliveries.py          # Delivery tracking endpoints
│   │   │   ├── reports.py             # KPI report endpoints
│   │   │   ├── settings.py            # Email/config settings endpoints
│   │   │   └── health.py              # Health check endpoint
│   │   ├── models/                    # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── inventory_item.py
│   │   │   ├── forecast.py
│   │   │   ├── agent_decision.py
│   │   │   ├── supplier_order.py
│   │   │   ├── delivery.py
│   │   │   ├── kpi_report.py
│   │   │   └── email_config.py
│   │   ├── schemas/                   # Pydantic request/response schemas
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── inventory.py
│   │   │   ├── agent.py
│   │   │   ├── delivery.py
│   │   │   ├── report.py
│   │   │   └── settings.py
│   │   ├── services/                  # Business logic layer
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── inventory_service.py
│   │   │   ├── forecast_service.py
│   │   │   ├── decision_service.py
│   │   │   ├── order_service.py
│   │   │   ├── delivery_service.py
│   │   │   ├── report_service.py
│   │   │   ├── email_service.py
│   │   │   └── rollback_service.py
│   │   ├── websocket/                 # Socket.IO event handlers
│   │   │   ├── __init__.py
│   │   │   ├── server.py              # Socket.IO server setup (Redis adapter)
│   │   │   ├── events.py              # Event handlers (inventory, agents, etc.)
│   │   │   └── middleware.py          # WS auth middleware
│   │   ├── agents/                    # AutoGen agent definitions
│   │   │   ├── __init__.py
│   │   │   ├── config.py              # Groq LLM config for AutoGen
│   │   │   ├── orchestrator.py        # AutoGen GroupChat / pipeline orchestrator
│   │   │   ├── inventory_monitor.py   # Inventory Monitoring Agent
│   │   │   ├── demand_forecast.py     # Intelligent Demand Forecast Agent
│   │   │   ├── decision_manager.py    # Decision Manager Agent
│   │   │   ├── supplier_email.py      # Supplier Email Agent
│   │   │   ├── delivery_tracker.py    # Delivery Tracking Agent
│   │   │   ├── undo_rollback.py       # Undo & Rollback Agent
│   │   │   └── reporting_kpi.py       # Reporting & KPI Agent
│   │   ├── intelligence/              # External API integration services
│   │   │   ├── __init__.py
│   │   │   ├── google_trends.py
│   │   │   ├── news_api.py
│   │   │   ├── weather_api.py
│   │   │   ├── holiday_api.py
│   │   │   └── aggregator.py          # Combines all intelligence signals
│   │   ├── email/                     # Email system
│   │   │   ├── __init__.py
│   │   │   ├── smtp_client.py         # Async SMTP client with retry logic
│   │   │   ├── templates/             # Jinja2 HTML email templates
│   │   │   │   ├── purchase_order.html
│   │   │   │   ├── cancellation.html
│   │   │   │   ├── kpi_report.html
│   │   │   │   └── admin_notification.html
│   │   │   └── renderer.py            # Template rendering engine
│   │   ├── simulation/                # Delivery simulation engine
│   │   │   ├── __init__.py
│   │   │   ├── engine.py              # Simulation state machine
│   │   │   └── scenarios.py           # Configurable simulation parameters
│   │   ├── memory/                    # ChromaDB agent memory
│   │   │   ├── __init__.py
│   │   │   └── vector_store.py        # ChromaDB client + collection management
│   │   └── core/                      # Cross-cutting concerns
│   │       ├── __init__.py
│   │       ├── security.py            # Password hashing, JWT tokens
│   │       ├── exceptions.py          # Custom exception classes
│   │       └── logging.py             # Structured logging setup
│   ├── celery_app/                    # Celery worker configuration
│   │   ├── __init__.py
│   │   ├── worker.py                  # Celery app factory
│   │   └── tasks/                     # Celery task definitions
│   │       ├── __init__.py
│   │       ├── email_tasks.py         # Send email, retry, track delivery
│   │       ├── report_tasks.py        # Daily KPI report generation
│   │       ├── monitoring_tasks.py    # Periodic inventory monitoring
│   │       └── simulation_tasks.py    # Delivery simulation progression
│   ├── migrations/                    # Alembic database migrations
│   │   ├── env.py
│   │   └── versions/
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── unit/
│   │   ├── integration/
│   │   └── contract/
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── Dockerfile
│
├── infrastructure/                    # Azure deployment & Docker
│   ├── docker/
│   │   └── docker-compose.yml         # Local dev: PostgreSQL, Redis, ChromaDB
│   ├── azure/
│   │   ├── bicep/                     # Azure Bicep IaC templates
│   │   │   ├── main.bicep
│   │   │   ├── container-apps.bicep
│   │   │   ├── database.bicep
│   │   │   ├── redis.bicep
│   │   │   └── parameters.json
│   │   └── pipelines/
│   │       └── azure-pipelines.yml    # CI/CD pipeline
│   └── nginx/
│       └── nginx.conf                 # Reverse proxy config
│
├── .env.example                       # Environment variable template
├── .gitignore
├── README.md
└── Makefile                           # Dev commands (make dev, make test, etc.)
```

**Structure Decision**: Web application pattern (Option 2 expanded) — separate `frontend/` and `backend/` directories with shared `infrastructure/` for deployment. The backend further separates `agents/`, `intelligence/`, `email/`, `simulation/`, and `memory/` as distinct domain modules within the clean architecture. Celery workers live in `celery_app/` alongside the main FastAPI app to share models and services.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| 7 AI agent modules | Each agent has distinct responsibilities, LLM prompts, and I/O contracts that require isolation | A monolithic agent would violate AutoGen's multi-agent design pattern and make reasoning traces unattributable |
| ChromaDB alongside PostgreSQL + Redis | Vector memory for agent context retrieval is semantically different from structured data (PostgreSQL) and ephemeral cache (Redis) | Storing embeddings in PostgreSQL with pgvector would couple AI concerns to the relational schema and complicate migrations |
| Celery worker process | Email retry, scheduled reports, and simulation progression require persistent background task execution with guaranteed delivery | In-process async tasks would be lost on server restart and cannot scale independently |
