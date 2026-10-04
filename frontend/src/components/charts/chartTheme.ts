/**
 * Recharts theme tokens for the white-theme overhaul (spec 002, US4).
 *
 * Every Recharts visualization across the app references these tokens so that
 * grid lines, axis ticks, tooltips, and series colors stay coherent and
 * WCAG-AA legible on white surfaces.
 */
import type { CSSProperties } from "react";

/** Soft slate grid lines on white. */
export const CHART_GRID_STROKE = "#E2E8F0";
/** Axis tick label color — slate-500. */
export const CHART_AXIS_TICK = "#64748B";
/** Axis line color — slate-200. */
export const CHART_AXIS_LINE = "#CBD5E1";
/** Inactive (background) track for radial bars / gauges. */
export const CHART_TRACK = "#E2E8F0";

/**
 * Curated series palette — all pass AA contrast against white and remain
 * distinct in print/black-and-white reproductions.
 *
 * Order is intentional: primary brand colors first, then complementary
 * categorical colors.
 */
export const CHART_PALETTE = [
  "#4F46E5", // indigo-600
  "#7C3AED", // violet-600
  "#06B6D4", // cyan-500
  "#10B981", // emerald-500
  "#F59E0B", // amber-500
  "#F43F5E", // rose-500
] as const;

/**
 * Inline-style object for Recharts `<Tooltip contentStyle={...} />` consumers
 * that cannot use the React `<ChartTooltip />` component (e.g. PieChart with
 * default tooltip rendering). Prefer `<ChartTooltip />` where possible.
 */
export const chartTooltipContentStyle: CSSProperties = {
  background: "#FFFFFF",
  border: "1px solid #E2E8F0",
  borderRadius: 10,
  boxShadow:
    "0 1px 3px rgba(15, 23, 42, 0.06), 0 8px 24px rgba(15, 23, 42, 0.08)",
  padding: "10px 12px",
  fontSize: 12,
};

export const chartTooltipLabelStyle: CSSProperties = {
  color: "#475569",
  fontSize: 11,
  fontWeight: 600,
  marginBottom: 4,
};

export const chartTooltipItemStyle: CSSProperties = {
  color: "#0F172A",
  fontSize: 13,
  fontWeight: 500,
};

/** Convenience: gradient stop colors for shaded area charts. */
export function gradientStops(color: string) {
  return { from: color, to: `${color}00` };
}

export const chartTheme = {
  grid: CHART_GRID_STROKE,
  axisTick: CHART_AXIS_TICK,
  axisLine: CHART_AXIS_LINE,
  track: CHART_TRACK,
  palette: CHART_PALETTE,
  tooltip: {
    contentStyle: chartTooltipContentStyle,
    labelStyle: chartTooltipLabelStyle,
    itemStyle: chartTooltipItemStyle,
  },
  gradientStops,
} as const;

export default chartTheme;
