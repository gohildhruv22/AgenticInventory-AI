import { motion } from "framer-motion";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { scaleIn, defaultTransition } from "@/lib/animations";
import { cn } from "@/lib/utils";
import {
  CHART_AXIS_LINE,
  CHART_AXIS_TICK,
  CHART_GRID_STROKE,
  CHART_PALETTE,
} from "./chartTheme";
import { ChartTooltip } from "./ChartTooltip";

interface SupplierData {
  supplier: string;
  orders: number;
  value: number;
  success_rate: number;
}

interface SupplierPerfChartProps {
  data: SupplierData[];
  height?: number;
  className?: string;
}

export function SupplierPerfChart({
  data,
  height = 280,
  className,
}: SupplierPerfChartProps) {
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
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-widest text-slate-500">
        Supplier Performance
      </h3>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
          <defs>
            <linearGradient id="barOrders" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART_PALETTE[0]} stopOpacity={0.95} />
              <stop offset="100%" stopColor={CHART_PALETTE[0]} stopOpacity={0.55} />
            </linearGradient>
            <linearGradient id="barSuccess" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART_PALETTE[3]} stopOpacity={0.95} />
              <stop offset="100%" stopColor={CHART_PALETTE[3]} stopOpacity={0.55} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_STROKE} />
          <XAxis
            dataKey="supplier"
            tick={{ fill: CHART_AXIS_TICK, fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: CHART_AXIS_LINE }}
            interval={0}
            angle={-20}
            textAnchor="end"
            height={50}
          />
          <YAxis
            tick={{ fill: CHART_AXIS_TICK, fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<ChartTooltip />} />
          <Legend
            wrapperStyle={{ paddingTop: 12 }}
            iconType="circle"
            formatter={(value: string) => (
              <span className="text-xs text-slate-600">{value}</span>
            )}
          />
          <Bar
            dataKey="orders"
            name="Orders"
            fill="url(#barOrders)"
            radius={[6, 6, 0, 0]}
            animationDuration={1000}
          />
          <Bar
            dataKey="success_rate"
            name="Success %"
            fill="url(#barSuccess)"
            radius={[6, 6, 0, 0]}
            animationDuration={1200}
          />
        </BarChart>
      </ResponsiveContainer>
    </motion.div>
  );
}
