# Feature Specification: Full White-Theme UI Overhaul

**Feature Branch**: `feature/002-white-theme-overhaul`

**Created**: 2026-05-19

**Status**: US1–US6 Implemented

**Input**: User description: "Now this app is in the white theme so every component must be according to a white theme. Every text and everything. There are still many places and many floating windows that have a dark theme. Make changes and convert the whole site into the white theme."

## Implementation Notes (US1–US3)

- `frontend/index.html` — removed `class="dark"` on `<html>`, replaced dark body classes with `bg-[#FAFBFD] text-slate-900`, added `<meta name="color-scheme" content="light">`.
- `frontend/src/globals.css` — extended the compatibility layer to also catch `bg-[#0b0b14]`, `bg-[#08080f]`, `bg-white/[0.01–0.025]` (now `#F8F9FC` for hierarchy), `bg-white/[0.07–0.30]`, all odd `text-white/{15,25,35,45,55,65,75,85,95}` variants, every `placeholder:text-white/*` opacity, hover-text-white variants, white ring/divide/from/to gradient stops, soft status pill tints (`bg-{color}-500/{15,20}`, `border-{color}-500/{30,40}`), backdrop-blur neutralization, modal-overlay dark-translucent preservation, and native form controls forced to `color-scheme: light`.
- `frontend/src/pages/Reports.tsx` — Report Detail modal now uses `bg-white border-slate-200` directly (no longer relies on compat override); `StatTile`/`Pill`/`InsightList` tone classes rewritten with proper light-tint tokens (`bg-emerald-50 text-emerald-700` etc.) for intentional brand identity (US3).
- `frontend/src/components/ui/GradientButton.tsx` — `secondary` and `ghost` variants rewritten to `bg-white border-slate-200 text-slate-700` and `text-slate-600 hover:bg-slate-100`.
- `frontend/src/pages/LandingPage.tsx` — page background now `bg-[#FAFBFD]`; hero pill, headline, body copy, CTA, feature cards, and footer all migrated to slate-on-white with preserved gradient accent text and primary CTA gradient (US3 brand identity intact).

## Implementation Notes (US4–US6)

- **US6 — Centralized theme tokens**: Created `frontend/src/styles/theme.ts` exporting `surface`, `text`, `border`, `accent`, `status`, `button`, `input` Tailwind class-string maps plus a parallel `colors` raw-hex map. The status group is the single source of truth for FR-007 pill variants (`success`/`warning`/`danger`/`info`/`neutral`/`brand`/`accent`/`cyan`, each `bg-*-50 text-*-700 border-*-200`).
- **US4 — Recharts white theme**:
  - Created `frontend/src/components/charts/chartTheme.ts` exporting `CHART_GRID_STROKE` (`#E2E8F0`), `CHART_AXIS_TICK` (`#64748B`), `CHART_AXIS_LINE` (`#CBD5E1`), `CHART_TRACK`, `CHART_PALETTE` (`#4F46E5, #7C3AED, #06B6D4, #10B981, #F59E0B, #F43F5E`), and tooltip inline-style objects.
  - Created `frontend/src/components/charts/ChartTooltip.tsx` — shared white-card tooltip (`bg-white border-slate-200 shadow-md`, slate-500 label header, slate-900 value rows with colored bullet) for use via `<Tooltip content={<ChartTooltip />} />`.
  - `TrendChart.tsx` — container now `bg-white border-slate-200 shadow-sm`; grid/axis colors swapped to chartTheme tokens; default series color `#4F46E5`; tooltip migrated to `<ChartTooltip />`; label text `text-slate-500`.
  - `SupplierPerfChart.tsx` — same container migration; bar gradients now reference `CHART_PALETTE[0]` (indigo) and `CHART_PALETTE[3]` (emerald); tooltip migrated to `<ChartTooltip />`; legend text `text-slate-600`.
  - `ConfidenceGauge.tsx` — inactive radial track now `CHART_TRACK` (`#E2E8F0`); status text colors shifted from `text-emerald-400` → `text-emerald-600`, etc.; raw fill swapped from `#4ade80`/`#fbbf24`/`#f87171` to `#10B981`/`#F59E0B`/`#EF4444`; bottom label `text-slate-500`.
  - `pages/Analytics.tsx` — pie chart series sourced from `CHART_PALETTE` (plus one indigo-400 spare); tooltip migrated to `<ChartTooltip />`; pie stroke white; legend + empty-state text now slate; TrendChart series shifted to `#7C3AED` (violet) and `#10B981` (emerald).
  - `KPICard.tsx` verified — already light (`bg-white border-slate-200`, slate text).
- **US5 — Email template verification**: All 4 Jinja templates (`admin_notification.html`, `cancellation.html`, `kpi_report.html`, `purchase_order.html`) inspected. Page background uses `#f3f4f6` (light gray) wrapping `#ffffff` card; all white text (`color:#fff`) is on intentional gradient/badge surfaces (brand identity per FR-006, US3). No remediation required.

## Background & Context

The original `001-agentic-inventory-ai` spec mandated a futuristic **dark** theme (Principle IV) using a `#0a0a0f` background, glassmorphism over white-on-dark transparencies (`bg-white/[0.03]`, `text-white/90`, `border-white/[0.06]`), purple→pink gradient accents, and HTML emails styled to match.

Recent UX work has shifted the product to a **light/white** theme for the main app shell, but the conversion is incomplete: many components, modals, popovers, dropdowns, toast notifications, charts, code blocks, table rows, status pills, focus rings, and chart tooltips still render dark-on-dark colors. Result: text is unreadable, "floating" surfaces (modals, command palettes, popovers, hover-cards, dropdowns) look broken, and the product feels inconsistent.

This feature finishes the white-theme conversion across **every surface** of the product (web app, popovers, modals, toasts, charts, status badges, email templates) so the entire UI is visually coherent and accessible (WCAG AA contrast minimum).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Consistent White Theme Across Every Page (Priority: P1)

A user signs in and navigates through every page of the app — Dashboard, Inventory, Decisions, Deliveries, Agents, Analytics, Reports, Settings, Landing, Login, Register. Every page renders with a light background, dark readable text, and the brand accent palette (indigo/violet/pink) applied tastefully. There are no leftover dark surfaces, no white-on-white invisible text, and no `text-white/40` ghost text on a light background.

**Why this priority**: This is the headline complaint. Without consistent theming the product looks broken, which blocks demos and erodes trust. This story alone is the MVP.

**Independent Test**: Open each of the 11 routed pages and verify (1) the page background is light (`#f7f7fb` or `#ffffff` family), (2) every primary text element has at least WCAG AA contrast against its background, (3) no element still uses `bg-white/[0.0X]`, `text-white/XX`, `border-white/[0.0X]` from the dark token set, (4) brand gradients on accents (buttons, score banners, agent type chips) remain visible.

**Acceptance Scenarios**:

1. **Given** any page in the app, **When** rendered with default settings, **Then** its outer background is one of the approved light tokens (`bg-white`, `bg-slate-50`, `bg-[#f7f7fb]`) and every text element resolves to a slate/gray family color (`text-slate-900`, `text-slate-700`, `text-slate-500`).
2. **Given** any glassmorphism card on any page, **When** inspected, **Then** it uses the new light-glass token set (white card on faint slate background with subtle shadow) instead of the dark-glass set (`bg-white/[0.03]` on `#0a0a0f`).
3. **Given** any status pill (approved / flagged / executed / rolled-back / sent / failed), **When** rendered, **Then** it uses a light-tint variant (e.g., `bg-emerald-50 text-emerald-700 border-emerald-200`) and remains legible against the white card.
4. **Given** a placeholder/empty state on any page, **When** rendered, **Then** the muted text uses `text-slate-400` or `text-slate-500` (never `text-white/XX`).

---

### User Story 2 — Floating Surfaces (Modals, Popovers, Dropdowns, Toasts) Are Light (Priority: P1)

A user opens the **Reports → View Details** modal, the supplier-order action dropdown, a chart tooltip, the toast/notification when a decision is approved, and the command-palette / select popovers. Every floating surface renders with a white card, soft slate border, low-elevation shadow, and dark readable content. No floating surface is still pitch black.

**Why this priority**: Floating surfaces are exactly what the user called out ("so many floating windows have a dark theme"). They are the most jarring inconsistency and the highest impact fix.

**Independent Test**: Trigger every floating surface (list below) and confirm they all share the same light surface tokens and have visible borders/shadows on a light page.

  Floating surfaces in scope:
  - Report detail modal (`ReportDetailModal` in `Reports.tsx`)
  - Email preview / KPI report HTML inside the detail modal iframe
  - Confirmation dialogs (Undo, Approve, Delete, Settings save)
  - Toast/notification system (success, error, info)
  - Tooltips (Recharts chart tooltip, hover hints, status indicators)
  - Dropdowns and `<select>` popovers (filters, category pickers, supplier pickers)
  - Date pickers
  - Hover-cards over agent activity rings, KPI tiles, supplier badges
  - Sidebar mobile drawer / mobile menu
  - Search command palette (if present)

**Acceptance Scenarios**:

1. **Given** the Reports page, **When** the user clicks "View Details" on any report row, **Then** the modal background is white (`bg-white`), the header uses the indigo→violet gradient with white text, and body sections use slate-on-white tokens.
2. **Given** any confirmation dialog (Undo, Approve, Save Settings), **When** opened, **Then** the surface is a light card with a colored accent (red / amber / emerald) on a white body — not a dark panel.
3. **Given** any Recharts visualization, **When** the user hovers a data point, **Then** the tooltip surface is white with slate-700 labels and slate-500 secondary text, with a 1px slate-200 border and a soft shadow.
4. **Given** any toast notification, **When** triggered, **Then** it renders as a white card with a colored left accent bar matching the variant (emerald success / amber warn / red error / indigo info).
5. **Given** any native `<select>` or custom dropdown popover, **When** opened, **Then** the option list is white with hover state `bg-slate-100` and selected state `bg-indigo-50 text-indigo-700`.

---

### User Story 3 — Brand Identity Preserved & Accessible (Priority: P2)

The product still feels like AgenticInventory AI: the indigo→violet→pink brand gradients appear on the landing hero, primary CTAs, the report performance-score banner, and agent type chips. But these gradients now sit on a white surface, with adequate contrast and without overpowering the page. Text on gradient surfaces remains white and readable; text on white surfaces uses slate-700/900.

**Why this priority**: Theme conversion must not strip brand identity. Without gradients the product looks generic; with too much gradient it looks garish on white.

**Acceptance Scenarios**:

1. **Given** the landing page hero, **When** rendered, **Then** the headline text is `text-slate-900`, the supporting copy is `text-slate-600`, and a single accent gradient ribbon or framed CTA is the only gradient element above the fold.
2. **Given** any primary CTA button, **When** rendered, **Then** it uses the gradient `from-indigo-500 via-violet-500 to-pink-500` with white text and `shadow-indigo-500/25`.
3. **Given** any agent type chip (Decision Manager / Forecast / Monitoring / Email / Reporting / Undo & Rollback), **When** rendered, **Then** it uses a soft tinted background (`bg-indigo-50` / `bg-cyan-50` / `bg-emerald-50` / `bg-amber-50` / `bg-purple-50` / `bg-red-50`) with matching `text-*-700` and `border-*-200`.
4. **Given** any text on top of a gradient surface, **When** measured, **Then** contrast ratio is ≥ 4.5:1 (WCAG AA for normal text).

---

### User Story 4 — Charts, Data Visualizations, and Sparklines Theme-Match (Priority: P2)

A user opens the Analytics page and the Dashboard. All Recharts graphs (line, area, bar, donut, gauge), sparklines, and progress rings render with light-theme palettes: grid lines in `#e2e8f0`, axes in `#94a3b8`, series colors picked from a curated palette of indigo/violet/cyan/emerald/amber/rose that read well on white, and tooltips in the same white surface as US2.

**Why this priority**: Charts make up a large portion of the screen real estate. Dark-theme-specific colors (e.g. neon cyan/lime, near-black grid lines) fail on white.

**Acceptance Scenarios**:

1. **Given** any Recharts chart, **When** rendered, **Then** its grid uses `stroke="#e2e8f0"` and axis ticks use `fill="#64748b"`.
2. **Given** any chart series, **When** rendered, **Then** colors come from the light-theme palette: `#4f46e5` (indigo-600), `#7c3aed` (violet-600), `#06b6d4` (cyan-500), `#10b981` (emerald-500), `#f59e0b` (amber-500), `#f43f5e` (rose-500).
3. **Given** any donut/gauge confidence ring, **When** rendered, **Then** the inactive track uses `stroke="#e2e8f0"` (not white-on-dark) and the label inside the ring is `text-slate-900`.

---

### User Story 5 — Email Templates Already Light, Verified End-to-End (Priority: P3)

The four HTML email templates (supplier purchase order, admin notification, KPI daily brief, low-stock alert) are already light-themed from earlier work; this story merely **verifies** they continue to render correctly after the in-app theme overhaul and that nothing imports dark-theme tokens via shared renderer helpers.

**Acceptance Scenarios**:

1. **Given** each of the four email templates, **When** opened in Gmail / Outlook web / Outlook desktop, **Then** the email renders with a white card on a `#f3f4f6` background, dark slate text, the indigo→violet gradient header, and color-coded status pills.
2. **Given** the Reports → View Details modal "Email Preview" affordance (if/when added), **When** rendered, **Then** the iframe content (using the same templates) is visually identical to the actual email.

---

### User Story 6 — Theme Tokens Centralized for Future Maintenance (Priority: P3)

A developer adding a new component opens `tailwind.config.ts` and `src/styles/theme.ts` (new file) and finds a single source of truth for surface, text, border, accent, status, and chart color tokens. They never need to grep for `bg-white/[0.03]` again — they reference `surface.card`, `text.primary`, `status.success`, etc.

**Acceptance Scenarios**:

1. **Given** the new theme module, **When** a developer adds a card, **Then** they use `cn(theme.surface.card, theme.text.primary)` or the semantic Tailwind tokens (`bg-card text-card-foreground`) and never inline dark tokens.
2. **Given** the codebase after this feature, **When** grepped for `text-white/`, `bg-white/[0.0`, or `border-white/[0.0`, **Then** zero matches remain in `frontend/src/**/*.{ts,tsx,css}` (allow-list: explicit "on-gradient" text such as `text-white` on a gradient CTA).

---

### Edge Cases

- **Charts inside the report detail modal** — must use the in-modal light tooltip variant, not the page-level tooltip.
- **Iframes that render the KPI email** — must not inherit dark styles from the parent; isolated by `srcdoc`.
- **System dark mode preference (`prefers-color-scheme: dark`)** — this release ships **light-only**. The app must explicitly opt out of OS dark mode by setting `color-scheme: light` and `<meta name="color-scheme" content="light">`.
- **Native form controls** (`<input type="date">`, `<input type="checkbox">`, scrollbars) — must use `color-scheme: light` and themed scrollbars (`scrollbar-color: #cbd5e1 #f1f5f9`).
- **Recharts default tooltips** — Recharts ships dark by default; every chart MUST pass an explicit `<Tooltip content={...} />` or `contentStyle` matching the light tokens.
- **Status indicator dots that previously glowed on dark** — adapt to subtle `ring-2 ring-offset-1` rings on white instead of `shadow-[0_0_8px_*]` neon glows.
- **Loading skeletons** previously using `bg-white/[0.04]` — switch to `bg-slate-100` with `animate-pulse`.
- **Code/JSON viewers** (reasoning trace raw view, if present) — light-theme syntax (Prism `prism` or `prism-tomorrow-light`).
- **Selected row / focused input rings** — replace neon purple ring with `ring-2 ring-indigo-500/40`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The application MUST render with a light/white theme on every routed page (Dashboard, Inventory, Decisions, Deliveries, Agents, Analytics, Reports, Settings, Landing, Login, Register) and on every shared layout component (Sidebar, TopBar, MobileDrawer, Footer if present).
- **FR-002**: Every floating surface (modal, dialog, popover, tooltip, dropdown, toast, hover-card, date picker, mobile drawer) MUST use the light surface token set.
- **FR-003**: A centralized theme token module MUST be introduced at `frontend/src/styles/theme.ts` exporting `surface`, `text`, `border`, `accent`, `status`, and `chart` token groups, and `tailwind.config.ts` MUST expose semantic colors (`background`, `foreground`, `card`, `card-foreground`, `muted`, `muted-foreground`, `border`, `accent`, `primary`, `destructive`).
- **FR-004**: All references to the dark token set in `frontend/src/**/*.{ts,tsx,css}` MUST be removed or migrated. Specifically: `bg-white/[0.0X]`, `text-white/XX` (except where text sits on a brand gradient and contrast is ≥ 4.5:1), `border-white/[0.0X]`, `bg-[#0a0a0f]`, `bg-[#0b0b14]`, `bg-black/XX` (except for modal overlays), `from-[#0` and similar dark hex literals.
- **FR-005**: Recharts charts MUST set `<CartesianGrid stroke="#e2e8f0" />`, axis `tick={{ fill: "#64748b" }}`, and supply a light `<Tooltip>` styled via a shared `ChartTooltip` component.
- **FR-006**: The root HTML and CSS MUST declare `color-scheme: light` so native controls and scrollbars render in light mode regardless of OS preference.
- **FR-007**: Status indicators (executed, approved, flagged, rejected, pending_review, rolled_back, sent, failed, in_transit, delivered) MUST have a single source of truth in the theme module with light-tint background, `text-*-700` foreground, and `border-*-200` border.
- **FR-008**: All primary CTA buttons MUST use the brand gradient `from-indigo-500 via-violet-500 to-pink-500` with `text-white` and visible `shadow-indigo-500/25` on white surfaces.
- **FR-009**: All non-CTA buttons MUST use one of these styles: secondary (`bg-white border border-slate-200 text-slate-700 hover:bg-slate-50`), ghost (`text-slate-600 hover:bg-slate-100`), or destructive (`bg-red-600 text-white hover:bg-red-700`).
- **FR-010**: All form inputs (`input`, `select`, `textarea`) MUST use `bg-white border border-slate-200 text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20`.
- **FR-011**: Skeleton loaders MUST use `bg-slate-100 animate-pulse` instead of `bg-white/[0.04]`.
- **FR-012**: Iframes rendering email-template HTML MUST render the same light template HTML and MUST set the iframe wrapper background to `#f3f4f6` to match the email's outer background.
- **FR-013**: WCAG AA contrast (≥ 4.5:1 normal text, ≥ 3:1 large text/UI components) MUST be verified for every text/background pair via an automated check.
- **FR-014**: The four HTML email templates MUST remain unchanged behaviorally; only verification that they still render correctly is required.
- **FR-015**: The constitutional Principle IV reference to "dark theme" MUST be reconciled — either the constitution is amended (preferred, via `/speckit.constitution`) or this spec MUST document the explicit waiver with a link.

### Non-Functional Requirements

- **NFR-001**: No measurable degradation in page load time vs. previous theme (≤ 5% Lighthouse perf regression on Dashboard route).
- **NFR-002**: Bundle size delta ≤ +10 KB gzip net (token module + any added utilities).
- **NFR-003**: Zero new TypeScript or ESLint errors after migration.
- **NFR-004**: Backend, database schema, API contracts, WebSocket payloads — all UNCHANGED. This is a frontend-only feature.

### Key Entities

This feature has no new data entities. Affected artifacts are visual tokens, not domain objects.

## Success Criteria *(mandatory)*

- **SC-001**: A user navigating all 11 routed pages reports zero "dark patches" or unreadable text.
- **SC-002**: A scripted grep across `frontend/src/**/*.{ts,tsx,css}` for the forbidden token patterns (`text-white/[0-9]`, `bg-white/\[0\.0`, `border-white/\[0\.0`, `bg-\[#0a0a0f\]`, `bg-\[#0b0b14\]`) returns **0 matches** outside an explicit allow-list (text on gradient backgrounds).
- **SC-003**: WCAG AA contrast verification on the top 50 text/background pairs returns ≥ 4.5:1 for normal text and ≥ 3:1 for UI/large text. (Manual sample: 50 pairs; automation optional.)
- **SC-004**: Lighthouse Accessibility score on Dashboard route is ≥ 95.
- **SC-005**: Lighthouse Performance score on Dashboard route does not drop more than 5 points vs. pre-overhaul baseline.
- **SC-006**: All 4 HTML email templates (supplier order, admin alert, KPI report, low-stock) render identically before and after the overhaul in Gmail and Outlook Web.
- **SC-007**: A first-time visitor can complete the demo flow (sign in → view decisions → approve a flagged decision → undo an executed decision → open a report's detail modal → trigger a daily report email) without encountering any unreadable text or invisible UI elements.
- **SC-008**: 100% of floating surfaces (modal, popover, tooltip, toast, dropdown) render with a white surface, slate border, and soft shadow.
- **SC-009**: Manual smoke test on Chrome, Edge, and Firefox at 1280×800 and 390×844 (mobile) shows visual parity.

## Assumptions

- Tailwind v3 with arbitrary value support is in use (existing config).
- Recharts is the chart library in use (existing).
- Framer Motion remains the animation library (no change).
- The product remains light-only for this release; a future feature may introduce a system-aware dark-mode toggle, but it is out of scope here.
- The HTML email templates are already light-themed from prior work (verified May 2026) and only require verification, not changes.
- The constitution's "dark theme" principle will be amended in a follow-up `/speckit.constitution` call; this spec proceeds under the assumption that the white-theme pivot has product-owner sign-off (the user request is the explicit sign-off).

## Out of Scope

- Adding a user-facing dark-mode toggle.
- Re-skinning HTML email templates (already light).
- Backend, database, agent logic, WebSocket protocol changes.
- New iconography or typography (Inter font + lucide-react icons remain).
- Internationalization or RTL support.

## Dependencies

- Tailwind config (`tailwind.config.ts`) — must add semantic color tokens.
- `frontend/src/styles/globals.css` (or equivalent) — must set `color-scheme: light` and scrollbar styling.
- `frontend/src/components/ui/GlassCard.tsx` and any other shared layout primitive — must be re-themed.
- Recharts wrappers / shared `ChartTooltip` component — created or updated.
- All page-level files in `frontend/src/pages/`.
- All component files in `frontend/src/components/`.

---

## Implementation Prompt (paste into `/speckit.implement`)

> Implement the white-theme overhaul defined in `specs/002-white-theme-overhaul/spec.md` end-to-end. Work in this order to avoid breakage and zero new TS/ESLint errors:
>
> 1. **Token foundation.**
>    - Create `frontend/src/styles/theme.ts` exporting the surface / text / border / accent / status / chart token groups described in FR-003. Export both Tailwind class strings (for use with `cn()`) and raw hex values (for Recharts).
>    - Update `tailwind.config.ts` to add the semantic colors: `background`, `foreground`, `card`, `card-foreground`, `muted`, `muted-foreground`, `border`, `input`, `ring`, `primary` (`#4f46e5`), `primary-foreground` (`#ffffff`), `accent` (`#7c3aed`), `destructive` (`#dc2626`).
>    - Update `frontend/src/index.css` (or `globals.css`): set `html { color-scheme: light; background: #f7f7fb; }`, body text default `#0f172a`, themed scrollbars (`scrollbar-color: #cbd5e1 #f1f5f9`), and a `:root` CSS variable mirror of the Tailwind semantic tokens.
>    - Add `<meta name="color-scheme" content="light">` to `index.html`.
>
> 2. **Shared primitives.** Re-theme in this order, running `npm run typecheck` (or `tsc --noEmit`) after each:
>    - `components/ui/GlassCard.tsx` → white card, `border-slate-200`, `shadow-sm`.
>    - `components/ui/StatusIndicator.tsx` and any status-pill component → light-tint variants per FR-007.
>    - `components/ui/Button` (or button utility) → primary/secondary/ghost/destructive per FR-009.
>    - `components/ui/Input`, `Select`, `Textarea`, `Switch`, `Tooltip`, `Modal`/`Dialog`, `Toast`, `Popover`, `Dropdown`, `DatePicker` → per FR-002 and FR-010.
>    - Create `components/charts/ChartTooltip.tsx` (white card, slate-700 labels, slate-200 border, `shadow-md`) and a `chartTheme` export with grid/axis/series colors per FR-005.
>
> 3. **Layout shells.** Re-theme `components/layout/Sidebar.tsx`, `TopBar.tsx`, `MobileDrawer.tsx`, `AppShell.tsx`. Replace any `bg-[#0a0a0f]` / `bg-white/[0.0X]` / `text-white/XX` with semantic tokens.
>
> 4. **Pages.** For each file in `frontend/src/pages/*.tsx`, find-and-replace the forbidden tokens with the new ones using the mapping table below; preserve gradient accents where they sit on white surfaces. Verify the page after each edit.
>    - `bg-[#0a0a0f]`, `bg-[#0b0b14]`, `bg-black` → `bg-white` (page) or `bg-slate-50` (page bg) or keep `bg-black/50` only for modal overlays.
>    - `bg-white/[0.03]`, `bg-white/[0.02]`, `bg-white/[0.015]` → `bg-white`.
>    - `bg-white/[0.04]`, `bg-white/[0.05]`, `bg-white/[0.06]` → `bg-slate-50` or `bg-slate-100`.
>    - `border-white/[0.06]`, `border-white/[0.04]` → `border-slate-200` or `border-slate-100`.
>    - `text-white`, `text-white/90`, `text-white/80` → `text-slate-900` (on white surfaces) or keep `text-white` only on gradient/brand surfaces.
>    - `text-white/70`, `text-white/60`, `text-white/50` → `text-slate-600`.
>    - `text-white/40`, `text-white/30`, `text-white/25`, `text-white/20` → `text-slate-400` or `text-slate-500`.
>    - `text-white/10` → `text-slate-300`.
>    - Status-color tokens like `text-emerald-400`, `text-amber-400`, `text-red-400` on dark → `text-emerald-700`, `text-amber-700`, `text-red-700` on light tints.
>    - Neon glow shadows (`shadow-[0_0_30px_rgba(139,92,246,0.15)]`) → `shadow-md` or `ring-2 ring-indigo-500/20`.
>
> 5. **Floating surfaces audit.** Open every modal, dialog, popover, toast, tooltip, dropdown in the running app; fix any leftover dark tokens. Specifically verify:
>    - `pages/Reports.tsx` → `ReportDetailModal` (header gradient + white body).
>    - `components/decisions/UndoButton.tsx` confirm-state popover.
>    - Any settings-save confirmation toast.
>    - Recharts default tooltips on Analytics + Dashboard.
>
> 6. **Charts.** Update every Recharts usage to import `chartTheme` and `<ChartTooltip />`. Replace any inline series colors with the curated light palette.
>
> 7. **Verification & guardrails.**
>    - Run `npm run typecheck`, `npm run lint`, and `npm run build` — must all pass with zero new errors.
>    - Run a repo-wide grep for the forbidden patterns; expected result is zero matches outside the documented allow-list:
>      ```
>      grep -rE "text-white/[0-9]|bg-white/\[0\.0|border-white/\[0\.0|bg-\[#0a0a0f\]|bg-\[#0b0b14\]" frontend/src
>      ```
>      (PowerShell: `Get-ChildItem frontend/src -Recurse -Include *.ts,*.tsx,*.css | Select-String -Pattern 'text-white/[0-9]|bg-white/\[0\.0|border-white/\[0\.0|bg-\[#0a0a0f\]|bg-\[#0b0b14\]'`)
>    - Manually load each of the 11 routes plus every floating surface listed in US2 and confirm SC-001…SC-009.
>    - Verify HTML email templates render unchanged by triggering a KPI report email and a supplier order email in dev.
>
> 8. **Cleanup.**
>    - Delete dead dark-theme CSS rules.
>    - Update README / docs screenshots if any are committed in the repo.
>    - Note the theme change in the project changelog or PR description.
>
> Constraints: zero backend changes; zero new TypeScript errors; preserve all existing behavior, animations, and data flows; preserve brand gradient accents on CTAs and headers; remain WCAG AA compliant.
