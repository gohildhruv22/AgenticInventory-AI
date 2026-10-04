import { motion } from "framer-motion";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { scaleIn, defaultTransition } from "@/lib/animations";
import { cn } from "@/lib/utils";
import {
  CHART_AXIS_LINE,
  CHART_AXIS_TICK,
  CHART_GRID_STROKE,
} from "./chartTheme";
import { ChartTooltip } from "./ChartTooltip";

interface TrendChartProps {
  data: Record<string, unknown>[];
  dataKey: string;
  xKey?: string;
  label?: string;
  color?: string;
  gradientFrom?: string;
  gradientTo?: string;
  format?: (v: number) => string;
  height?: number;
  className?: string;
}

export function TrendChart({
  data,
  dataKey,
  xKey = "date",
  label,
  color = "#4F46E5",
  gradientFrom,
  gradientTo,
  format,
  height = 240,
  className,
}: TrendChartProps) {
  const gFrom = gradientFrom ?? color;
  const gTo = gradientTo ?? `${color}00`;
  const gradientId = `trend-${dataKey}`;

  return (
    <motion.div
      variants={scaleIn}
      initial="initial"
      animate="animate"
      transition={defaultTransition}
      className={cn(
        "rounded-2xl border border-slate-200 bg-white p-5 shadow-sm",
        className
      )}
    >
      {label && (
        <h3 className="mb-4 text-sm font-semibold uppercase tracking-widest text-slate-500">
          {label}
        </h3>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={gFrom} stopOpacity={0.3} />
              <stop offset="100%" stopColor={gTo} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_STROKE} />
          <XAxis
            dataKey={xKey}
            tick={{ fill: CHART_AXIS_TICK, fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: CHART_AXIS_LINE }}
          />
          <YAxis
            tick={{ fill: CHART_AXIS_TICK, fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={format}
          />
          <Tooltip content={<ChartTooltip format={format} fallbackLabel={label ?? dataKey} />} />
          <Area
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            strokeWidth={2}
            fill={`url(#${gradientId})`}
            animationDuration={1200}
            animationEasing="ease-out"
          />
        </AreaChart>
      </ResponsiveContainer>
    </motion.div>
  );
}
