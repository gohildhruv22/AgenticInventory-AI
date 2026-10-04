/**
 * AgenticInventory AI — Centralized Theme Tokens (spec 002, US6)
 *
 * Single source of truth for surface / text / border / accent / status / chart
 * colors. Components should reference these via `theme.<group>.<token>` instead
 * of hard-coding utility classes or hex values.
 *
 * Two parallel APIs are exported:
 *  - Class string maps (for Tailwind + `cn()` composition in JSX).
 *  - Raw hex maps (for Recharts, framer-motion `style` props, inline SVG).
 *
 * NOTE: the `globals.css` compatibility layer continues to remap any legacy
 * dark tokens (`text-white/X`, `bg-white/[0.0X]`, …) to these same light
 * values at the CSS level. New code should consume these tokens directly.
 */

// ─── Class strings (Tailwind) ────────────────────────────────────────────
export const surface = {
  page: "bg-[#FAFBFD]",
  card: "bg-white",
  cardHover: "hover:bg-slate-50",
  soft: "bg-slate-50",
  softer: "bg-[#F8F9FC]",
  muted: "bg-slate-100",
  inverted: "bg-slate-900",
  overlay: "bg-slate-900/50",
} as const;

export const text = {
  primary: "text-slate-900",
  secondary: "text-slate-600",
  muted: "text-slate-500",
  faint: "text-slate-400",
  disabled: "text-slate-300",
  onAccent: "text-white",
  brand: "text-purple-700",
  link: "text-indigo-600 hover:text-indigo-700",
} as const;

export const border = {
  subtle: "border-slate-100",
  default: "border-slate-200",
  strong: "border-slate-300",
  brand: "border-purple-200",
  focusRing: "ring-2 ring-indigo-500/40",
} as const;

export const accent = {
  gradient: "bg-gradient-to-r from-indigo-500 via-violet-500 to-pink-500",
  gradientShadow: "shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40",
  gradientText:
    "bg-gradient-to-r from-purple-600 via-pink-500 to-cyan-600 bg-clip-text text-transparent",
  ring: "ring-2 ring-indigo-500/20",
} as const;

/**
 * Status pill tokens — single source of truth for FR-007.
 * Each variant resolves to a `bg-*-50 text-*-700 border-*-200` triplet that
 * remains legible on a white card and matches WCAG AA.
 */
export const status = {
  success: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  warning: "bg-amber-50 text-amber-700 border border-amber-200",
  danger: "bg-red-50 text-red-700 border border-red-200",
  info: "bg-indigo-50 text-indigo-700 border border-indigo-200",
  neutral: "bg-slate-50 text-slate-700 border border-slate-200",
  brand: "bg-purple-50 text-purple-700 border border-purple-200",
  accent: "bg-pink-50 text-pink-700 border border-pink-200",
  cyan: "bg-cyan-50 text-cyan-700 border border-cyan-200",
} as const;

export const button = {
  primary: [
    "bg-gradient-to-r from-indigo-500 via-violet-500 to-pink-500",
    "text-white shadow-lg shadow-indigo-500/25",
    "hover:shadow-indigo-500/40 hover:scale-[1.02] active:scale-[0.98]",
  ].join(" "),
  secondary: [
    "bg-white border border-slate-200 text-slate-700",
    "hover:bg-slate-50 hover:border-slate-300 active:scale-[0.98]",
  ].join(" "),
  ghost: "text-slate-600 hover:text-slate-900 hover:bg-slate-100 active:scale-[0.98]",
  destructive: "bg-red-600 text-white hover:bg-red-700 active:scale-[0.98]",
} as const;

export const input = {
  base: [
    "bg-white border border-slate-200 text-slate-900",
    "placeholder:text-slate-400",
    "focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20",
  ].join(" "),
} as const;

// ─── Raw hex values (Recharts, SVG, inline styles) ───────────────────────
export const colors = {
  bgPage: "#FAFBFD",
  bgCard: "#FFFFFF",
  bgSoft: "#F8F9FC",
  bgMuted: "#F1F5F9",
  textPrimary: "#0F172A",
  textSecondary: "#475569",
  textMuted: "#64748B",
  textFaint: "#94A3B8",
  borderSubtle: "#F1F5F9",
  borderDefault: "#E2E8F0",
  borderStrong: "#CBD5E1",
  brandIndigo: "#4F46E5",
  brandViolet: "#7C3AED",
  brandPink: "#EC4899",
  success: "#10B981",
  warning: "#F59E0B",
  danger: "#EF4444",
  info: "#4F46E5",
} as const;

export const theme = {
  surface,
  text,
  border,
  accent,
  status,
  button,
  input,
  colors,
} as const;

export default theme;
