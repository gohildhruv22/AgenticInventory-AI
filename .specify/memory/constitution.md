<!--
  Sync Impact Report
  ===================
  Version change: N/A → 1.0.0
  Modified principles: N/A (initial creation)
  Added sections:
    - Core Principles (10 principles)
    - Technology Stack Constraints
    - Development Workflow & Quality Gates
    - Governance
  Removed sections: N/A
  Templates requiring updates:
    - .specify/templates/plan-template.md ✅ reviewed (no changes needed)
    - .specify/templates/spec-template.md ✅ reviewed (no changes needed)
    - .specify/templates/tasks-template.md ✅ reviewed (no changes needed)
  Follow-up TODOs: None
-->

# AgenticInventory AI Constitution

## Core Principles

### I. AutoGen-Only Agent Orchestration (NON-NEGOTIABLE)

- Microsoft AutoGen MUST be the sole framework for all
  multi-agent orchestration. No alternative agent frameworks
  (LangGraph, CrewAI, custom orchestrators) are permitted.
- All AI agents MUST operate autonomously without requiring
  human-in-the-loop intervention for routine decisions.
- Agent communication patterns, role definitions, and
  conversation flows MUST use AutoGen primitives exclusively.

**Rationale**: A single orchestration framework eliminates
integration friction, ensures consistent agent behavior, and
concentrates team expertise in one ecosystem.

### II. Groq-Exclusive LLM Provider (NON-NEGOTIABLE)

- Groq MUST be the only LLM provider for all AI inference.
- No OpenAI, Anthropic, local models, or other LLM backends
  are permitted in any environment (dev, staging, production).
- Every AI agent MUST use LLM reasoning for all of its
  decisions—hard-coded rule engines MUST NOT substitute for
  LLM inference where reasoning is required.

**Rationale**: Groq's inference speed is critical for
real-time autonomous procurement decisions. A single provider
simplifies API key management, billing, and latency profiling.

### III. AI Explainability & Reversibility (NON-NEGOTIABLE)

- Every AI decision MUST produce an explainable reasoning
  trace that can be inspected by operators and auditors.
- Reasoning traces MUST include: input context, decision
  rationale, confidence level, and alternative options
  considered.
- Every autonomous action MUST support undo/rollback. No
  irreversible side effects are permitted without explicit
  human approval.
- Undo operations MUST restore the previous state completely
  and MUST be accessible from the UI.

**Rationale**: Autonomous procurement decisions carry
financial risk. Explainability builds trust; reversibility
provides a safety net against erroneous AI actions.

### IV. UI/UX Excellence (HIGHEST PRIORITY — NON-NEGOTIABLE)

- UI/UX quality MUST be the highest priority across all
  engineering decisions. When trade-offs arise, user
  experience wins.
- The interface MUST feel like a blend of Zepto (speed and
  delight), Stripe (clarity and precision), and Linear
  (keyboard-first productivity).
- MUST use a futuristic SaaS design system with a modern dark
  theme featuring purple-to-pink gradient accents.
- Beautiful animations (micro-interactions, page transitions,
  loading states) and premium UX polish are mandatory in every
  feature delivered.
- The platform MUST be demo-friendly and visually impressive
  at all times—no feature ships without visual polish.

**Rationale**: A visually stunning, responsive UI
differentiates the platform in enterprise procurement demos
and drives user adoption.

### V. Real-Time WebSocket Architecture

- WebSockets MUST be used throughout the entire system for
  all real-time data communication between frontend and
  backend.
- Polling-based alternatives are NOT permitted for any data
  that changes in real time (inventory levels, agent status,
  procurement events, KPI dashboards).
- WebSocket connections MUST implement reconnection logic,
  heartbeat monitoring, and graceful degradation.

**Rationale**: Autonomous AI agents produce continuous state
changes; WebSockets ensure operators see live updates without
latency or stale data.

### VI. External Intelligence APIs

- The platform MUST integrate the following external data
  sources to power AI agent reasoning:
  - **Google Trends API**: Market demand signal detection
  - **News API**: Supply chain disruption and market event
    monitoring
  - **Weather API**: Weather-dependent demand and logistics
    forecasting
  - **Holiday API**: Seasonal demand spike prediction
- All external API integrations MUST include caching,
  rate-limit handling, and fallback behavior when APIs are
  unavailable.

**Rationale**: Procurement intelligence requires real-world
context signals beyond historical inventory data. These APIs
provide the external intelligence layer that differentiates
autonomous decisions from simple threshold-based reordering.

### VII. Delivery Simulation

- The platform MUST support end-to-end delivery simulation
  for procurement scenarios including order placement,
  supplier lead times, transit tracking, and warehouse
  receipt.
- Simulations MUST be configurable with variable parameters
  (delays, partial deliveries, supplier failures).
- Simulation results MUST be visualized in the UI with
  timeline and status indicators.

**Rationale**: Delivery simulation enables risk assessment
and what-if analysis before committing to real procurement
actions.

### VIII. Reporting & Analytics Excellence

- Daily KPI reports MUST exist both in-app (dashboard) and
  via automated email delivery.
- All reports and analytics MUST be visually rich with
  interactive charts, graphs, and data visualizations—no
  plain-text or table-only reports.
- Dashboard metrics MUST update in real time via WebSockets
  (see Principle V).

**Rationale**: Decision-makers require at-a-glance
visibility into procurement performance. Rich visuals
accelerate comprehension and support executive presentations.

### IX. Production-Grade Email Automation

- SMTP email automation MUST be production-grade: reliable
  delivery, HTML-templated messages, delivery tracking, and
  retry logic on failure.
- Email templates MUST match the platform's design system
  (dark theme, purple/pink gradients) for brand consistency.
- Daily KPI report emails MUST be sent automatically without
  manual triggering.

**Rationale**: Email is the primary out-of-app communication
channel. Production-grade reliability ensures stakeholders
never miss critical procurement alerts or daily reports.

### X. Scalable Clean Architecture & Azure Readiness

- The codebase MUST follow clean architecture principles:
  clear separation of concerns, dependency inversion, and
  domain-driven boundaries.
- The system MUST be Azure deployment ready at all times—
  containerized services, infrastructure-as-code templates,
  and CI/CD pipeline compatibility.
- Scalability MUST be designed in from the start: stateless
  services, horizontal scaling support, and externalized
  configuration.

**Rationale**: Enterprise procurement platforms must scale
with business growth. Clean architecture ensures
maintainability; Azure readiness enables rapid deployment to
customer environments.

## Technology Stack Constraints

- **Agent Framework**: Microsoft AutoGen (exclusive)
- **LLM Provider**: Groq (exclusive)
- **Frontend**: React/Next.js with TypeScript, Tailwind CSS,
  Framer Motion for animations
- **Backend**: Python (FastAPI) for AI services, Node.js for
  real-time WebSocket gateway
- **Database**: PostgreSQL for persistent data, Redis for
  caching and pub/sub
- **Real-Time**: WebSocket connections (Socket.IO or native
  WS)
- **External APIs**: Google Trends, News API, Weather API,
  Holiday API
- **Email**: SMTP with HTML template engine
- **Deployment**: Docker containers, Azure-ready
  infrastructure
- **Design System**: Dark theme, purple/pink gradients,
  futuristic SaaS aesthetic

## Development Workflow & Quality Gates

- Every feature MUST include UI polish before it is
  considered complete—no "functionality first, design later"
  exceptions.
- All AI agent behaviors MUST include explainability metadata
  in their response payloads.
- Undo/rollback MUST be tested as part of acceptance criteria
  for any autonomous action.
- External API integrations MUST include mock/stub fallbacks
  for offline development and testing.
- WebSocket connections MUST be load-tested before any
  release.
- Email delivery MUST be verified in staging before
  production deployment.
- All PRs MUST verify compliance with this constitution
  before merge.

## Governance

- This constitution supersedes all other development
  practices, coding guidelines, and ad-hoc decisions.
- Amendments require:
  1. Written proposal documenting the change and rationale.
  2. Review of impact on all dependent templates and
     artifacts.
  3. Version bump following semantic versioning (MAJOR for
     principle removals/redefinitions, MINOR for additions,
     PATCH for clarifications).
  4. Update of the `LAST_AMENDED_DATE` field.
- All code reviews and PRs MUST verify compliance with the
  active constitution version.
- Complexity beyond what is specified here MUST be justified
  with a documented rationale and a simpler alternative that
  was considered and rejected.

**Version**: 1.0.0 | **Ratified**: 2026-05-17 | **Last Amended**: 2026-05-17
