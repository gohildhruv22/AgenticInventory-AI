# Feature Specification: Purpose-Driven Email Redesign with LLM Explainability

**Feature Branch**: `feature/003-email-redesign`

**Created**: 2026-05-20

**Status**: Draft

**Input**: User description: "Now you have to edit the emails in the proper way. We have 3 types of mail — (1) Supplier Purchase request mail, (2) Admin Information mail about purchase, (3) Daily Report mail about yesterday's update. For (1) we are sending too much (confidence level etc.); just inform about the order with proper prices. For (2) include the confidence level, why the order was placed, the forecast and KPIs we looked at, and tell admin they can undo or cancel from the app. For (3) keep it brief — purchases made and for how much, stocks that arrived today, and potential actions for managers. Add proper explainability using the LLM. Restructure the HTML with the light theme and a Zepto-like UI."

## Background & Context

The system currently emits three transactional emails from the backend (`backend/app/email/templates/`):

1. **`purchase_order.html`** — sent to suppliers when the autonomous agent places an order.
2. **`admin_notification.html`** — sent to administrators when an order needs visibility (flagged, high-value, or autonomous).
3. **`kpi_report.html`** — sent daily as a digest of activity (currently dense and full of KPIs).
4. **`cancellation.html`** — sent to suppliers when an order is cancelled (out of scope here; unchanged).

Two structural problems exist today:

- **Wrong content for the wrong audience.** The supplier PO email leaks internal agent reasoning (confidence scores, forecast inputs) that suppliers don't need and shouldn't see. The admin email under-explains *why* the agent placed the order. The daily report dumps every KPI rather than guiding the manager to action.
- **Inconsistent visual identity.** Spec `002-white-theme-overhaul` migrated the web app to a white/Zepto-style UI, but email templates were verified-as-light only at the page level. They still lack the compact card layout, large numerals, prominent CTAs, and bright accent badges that define the in-app Zepto-like aesthetic.

This feature restructures each email's **content** by audience role and rebuilds each template's **layout** to match the Zepto/light app UI. It also introduces an LLM-generated explainability narrative for the admin email so the "why" of every agent decision is captured in natural language.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Supplier-Friendly Purchase Order Email (Priority: P1)

When the agent places a purchase order, the supplier receives a clean, transactional email containing only what they need to fulfill the order: order ID, supplier-facing reference, line items with quantities, unit prices, line totals, subtotal, taxes/fees, grand total, requested delivery date, ship-to address, payment terms, and the buyer's contact information. No mention of agent confidence, internal scoring, or forecast inputs.

**Why this priority**: This email leaves the company's perimeter and is read by external partners. Leaking internal AI reasoning is both unprofessional and a competitive-information risk. It is the most visible bug today and the highest-trust surface.

**Independent Test**: Trigger an autonomous purchase via the existing decision flow, capture the rendered HTML email, and confirm (a) it contains every order/pricing field a supplier needs, (b) it contains zero internal scoring/forecast/confidence content, and (c) it visually matches the Zepto-style light theme used in the app.

**Acceptance Scenarios**:

1. **Given** the agent has approved a purchase order with 3 line items, **When** the supplier email is rendered, **Then** the email displays the order ID, requested delivery date, each line item's name + SKU + quantity + unit price + line total, subtotal, taxes, grand total, ship-to address, payment terms, and a primary contact, and contains **no** "confidence", "forecast", "KPI", "agent", "model", or numeric score language.
2. **Given** the order has a "CRITICAL" priority flag in-app, **When** the supplier email is rendered, **Then** the email may show a neutral "Expedited" or "Priority" badge in supplier-appropriate language, but does not expose internal urgency scoring.
3. **Given** a supplier opens the email on a mobile device (≤ 480 px wide), **When** the email is viewed, **Then** all line items, totals, and the call-to-action remain legible without horizontal scrolling.

---

### User Story 2 — Explainable Admin Notification Email (Priority: P1)

When the agent makes (or proposes) a notable purchase, the administrator receives an email that explains the decision end-to-end: a one-line headline, an LLM-generated 2–4 sentence rationale in plain English, the confidence score with a colored band, the key forecast and KPI signals the agent weighed (e.g., projected stock-out date, demand trend, current on-hand, supplier success rate, unit-cost delta vs. last 30 days), the alternatives considered (next-best supplier or "wait" option), and a prominent footer call-to-action: "Open in app to approve, undo, or cancel."

**Why this priority**: Admins are the human-in-the-loop. Without a clear, trustworthy explanation, every notification either gets rubber-stamped (loss of oversight) or ignored (loss of agility). This is the email that determines whether the autonomous-agent product earns trust.

**Independent Test**: Inject a synthetic decision with a known reasoning trace (confidence, forecast inputs, KPI deltas), trigger the admin email, and confirm the rendered email surfaces every input from the trace plus an LLM-generated narrative that paraphrases them faithfully (no hallucinated numbers).

**Acceptance Scenarios**:

1. **Given** the agent approves an order with confidence 0.87 driven by a projected stock-out in 4 days and a +18% 30-day demand trend, **When** the admin email is rendered, **Then** it shows the 0.87 score in an emerald band, lists the 4-day stock-out and +18% demand trend as decision drivers, and the LLM narrative explicitly references both signals.
2. **Given** the agent considered two suppliers and chose the second on price (–6% unit cost), **When** the admin email is rendered, **Then** it includes an "Alternatives considered" section showing both suppliers and the deciding factor.
3. **Given** the admin opens the email, **When** they reach the footer, **Then** they see a primary button "Review in App" linking to the decision's detail page and secondary text "You can approve, undo, or cancel this order from your dashboard."
4. **Given** the LLM service is unavailable when the email is composed, **When** the email is rendered, **Then** the template falls back to a deterministic templated rationale built from the raw signals and explicitly labels the section "Summary" (no fabricated narrative).

---

### User Story 3 — Brief Daily Digest for Managers (Priority: P2)

Each morning the manager receives a short digest of the previous day: how many orders were placed and the total spend, which inbound shipments arrived today, and 2–4 "Potential actions" the agent recommends they handle (e.g., approve a flagged order, restock a SKU below the safety threshold, review a supplier with a recent delivery miss). No dense KPI grid; the digest fits within roughly one screen.

**Why this priority**: Manager attention is the scarcest resource. A focused digest drives action; a KPI dump trains managers to ignore the email entirely. Important but secondary to the supplier and admin emails, which are transactional.

**Independent Test**: Run the daily report job with seeded data containing 3 purchases, 2 arrivals, and 2 flagged items; confirm the rendered email shows a one-line spend summary, the 2 arrivals, and exactly the 2 flagged items as actions — and that no KPI charts beyond the headline summary are present.

**Acceptance Scenarios**:

1. **Given** yesterday had 3 purchases totalling $14,820 and 2 shipments arrived today, **When** the digest is rendered, **Then** it shows "3 orders placed · $14,820 spent" at the top, lists the 2 arrivals with SKU and qty received, and shows a "Potential actions" list with at most 4 items.
2. **Given** zero arrivals and zero flagged items, **When** the digest is rendered, **Then** the arrivals section is hidden and the actions section shows a friendly empty-state ("All clear — no actions needed today").
3. **Given** the manager opens the email on mobile, **When** they view it, **Then** the entire digest is scannable in under 30 seconds with no horizontal scrolling.

---

### User Story 4 — Zepto-Style Light HTML Layout Across All Three Templates (Priority: P2)

All three templates share a consistent visual language matching the in-app design: white card on `#F3F4F6` page background, rounded `12px` corners, soft `rgba(15,23,42,0.06)` shadow, prominent brand gradient header (indigo → violet → pink) reserved only for the masthead, large bold numerals for headline figures, pill-shaped status badges in semantic colors (`emerald-50/700`, `amber-50/700`, `red-50/700`, `indigo-50/700`), generous whitespace, single-column mobile-first layout, and a clear primary CTA button.

**Why this priority**: Visual coherence with the app reinforces trust and brand. Mechanically straightforward but lower urgency than fixing content for the wrong audience.

**Independent Test**: Render all three templates with representative fixture data, view at 640 px and 360 px widths in a standard email client (Gmail/Outlook), and verify the cards, numerals, badges, and CTA buttons match the in-app Reports modal and KPI card styling.

**Acceptance Scenarios**:

1. **Given** any of the three templates, **When** rendered in a standards-compliant email client, **Then** the page background is `#F3F4F6`, the content card is `#FFFFFF` with `12px` radius and the standard soft shadow, and all body text uses the slate-900 / slate-600 / slate-500 hierarchy.
2. **Given** a headline figure (e.g., grand total, total spend, confidence score), **When** the email is rendered, **Then** the figure appears at ≥ 28 px font weight 700, with a small uppercase muted label above it.
3. **Given** a status indicator (priority, confidence band, action urgency), **When** the email is rendered, **Then** it appears as a rounded pill using the corresponding semantic `bg-*-50 text-*-700 border-*-200` triplet — never as plain text or a dark badge.
4. **Given** the email is viewed on a 360 px wide device, **When** rendered, **Then** the layout collapses to a single column with no horizontal scroll and the primary CTA is full-width.

---

### Edge Cases

- What happens when an order has more than ~10 line items? → The supplier email lists all items in a scrollable region within the email (no truncation in the source HTML) and shows the count in the order header.
- What happens when the LLM rationale exceeds a sensible length (> 500 characters)? → Truncate at a sentence boundary near 400 characters and append "(full reasoning in app)".
- How does the system handle missing fields (e.g., supplier email has no `payment_terms`)? → Hide the row entirely; never render "N/A" or "null".
- What happens if the daily digest has zero orders and zero arrivals? → Render a friendly empty-state digest acknowledging the quiet day rather than skipping the email.
- How does the system handle very low confidence scores in the admin email (e.g., < 0.5)? → The confidence band switches to red, the headline tone is "Decision needs your review", and the primary CTA upgrades from "Review in App" to "Approve or Cancel".
- What happens when the LLM call fails or times out for the admin email? → Fall back to a deterministic templated rationale built from the raw signals (US2 acceptance scenario 4).

## Requirements *(mandatory)*

### Functional Requirements

**Content separation by audience (US1, US2, US3)**

- **FR-001**: The supplier purchase order email MUST contain order metadata (order ID, requested delivery date), full line-item table (name, SKU, qty, unit price, line total), totals breakdown (subtotal, taxes/fees, grand total), ship-to address, payment terms, and buyer contact information.
- **FR-002**: The supplier purchase order email MUST NOT contain any reference to agent confidence, model output, internal forecasts, KPI deltas, alternatives considered, or any string matching the patterns "confidence", "agent", "model", "forecast", "KPI", or a numeric score on a 0–1 scale.
- **FR-003**: The admin notification email MUST contain: (a) a one-line headline, (b) an LLM-generated natural-language rationale of 2–4 sentences, (c) the confidence score rendered in an emerald / amber / red band corresponding to ≥ 0.8 / 0.6–0.8 / < 0.6, (d) a "Decision drivers" list of the forecast and KPI signals the agent considered, (e) an "Alternatives considered" section when more than one option was scored, and (f) a footer CTA linking to the decision detail page in-app with copy stating the admin can approve, undo, or cancel.
- **FR-004**: The daily digest email MUST contain: (a) a one-line summary of the previous day's order count and total spend, (b) a list of inbound shipments received today (SKU, qty, supplier), (c) a "Potential actions" list of 0–4 manager-actionable items, and (d) a single CTA linking to the in-app dashboard.
- **FR-005**: The daily digest email MUST NOT contain detailed KPI tables, multi-metric dashboards, or any visualization that requires more than a glance to interpret. Beyond the headline summary line, no further KPI numbers are shown.

**LLM explainability (US2)**

- **FR-006**: The admin notification email pipeline MUST invoke the existing backend LLM integration to generate a plain-English rationale conditioned on the decision's signals (confidence, demand forecast, on-hand stock, supplier score, cost delta, alternatives).
- **FR-007**: The LLM rationale MUST be grounded — it MUST NOT invent numeric values; every number in the rationale MUST appear in the underlying decision payload.
- **FR-008**: The email pipeline MUST gracefully degrade when the LLM is unavailable, timed out, or returns an unsafe response (rate limit, content filter): fall back to a deterministic templated summary built from the raw signals and label that block "Summary" instead of "Why this decision".
- **FR-009**: The LLM rationale MUST be truncated at a sentence boundary at or below 500 characters; when truncated, the email MUST append a "(full reasoning in app)" pointer.

**Visual layout (US4)**

- **FR-010**: All three templates MUST share a common header partial (gradient masthead with brand mark), card wrapper (white, `12px` radius, soft slate shadow), typography scale (slate-900 / slate-600 / slate-500), and CTA button style (full-width primary gradient on mobile, inline on desktop).
- **FR-011**: Status indicators MUST use the centralized status pill style (`bg-{color}-50 text-{color}-700 border-{color}-200`) introduced by spec `002-white-theme-overhaul` — emerald (success/healthy), amber (warning/medium), red (critical/low), indigo (info), slate (neutral).
- **FR-012**: Templates MUST render correctly at 360 px, 480 px, 640 px, and desktop widths in Gmail, Outlook (desktop + web), and Apple Mail, with all critical content above the fold on mobile.
- **FR-013**: Templates MUST keep all inline styles compatible with email-client constraints (no external CSS, no `<style>`-only declarations for critical layout, no JavaScript, no web fonts beyond system-font fallbacks).

**Operational**

- **FR-014**: Existing email-sending entry points (autonomous purchase trigger, admin-notify trigger, daily digest cron) MUST continue to work without changes to their call sites — only the template content and a new optional `rationale` field flowing from the decision payload may change.
- **FR-015**: The system MUST log when the LLM fallback path is taken so operators can monitor explainability quality over time.

### Key Entities

- **PurchaseOrderEmailContext** — the data passed to the supplier template: order ID, supplier name, line items, totals, ship-to, payment terms, buyer contact, requested delivery date. Excludes any agent-internal field.
- **AdminDecisionEmailContext** — the data passed to the admin template: order summary, confidence score, decision drivers (list of `{label, value, trend}`), alternatives considered (list of `{option, score, deciding_factor}`), `rationale` (LLM-generated string, optional), `rationale_source` (`"llm"` | `"fallback"`), and a deep-link URL to the in-app decision page.
- **DailyDigestEmailContext** — the data passed to the daily template: yesterday's order count, yesterday's total spend, list of today's arrivals, list of 0–4 potential actions (each with a label, a one-line reason, and a deep-link).
- **EmailRationale** — the LLM-generated narrative attached to admin emails: source, generated text, optional truncated flag, generation timestamp.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of supplier purchase order emails contain zero internal-AI terms (audited via automated check on rendered HTML for the forbidden string list in FR-002).
- **SC-002**: 95% of admin notification emails include a non-empty LLM-generated rationale (the remaining ≤ 5% use the deterministic fallback and are clearly labelled "Summary").
- **SC-003**: Every numeric value in an LLM-generated admin rationale can be traced to a field in the underlying decision payload (audited by a grounding check at send time; non-grounded outputs are rejected and trigger the fallback).
- **SC-004**: The daily digest email length stays under 800 words rendered and presents no more than 4 "Potential actions".
- **SC-005**: All three templates pass a mobile-readability check at 360 px (no horizontal scroll, primary CTA visible without scrolling more than one screen height).
- **SC-006**: All three templates render with visual-regression parity to the in-app Zepto-style design system (manually reviewed against the Reports modal and KPI cards) — page bg `#F3F4F6`, card `#FFFFFF` with `12px` radius and the standard soft shadow, slate-900/600/500 type hierarchy, semantic status pills.
- **SC-007**: Admin recipients can navigate from email → in-app decision detail with a single click via the footer CTA (verified by click-through telemetry or manual test).
- **SC-008**: Supplier feedback (manual sampling of 5 recipients) reports no confusion about the email's contents and no perception of leaked internal data, post-rollout.

## Assumptions

- The existing backend LLM integration (used elsewhere for explanation generation) is reused; no new model selection, prompt-engineering, or vendor decision is in scope here.
- All three emails are HTML emails; a plain-text alternate part is generated automatically by the existing email service and is out of scope for visual design.
- The decision payload already contains (or can be extended on the producer side to contain) the signals required for admin emails — confidence, decision drivers, alternatives. If a field is missing, the corresponding section in the email is hidden rather than rendered with placeholder content.
- The supplier email's "no internal-AI content" constraint is enforced at the template level (the supplier-facing context object simply omits those fields), not by runtime redaction. The producer code MUST construct the supplier context from a whitelisted subset of the order payload.
- Email-client compatibility targets the four most common clients (Gmail, Outlook web, Outlook desktop, Apple Mail) at the latest two versions each. Niche clients are best-effort.
- The "Zepto-like UI" reference is the in-app design language established by spec `002-white-theme-overhaul` (Reports modal, KPI cards, landing page) — clean white cards with bright accent pills, generous whitespace, and bold numerals. No literal asset reuse from the Zepto product.
- The Daily Digest's "stocks arrived today" is sourced from the existing inbound-shipment tracking already exposed by the backend; no new ingestion pipeline is required.
- Cancellation email (`cancellation.html`) is intentionally **out of scope** for this feature; it will be revisited if its content/layout drifts.

## Out of Scope

- Backend LLM provider/model selection or prompt-engineering for entirely new use cases beyond the admin-email rationale.
- Plain-text email part design and copy.
- Internationalization / localization of email copy (English only, matching current state).
- A/B testing harness for email variants.
- Changes to the cancellation email template.
- Changes to in-app notification surfaces (toast, in-app inbox).
