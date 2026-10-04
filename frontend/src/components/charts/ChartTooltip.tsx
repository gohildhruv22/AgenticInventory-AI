import type { TooltipProps } from "recharts";
import {
  chartTooltipContentStyle,
  chartTooltipItemStyle,
  chartTooltipLabelStyle,
} from "./chartTheme";

interface ChartTooltipProps extends TooltipProps<number | string, string> {
  /** Optional formatter applied to numeric values before display. */
  format?: (v: number) => string;
  /** Label shown above the entry list when no payload label is available. */
  fallbackLabel?: string;
}

/**
 * Shared light-theme Recharts tooltip (spec 002, US4 / FR-005).
 *
 * Renders a white card with slate-700 labels and slate-200 border, replacing
 * Recharts' default dark tooltip. Pass to any chart via:
 *   <Tooltip content={<ChartTooltip />} />
 */
export function ChartTooltip(props: ChartTooltipProps) {
  const {
    active,
    payload,
    label,
    format,
    fallbackLabel,
  } = props as ChartTooltipProps & {
    payload?: ReadonlyArray<Record<string, unknown>>;
    label?: string | number;
  };
  if (!active || !payload || payload.length === 0) return null;

  const heading = label ?? fallbackLabel;

  return (
    <div style={chartTooltipContentStyle}>
      {heading != null && heading !== "" && (
        <div style={chartTooltipLabelStyle}>{String(heading)}</div>
      )}
      <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
        {payload.map((entry: Record<string, unknown>, idx: number) => {
          const raw = entry.value;
          const display =
            typeof raw === "number" && format ? format(raw) : String(raw ?? "");
          return (
            <li
              key={`${entry.dataKey ?? idx}`}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginTop: idx === 0 ? 0 : 4,
                ...chartTooltipItemStyle,
              }}
            >
              <span
                aria-hidden
                style={{
                  display: "inline-block",
                  width: 8,
                  height: 8,
                  borderRadius: 999,
                  background: (entry.color as string) ?? "#4F46E5",
                }}
              />
              <span style={{ color: "#64748B", fontWeight: 500 }}>
                {String(entry.name ?? entry.dataKey ?? "")}
              </span>
              <span style={{ marginLeft: "auto", color: "#0F172A", fontWeight: 600 }}>
                {display}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default ChartTooltip;
