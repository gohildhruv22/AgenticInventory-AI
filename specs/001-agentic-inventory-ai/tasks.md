# Tasks: AgenticInventory AI — Autonomous Procurement Platform

**Input**: Design documents from `specs/001-agentic-inventory-ai/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Frontend**: `frontend/src/`
- **Backend**: `backend/app/`
- **Infrastructure**: `infrastructure/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, tooling, and dependency installation

- [x] T001 Create root project structure with frontend/, backend/, infrastructure/ directories and root files (.env.example, .gitignore, Makefile, README.md)
- [x] T002 Initialize frontend React project with Vite 5, TypeScript, and package.json in frontend/
- [x] T003 [P] Install frontend dependencies (React 18, Tailwind CSS 3, ShadCN UI, Framer Motion, Zustand, TanStack Query v5, Recharts, Socket.IO Client, React Router) in frontend/package.json
- [x] T004 [P] Configure Tailwind CSS with custom dark theme design tokens (colors, gradients, glassmorphism utilities) in frontend/tailwind.config.ts
- [x] T005 [P] Create global CSS with dark theme base styles, glassmorphism classes, gradient utilities, and premium typography in frontend/src/styles/globals.css
- [x] T006 [P] Create Framer Motion animation preset library (fadeInUp, scaleIn, slideInLeft, pulseGlow, staggerChildren) in frontend/src/lib/animations.ts
- [x] T007 Initialize backend Python project with pyproject.toml and requirements.txt (FastAPI, SQLAlchemy 2, Alembic, Celery, python-socketio, autogen, groq, chromadb, aiosmtplib, Jinja2, bcrypt, PyJWT, httpx, pytrends) in backend/
- [x] T008 [P] Create backend config module with Pydantic BaseSettings for all env vars (database, redis, groq, smtp, external APIs) in backend/app/config.py
- [x] T009 [P] Create docker-compose.yml with PostgreSQL 16, Redis 7, and ChromaDB services for local development in infrastructure/docker/docker-compose.yml
- [x] T010 Configure Vite dev server with proxy to backend API and HMR in frontend/vite.config.ts

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T011 Create SQLAlchemy 2 async engine and session factory with PostgreSQL connection in backend/app/database.py
- [x] T012 [P] Create User ORM model with UUID PK, email, password_hash, name, role, is_active, timestamps in backend/app/models/user.py
- [x] T013 [P] Create InventoryItem ORM model with all fields per data-model.md (sku, category, current_stock, reorder_threshold, safety_stock, lead_time_days, unit_cost, supplier_email, is_active) in backend/app/models/inventory_item.py
- [x] T014 [P] Create Forecast ORM model with all intelligence signal fields per data-model.md in backend/app/models/forecast.py
- [x] T015 [P] Create AgentDecision ORM model with reasoning_trace JSONB, alternatives_considered, status fields in backend/app/models/agent_decision.py
- [x] T016 [P] Create SupplierOrder ORM model with items JSONB, email_status, retry tracking fields in backend/app/models/supplier_order.py
- [x] T017 [P] Create Delivery ORM model with stage_history JSONB, simulation_config, state machine stages in backend/app/models/delivery.py
- [x] T018 [P] Create ActionLog ORM model with before_state/after_state JSONB, compensating_action, rollback tracking in backend/app/models/action_log.py
- [x] T019 [P] Create KPIReport ORM model with all metrics fields, supplier_performance JSONB, report_data JSONB in backend/app/models/kpi_report.py
- [x] T020 [P] Create EmailConfiguration ORM model with SMTP settings, supplier_mappings JSONB, confidence_threshold in backend/app/models/email_config.py
- [x] T021 Create models __init__.py exporting all models and Base for Alembic discovery in backend/app/models/__init__.py
- [x] T022 Configure Alembic with async PostgreSQL support and generate initial migration for all 9 tables in backend/migrations/
- [x] T023 [P] Create Pydantic schemas for auth (register, login, user response) in backend/app/schemas/auth.py
- [x] T024 [P] Create Pydantic schemas for inventory (create, update, list response with pagination) in backend/app/schemas/inventory.py
- [x] T025 [P] Create Pydantic schemas for agent decisions (decision response, reasoning trace, undo response) in backend/app/schemas/agent.py
- [x] T026 [P] Create Pydantic schemas for deliveries (delivery response, stage history) in backend/app/schemas/delivery.py
- [x] T027 [P] Create Pydantic schemas for reports (KPI report response, dashboard metrics) in backend/app/schemas/report.py
- [x] T028 [P] Create Pydantic schemas for settings (email config create/update, supplier mappings) in backend/app/schemas/settings.py
- [x] T029 Create security module with bcrypt password hashing, JWT token creation/verification (access + refresh), httpOnly cookie helpers in backend/app/core/security.py
- [x] T030 [P] Create custom exception classes (NotFound, Unauthorized, Conflict, ValidationError) with FastAPI exception handlers in backend/app/core/exceptions.py
- [x] T031 [P] Create structured logging setup with JSON formatter and request correlation IDs in backend/app/core/logging.py
- [x] T032 Create API dependency injection module (get_db_session, get_current_user, require_admin) in backend/app/api/deps.py
- [x] T033 Create FastAPI app factory with CORS, exception handlers, router includes, and native WebSocket endpoint in backend/app/main.py
- [x] T034 Create health check endpoint verifying database and Redis connectivity in backend/app/api/health.py
- [ ] T035 Create Celery app factory with Redis broker, beat schedule configuration in backend/celery_app/worker.py
- [ ] T036 [P] Create Redis connection helper for caching, pub/sub, and Socket.IO adapter in backend/app/config.py
- [ ] T037 [P] Create ChromaDB client and collection management (agent_decisions, forecast_history, inventory_patterns) in backend/app/memory/vector_store.py
- [ ] T038 [P] Create TypeScript type definitions for inventory, agent, delivery, report, settings matching Pydantic schemas in frontend/src/types/
- [ ] T039 [P] Create REST API client with fetch/axios, auth cookie handling, error interceptor in frontend/src/services/api.ts
- [ ] T040 [P] Create React Query key constants for all entity types in frontend/src/services/queryKeys.ts
- [ ] T041 [P] Create utility functions (formatCurrency, formatDate, cn class merger, debounce) in frontend/src/lib/utils.ts
- [ ] T042 [P] Create app constants (API_BASE_URL, WS_URL, agent types enum, delivery stages enum, status colors) in frontend/src/lib/constants.ts

**Checkpoint**: Foundation ready — all models, schemas, auth, config, and client utilities are in place. User story implementation can now begin in parallel.

---

## Phase 3: User Story 1 — Real-Time Inventory Monitoring & Autonomous Reorder (Priority: P1) 🎯 MVP

**Goal**: Complete autonomous pipeline: inventory monitoring → demand forecast → decision → supplier email. The core value proposition of the platform.

**Independent Test**: Seed inventory data, lower a product's stock below threshold, verify the system autonomously detects, forecasts, decides, and emails — all visible in the UI with reasoning traces.

### Backend — Agent Orchestration & Pipeline (US1)

- [x] T043 [US1] Create Groq LLM config for AutoGen with primary (llama-3.3-70b-versatile) and lightweight (llama-3.1-8b-instant) model configs in backend/app/agents/config.py
- [x] T044 [US1] Create Inventory Monitoring Agent (AutoGen AssistantAgent) with system prompt for stock level analysis, threshold detection, and reasoning trace output in backend/app/agents/inventory_monitor.py
- [x] T045 [US1] Create Intelligent Demand Forecast Agent (AutoGen AssistantAgent) with system prompt for multi-signal analysis, confidence scoring, order quantity suggestion, and explainable reasoning in backend/app/agents/demand_forecast.py
- [x] T046 [US1] Create Decision Manager Agent (AutoGen AssistantAgent) with system prompt for threshold evaluation, approval/flagging logic, alternatives consideration, and full reasoning trace in backend/app/agents/decision_manager.py
- [x] T047 [US1] Create Supplier Email Agent (AutoGen AssistantAgent) with system prompt for email composition, category-based supplier lookup, and order formatting in backend/app/agents/supplier_email.py
- [ ] T048 [US1] Create AutoGen GroupChat orchestrator with custom pipeline speaker selector (monitor → forecast → decision → email), max_round config, and pipeline state tracking in backend/app/agents/orchestrator.py

### Backend — Intelligence APIs (US1)

- [x] T049 [P] [US1] Create Google Trends integration service with pytrends, async execution, Redis caching (30min TTL), and fallback in backend/app/intelligence/google_trends.py
- [x] T050 [P] [US1] Create News API integration service with httpx, category-filtered search, sentiment extraction, Redis caching (30min TTL), and fallback in backend/app/intelligence/news_api.py
- [x] T051 [P] [US1] Create Weather API integration service (OpenWeatherMap) with location-based forecast, disruption risk scoring, Redis caching (60min TTL), and fallback in backend/app/intelligence/weather_api.py
- [x] T052 [P] [US1] Create Holiday API integration service (Calendarific) with proximity calculation, Redis caching (24hr TTL), and static calendar fallback in backend/app/intelligence/holiday_api.py
- [x] T053 [US1] Create IntelligenceAggregator that queries all 4 APIs concurrently via asyncio.gather, merges into unified IntelligenceSignals payload, handles partial failures in backend/app/intelligence/aggregator.py

### Backend — Services & API (US1)

- [x] T054 [US1] Create inventory service with CRUD operations, stock level change detection, threshold breach check, batch category queries in backend/app/services/inventory_service.py
- [x] T055 [US1] Create forecast service that invokes IntelligenceAggregator, passes signals to Demand Forecast Agent, persists Forecast record with all signal fields in backend/app/services/forecast_service.py
- [x] T056 [US1] Create decision service that invokes Decision Manager Agent, creates AgentDecision record with reasoning trace, handles approve/flag logic in backend/app/services/decision_service.py
- [x] T057 [US1] Create order service that creates SupplierOrder from approved decision, resolves supplier email from category mapping, queues email task in backend/app/services/order_service.py
- [x] T058 [US1] Create inventory API endpoints (GET list with filtering/pagination/search, GET single with latest forecast, POST create, PATCH update, DELETE soft-delete, POST seed) per rest-api.md contract in backend/app/api/inventory.py
- [ ] T059 [US1] Create agent decisions API endpoints (GET list with filtering, GET single with expanded relations, POST trigger pipeline) per rest-api.md contract in backend/app/api/agents.py
- [x] T060 [US1] Create Celery periodic monitoring task that checks all active inventory items every 60 seconds, triggers pipeline for threshold breaches in backend/celery_app/tasks/monitoring_tasks.py
- [x] T061 [US1] Create demo data seed script with 25 inventory items across 5 categories, realistic stock levels, thresholds, and supplier mappings in backend/app/seed.py

### Backend — WebSocket (US1)

- [ ] T062 [US1] Create Socket.IO server setup with async mode, Redis adapter for horizontal scaling, CORS config in backend/app/websocket/server.py
- [ ] T063 [P] [US1] Create WebSocket auth middleware that validates JWT token on connection handshake in backend/app/websocket/middleware.py
- [ ] T064 [US1] Create WebSocket event emitters for inventory:update, agent:status, agent:decision, agent:reasoning, pipeline:progress per websocket.md contract in backend/app/websocket/events.py

### Frontend — Core Layout & Navigation (US1)

- [x] T065 [US1] Create AppShell layout with animated sidebar, glassmorphism header, page transition wrapper using Framer Motion in frontend/src/components/layout/AppShell.tsx
- [x] T066 [P] [US1] Create Sidebar navigation with gradient active indicator, icon animations, route links to all 9 pages, collapse/expand in frontend/src/components/layout/Sidebar.tsx
- [x] T067 [P] [US1] Create Header with user avatar, notification bell with pulse animation, breadcrumb, glassmorphism background in frontend/src/components/layout/Header.tsx
- [x] T068 [US1] Create React Router configuration with protected routes, auth guard, page-level code splitting in frontend/src/app/router.tsx
- [x] T069 [US1] Create providers wrapper with QueryClientProvider, Zustand stores, Socket.IO context in frontend/src/app/providers.tsx
- [x] T070 [US1] Create App.tsx entry component composing providers, router, and global animation layout in frontend/src/app/App.tsx

### Frontend — Design System Atoms (US1)

- [x] T071 [P] [US1] Create GlassCard component with backdrop-blur, glass border, hover glow effect, Framer Motion entrance animation in frontend/src/components/common/GlassCard.tsx
- [x] T072 [P] [US1] Create GradientButton component with purple-to-pink gradient, hover scale, loading spinner, disabled state in frontend/src/components/common/GradientButton.tsx
- [x] T073 [P] [US1] Create AnimatedCounter component with number spring animation using Framer Motion useSpring for KPI values in frontend/src/components/common/AnimatedCounter.tsx
- [x] T074 [P] [US1] Create StatusIndicator component with pulsing dot, color-coded status (success/warning/error/processing), label in frontend/src/components/common/StatusIndicator.tsx

### Frontend — WebSocket & State (US1)

- [x] T075 [US1] Create Socket.IO client singleton with auth token, auto-reconnection (exponential backoff), reconnecting indicator, state resync on reconnect in frontend/src/services/socket.ts
- [x] T076 [US1] Create useWebSocket hook that subscribes to Socket.IO events, updates Zustand stores on incoming data, handles connection status in frontend/src/hooks/useWebSocket.ts
- [x] T077 [P] [US1] Create inventoryStore (Zustand) with items map, real-time update handler, optimistic updates, filtering state in frontend/src/stores/inventoryStore.ts
- [x] T078 [P] [US1] Create agentStore (Zustand) with decisions list, pipeline status, active agent tracking, reasoning cache in frontend/src/stores/agentStore.ts

### Frontend — Dashboard Page (US1)

- [x] T079 [US1] Create KPICard component with glassmorphism, animated value counter, trend indicator arrow, sparkline mini-chart in frontend/src/components/charts/KPICard.tsx
- [x] T080 [US1] Create DashboardPage with KPI card grid (order volume, total spend, forecast accuracy, active deliveries, low stock count), recent decisions feed, inventory alerts section in frontend/src/pages/DashboardPage.tsx
- [x] T081 [US1] Create useKPIMetrics hook with React Query for initial load and WebSocket for real-time updates in frontend/src/hooks/useKPIMetrics.ts

### Frontend — Inventory Page (US1)

- [x] T082 [US1] Create InventoryTable with sortable columns, search, category filter, status badge, real-time stock level updates via WebSocket in frontend/src/components/inventory/InventoryTable.tsx
- [x] T083 [P] [US1] Create StockLevelBadge with color-coded status (normal=green, low=amber, out=red, pending=purple), animated transitions on stock changes in frontend/src/components/inventory/StockLevelBadge.tsx
- [x] T084 [P] [US1] Create ReorderAlert component with sliding notification when threshold breach detected, showing item name and agent status in frontend/src/components/inventory/ReorderAlert.tsx
- [x] T085 [US1] Create InventoryPage composing InventoryTable, filters, add item dialog, with Framer Motion stagger animations in frontend/src/pages/InventoryPage.tsx
- [x] T086 [US1] Create useInventory hook with React Query for CRUD operations and WebSocket subscription for real-time updates in frontend/src/hooks/useInventory.ts

### Frontend — Agent Decisions Page (US1)

- [x] T087 [US1] Create DecisionCard with glassmorphism, agent type icon, action summary, confidence gauge, status badge, expandable reasoning trace, timestamp in frontend/src/components/decisions/DecisionCard.tsx
- [x] T088 [P] [US1] Create ReasoningTrace component with collapsible JSON tree, syntax highlighting, input/rationale/confidence/alternatives sections in frontend/src/components/decisions/ReasoningTrace.tsx
- [x] T089 [US1] Create AgentDecisionsPage with filterable decision feed (by agent type, status, date range), infinite scroll, real-time new decision notifications in frontend/src/pages/AgentDecisionsPage.tsx
- [x] T090 [US1] Create useAgentDecisions hook with React Query for paginated fetch and WebSocket subscription for live decisions in frontend/src/hooks/useAgentDecisions.ts

**Checkpoint**: At this point, the full autonomous pipeline (monitoring → forecast → decision → email) is functional and visible in the UI. User Story 1 is independently testable as an MVP.

---

## Phase 4: User Story 2 — Undo & Rollback for Autonomous Actions (Priority: P2)

**Goal**: Full undo/rollback capability for all autonomous actions with audit trail and real-time UI feedback.

**Independent Test**: Trigger a reorder via US1, then undo from Agent Decisions page. Verify inventory, orders, and email logs revert. Verify audit trail.

### Backend — Rollback System (US2)

- [x] T091 [US2] Create rollback service with action log querying, reverse-chronological compensating action execution, state restoration, audit trail recording in backend/app/services/rollback_service.py
- [x] T092 [US2] Create Undo & Rollback Agent (AutoGen AssistantAgent) with system prompt for analyzing action dependencies, determining reversibility, executing compensating actions, and explaining what was rolled back in backend/app/agents/undo_rollback.py
- [x] T093 [US2] Integrate ActionLog creation into inventory_service, order_service, and delivery_service — every state mutation records before_state, after_state, and compensating_action in backend/app/services/
- [x] T094 [US2] Add POST /decisions/{id}/undo endpoint that invokes Undo Agent, returns rollback summary with all reversed actions per rest-api.md contract in backend/app/api/agents.py
- [x] T095 [US2] Create WebSocket rollback:progress event emitter for real-time undo progress streaming (actions_total, actions_completed, current_action) in backend/app/websocket/events.py

### Frontend — Undo UI (US2)

- [x] T096 [US2] Create UndoButton component with confirmation dialog, loading state, progress indicator, success/error feedback animation in frontend/src/components/decisions/UndoButton.tsx
- [x] T097 [US2] Add undo functionality to AgentDecisionsPage — UndoButton on each decision card, real-time rollback progress via WebSocket, status transition animation (executed → rolling_back → rolled_back) in frontend/src/pages/AgentDecisionsPage.tsx
- [x] T098 [US2] Create rollback audit trail view within DecisionCard showing reversed actions, timestamps, and restored values when status is "rolled_back" in frontend/src/components/decisions/DecisionCard.tsx

**Checkpoint**: All autonomous actions support undo. Rollback is visible in real time with full audit trail. US2 is independently testable.

---

## Phase 5: User Story 3 — Analytics Dashboard & Daily KPI Reports (Priority: P3)

**Goal**: Interactive analytics dashboard with real-time charts and automated daily KPI email reports.

**Independent Test**: Run system with multiple agent decisions, verify dashboard charts display accurate data. Verify daily email report sends on schedule.

### Backend — Reporting System (US3)

- [x] T099 [US3] Create report service that aggregates daily KPI metrics (order volume, forecast accuracy, cost savings, decision distribution, supplier performance) from database in backend/app/services/report_service.py
- [x] T100 [US3] Create Reporting & KPI Agent (AutoGen AssistantAgent) with system prompt for generating natural-language KPI summaries, trend analysis, and recommendations in backend/app/agents/reporting_kpi.py
- [x] T101 [US3] Create KPI report API endpoints (GET list with date filtering, GET single with full data, GET /reports/dashboard for real-time running totals) per rest-api.md in backend/app/api/reports.py
- [x] T102 [US3] Create Jinja2 HTML email template for KPI report with dark theme, inline charts (base64 encoded), gradient header, branded footer in backend/app/email/templates/kpi_report.html
- [x] T103 [US3] Create Celery scheduled task for daily KPI report generation and email dispatch at configurable time in backend/celery_app/tasks/report_tasks.py
- [x] T104 [US3] Create WebSocket kpi:update event emission on every metric change (decision created, delivery completed, etc.) in backend/app/websocket/events.py

### Frontend — Analytics & Reports (US3)

- [x] T105 [P] [US3] Create TrendChart component (Recharts AreaChart) with gradient fill, animated data transitions, tooltips, responsive sizing in frontend/src/components/charts/TrendChart.tsx
- [x] T106 [P] [US3] Create ConfidenceGauge component (Recharts RadialBarChart) with purple-to-pink gradient arc, animated value, center label in frontend/src/components/charts/ConfidenceGauge.tsx
- [x] T107 [P] [US3] Create SupplierPerfChart component (Recharts BarChart) with grouped bars, gradient fills, interactive tooltips, legend in frontend/src/components/charts/SupplierPerfChart.tsx
- [x] T108 [US3] Create AnalyticsPage with KPI card row, order volume trend (7-day), forecast accuracy trend, agent activity distribution (pie chart), supplier performance comparison, cost savings tracker in frontend/src/pages/AnalyticsPage.tsx
- [x] T109 [US3] Create ReportsPage with daily report list, expandable report detail view with charts, email delivery status badge, date range picker in frontend/src/pages/ReportsPage.tsx

**Checkpoint**: Analytics dashboard shows real-time KPIs with interactive charts. Daily reports auto-generate and email. US3 independently testable.

---

## Phase 6: User Story 4 — Delivery Tracking & Inventory Auto-Update (Priority: P4)

**Goal**: Delivery simulation engine, real-time tracking UI, and automatic inventory update on receipt.

**Independent Test**: Trigger reorder, observe delivery stages progressing in real time, verify inventory auto-updates on delivery confirmation.

### Backend — Delivery Simulation (US4)

- [ ] T110 [US4] Create delivery simulation state machine engine with configurable stage transitions, timing parameters, probability settings (delivery success, partial delivery) in backend/app/simulation/engine.py
- [ ] T111 [P] [US4] Create simulation scenario configurations (standard delivery, delayed delivery, partial delivery, failed delivery) with adjustable parameters in backend/app/simulation/scenarios.py
- [ ] T112 [US4] Create Delivery Tracking Agent (AutoGen AssistantAgent) with system prompt for monitoring delivery progress, processing receipts, triggering inventory updates, and explaining delivery status in backend/app/agents/delivery_tracker.py
- [ ] T113 [US4] Create delivery service with delivery creation on order placement, stage transition processing, inventory auto-update on receipt, partial delivery handling in backend/app/services/delivery_service.py
- [ ] T114 [US4] Create Celery periodic task for delivery simulation progression — advances each active delivery to next stage based on timing config in backend/celery_app/tasks/simulation_tasks.py
- [ ] T115 [US4] Create delivery API endpoints (GET list with stage filtering, GET single with full history) per rest-api.md in backend/app/api/deliveries.py
- [ ] T116 [US4] Create WebSocket delivery:update event emission on every stage transition with stage, timestamp, and order details in backend/app/websocket/events.py

### Frontend — Delivery Tracking UI (US4)

- [ ] T117 [P] [US4] Create DeliveryTimeline component with vertical timeline, stage icons, animated progress connector, active stage pulse, timestamps in frontend/src/components/delivery/DeliveryTimeline.tsx
- [ ] T118 [P] [US4] Create DeliveryStatusBadge with stage-specific colors and icons, animated transition on stage change in frontend/src/components/delivery/DeliveryStatusBadge.tsx
- [ ] T119 [US4] Add delivery tracking section to DashboardPage showing active deliveries count, latest delivery updates feed in frontend/src/pages/DashboardPage.tsx
- [ ] T120 [US4] Create deliveryStore (Zustand) with active deliveries, stage update handler, delivery history in frontend/src/stores/deliveryStore.ts
- [ ] T121 [US4] Create useDeliveryTracking hook with React Query for delivery list and WebSocket subscription for real-time stage updates in frontend/src/hooks/useDeliveryTracking.ts

**Checkpoint**: Delivery simulation runs autonomously. Stages appear in real time. Inventory auto-updates on receipt. US4 independently testable.

---

## Phase 7: User Story 5 — Premium UI/UX with Agent Workflow Visualization (Priority: P5)

**Goal**: All 9 pages meet premium design bar. Agent Workflow Visualization page shows live animated pipeline.

**Independent Test**: Navigate all 9 pages. Verify dark theme, glassmorphism, gradients, animations, responsive layout. Verify workflow viz shows live pipeline with reasoning.

### Frontend — Agent Workflow Visualization (US5)

- [x] T122 [US5] Create AgentNode component with glassmorphism card, agent icon, name, status indicator, pulsing glow animation when active, idle/processing/completed/error states in frontend/src/components/agents/AgentNode.tsx
- [x] T123 [P] [US5] Create ReasoningTooltip component with hover-triggered popover showing agent's latest reasoning summary, confidence score, key data points in frontend/src/components/agents/ReasoningTooltip.tsx
- [x] T124 [US5] Create AgentFlowChart component with 7 connected agent nodes in pipeline layout (horizontal flow with animated connection lines), real-time status from pipeline:progress WebSocket events, active node pulsing in frontend/src/components/agents/AgentFlowChart.tsx
- [x] T125 [US5] Create AgentWorkflowPage composing AgentFlowChart, live pipeline activity feed, pipeline trigger button for demos, pipeline history list in frontend/src/pages/AgentWorkflowPage.tsx

### Frontend — Landing Page (US5)

- [x] T126 [US5] Create LandingPage with animated hero section (gradient text, floating glassmorphism cards, particle background effect), feature showcase grid with Framer Motion stagger, CTA buttons with gradient hover in frontend/src/pages/LandingPage.tsx

### Frontend — Polish & Animations (US5)

- [x] T127 [US5] Add page transition animations using Framer Motion AnimatePresence with fadeInUp variants on all route changes in frontend/src/app/router.tsx
- [x] T128 [US5] Add micro-interactions to all interactive elements — button hover scales, card hover lifts, tab switch slides, dialog backdrop blur, toast slide-in in frontend/src/components/
- [x] T129 [US5] Add skeleton loading states with shimmer animation (glassmorphism-styled) for all data-dependent components (tables, charts, cards) in frontend/src/components/common/
- [x] T130 [US5] Add real-time chart animation — smooth data point transitions using Recharts animationDuration, animated axis labels, tooltip fade-in across all chart components in frontend/src/components/charts/
- [x] T131 [US5] Create WebSocket reconnecting overlay with animated spinner, "Reconnecting..." message, gradient border pulse in frontend/src/components/common/

**Checkpoint**: All pages meet premium design standard. Agent workflow visualization shows live pipeline. Platform is demo-ready. US5 independently testable.

---

## Phase 8: User Story 6 — Authentication & Email Configuration (Priority: P6)

**Goal**: Secure auth flow, email settings configuration, and supplier email mapping per category.

**Independent Test**: Register, login, configure SMTP and supplier mappings, verify next reorder uses configured settings.

### Backend — Auth & Settings (US6)

- [x] T132 [US6] Create auth service with register (bcrypt hash + user creation), login (credential verification + JWT cookie set), logout (cookie clear), get_current_user in backend/app/services/auth_service.py
- [x] T133 [US6] Create auth API endpoints (POST register, POST login, POST logout, GET me) with httpOnly cookie management, rate limiting on login per rest-api.md in backend/app/api/auth.py
- [x] T134 [US6] Create email service with SMTP config loading, connection validation (test email), encrypted password storage in backend/app/services/email_service.py
- [x] T135 [US6] Create settings API endpoints (GET email config, PUT email config, POST test email) per rest-api.md in backend/app/api/settings.py

### Backend — SMTP Email Queue (US6)

- [x] T136 [US6] Create async SMTP client with aiosmtplib, TLS support, connection pooling, timeout handling in backend/app/email/smtp_client.py
- [x] T137 [P] [US6] Create Jinja2 email template renderer with base dark-theme layout, purchase order template, cancellation template, admin notification template in backend/app/email/renderer.py and backend/app/email/templates/
- [x] T138 [US6] Create Celery email tasks with send_email (SMTP send + status recording), retry logic (3 attempts, exponential backoff 30s/120s/480s), failure notification in backend/celery_app/tasks/email_tasks.py

### Frontend — Auth & Settings (US6)

- [x] T139 [P] [US6] Create authStore (Zustand) with user state, login/logout actions, token refresh, isAuthenticated computed in frontend/src/stores/authStore.ts
- [x] T140 [P] [US6] Create settingsStore (Zustand) with email config state, supplier mappings, confidence threshold in frontend/src/stores/settingsStore.ts
- [x] T141 [US6] Create LoginPage with glassmorphism card form, gradient CTA button, email/password validation, error display, animated entrance in frontend/src/pages/LoginPage.tsx
- [x] T142 [P] [US6] Create RegisterPage with glassmorphism card form, name/email/password fields, password strength indicator, animated entrance in frontend/src/pages/RegisterPage.tsx
- [x] T143 [US6] Create EmailSettingsPage with SMTP config form, supplier email mapping editor (add/edit/delete by category), confidence threshold slider, daily report toggle with time picker, test email button with result feedback in frontend/src/pages/EmailSettingsPage.tsx

**Checkpoint**: Full auth flow works. Email settings configurable. SMTP queue processes emails with retry. US6 independently testable.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Integration testing, deployment readiness, performance optimization, and final polish

### Infrastructure & Deployment

- [ ] T144 Create backend Dockerfile with multi-stage build (deps → app), non-root user, health check in backend/Dockerfile
- [ ] T145 [P] Create frontend Dockerfile with multi-stage build (deps → build → nginx serve), gzip compression in frontend/Dockerfile
- [ ] T146 [P] Create nginx reverse proxy config for frontend static serving, API proxying, WebSocket upgrade handling in infrastructure/nginx/nginx.conf
- [ ] T147 Update docker-compose.yml to include frontend, backend, celery-worker, and nginx services alongside PostgreSQL, Redis, ChromaDB for full local stack in infrastructure/docker/docker-compose.yml
- [ ] T148 [P] Create Azure Bicep main template orchestrating container apps environment, database, redis, and container registry in infrastructure/azure/bicep/main.bicep
- [ ] T149 [P] Create Azure Bicep module for Container Apps (frontend, backend, celery-worker, chromadb) with scaling rules, env vars, secrets in infrastructure/azure/bicep/container-apps.bicep
- [ ] T150 [P] Create Azure Bicep module for PostgreSQL Flexible Server with firewall rules, SSL, backup in infrastructure/azure/bicep/database.bicep
- [ ] T151 [P] Create Azure Bicep module for Azure Cache for Redis Premium with pub/sub support in infrastructure/azure/bicep/redis.bicep
- [ ] T152 Create Azure Pipelines CI/CD YAML with build, test, Docker push, and Bicep deploy stages in infrastructure/azure/pipelines/azure-pipelines.yml

### Demo & Seed Data

- [x] T153 Create pipeline manual trigger endpoint (POST /pipeline/trigger with inventory_item_id) and GET /pipeline/{id}/status for live demos per rest-api.md in backend/app/api/agents.py
- [x] T154 Enhance seed script with realistic demo scenario: 25 items across 5 categories (Electronics, Office Supplies, Raw Materials, Food & Beverage, Cleaning Supplies), 3 items already below threshold for immediate pipeline trigger in backend/app/seed.py
- [x] T155 Add notification system (WebSocket notification event) with toast UI component for admin alerts (SMTP failures, stale data warnings, delivery failures) in frontend/src/components/common/ and backend/app/websocket/events.py

### Final Integration & Makefile

- [x] T156 Create Makefile with dev (docker-up + backend + frontend), test (pytest + vitest), lint, migrate, seed, docker-up, docker-down, build, deploy commands in Makefile
- [x] T157 Create comprehensive .env.example with all required and optional environment variables, comments, and defaults in .env.example
- [x] T158 Create README.md with project overview, architecture diagram (text), setup instructions, tech stack badges, and demo instructions in README.md

---

## Dependencies

```
Phase 1 (Setup)
  └──> Phase 2 (Foundational)
         └──> Phase 3 (US1: Core Pipeline) 🎯 MVP
         │      └──> Phase 4 (US2: Undo/Rollback)
         │      └──> Phase 5 (US3: Analytics/Reports)
         │      └──> Phase 6 (US4: Delivery Tracking)
         │      └──> Phase 7 (US5: Premium UI/Workflow Viz)
         │      └──> Phase 8 (US6: Auth/Email Config)
         └──> Phase 9 (Polish & Deployment)
```

**Key Dependency Rules**:
- Phases 4-8 can ALL proceed in parallel after Phase 3 is complete
- Phase 9 depends on all user stories being functionally complete
- Within each phase, tasks marked [P] can run in parallel
- Tasks without [P] must run sequentially within their phase

## Parallel Execution Examples

**After Phase 2 is complete — maximum parallelism**:
```
Thread A: T043-T064 (US1 Backend agents + APIs + WebSocket)
Thread B: T065-T078 (US1 Frontend layout + design system + state)
```

**After Phase 3 is complete — all user stories in parallel**:
```
Thread A: T091-T098 (US2 Undo/Rollback)
Thread B: T099-T109 (US3 Analytics/Reports)
Thread C: T110-T121 (US4 Delivery Tracking)
Thread D: T122-T131 (US5 UI/UX Polish)
Thread E: T132-T143 (US6 Auth/Email)
```

## Implementation Strategy

**MVP Scope** (Phase 1 + 2 + 3 = T001-T090):
- Complete autonomous pipeline (monitor → forecast → decide → email)
- Real-time WebSocket updates
- Dashboard, Inventory, and Agent Decisions pages
- Design system with glassmorphism dark theme
- 90 tasks to functional MVP

**Incremental Delivery Order**:
1. **MVP**: Phase 1-3 (US1) — autonomous pipeline end-to-end
2. **Safety**: Phase 4 (US2) — undo/rollback for production trust
3. **Visibility**: Phase 5 (US3) — analytics and reporting
4. **Completeness**: Phase 6 (US4) — delivery tracking closes the loop
5. **Polish**: Phase 7 (US5) — premium UI and workflow visualization
6. **Config**: Phase 8 (US6) — auth and email settings
7. **Ship**: Phase 9 — deployment and final integration
