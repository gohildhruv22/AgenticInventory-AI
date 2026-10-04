import { motion } from "framer-motion";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import {
  ShoppingCart,
  DollarSign,
  Brain,
  Truck,
  AlertTriangle,
} from "lucide-react";
import { fadeInUp, staggerChildren, pageTransition } from "@/lib/animations";
import { formatCurrency } from "@/lib/utils";
import { KPICard } from "@/components/charts/KPICard";
import { TrendChart } from "@/components/charts/TrendChart";
import { ConfidenceGauge } from "@/components/charts/ConfidenceGauge";
import { SupplierPerfChart } from "@/components/charts/SupplierPerfChart";
import { ChartTooltip } from "@/components/charts/ChartTooltip";
import { CHART_PALETTE } from "@/components/charts/chartTheme";
import { GlassCard } from "@/components/ui/GlassCard";
import {
  useDashboardMetrics,
  useTrendData,
  useSupplierPerformance,
  useAgentActivity,
} from "@/hooks/useKPIMetrics";

const AGENT_COLORS = [
  ...CHART_PALETTE,
  "#818CF8",
];

const AGENT_LABELS: Record<string, string> = {
  decision_manager: "Decision Manager",
  forecast: "Forecast",
  monitoring: "Monitoring",
  supplier_email: "Email Agent",
  delivery_tracker: "Delivery Tracker",
  undo_rollback: "Undo & Rollback",
  reporting_kpi: "Reporting & KPI",
};

export default function Analytics() {
  const { data: metrics } = useDashboardMetrics();
  const { data: trends } = useTrendData(7);
  const { data: suppliers } = useSupplierPerformance();
  const { data: agents } = useAgentActivity();

  const m = metrics ?? {
    order_volume: 0,
    total_spend: 0,
    forecast_accuracy: null,
    avg_confidence: null,
    decisions_approved: 0,
    decisions_flagged: 0,
    active_deliveries: 0,
    low_stock_count: 0,
  };

  const agentPieData = (agents ?? []).map((a) => ({
    name: AGENT_LABELS[a.agent] ?? a.agent,
    value: a.count,
  }));

  return (
    <motion.div
      variants={pageTransition}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-6"
    >
      {/* ─── Page Header ──────────────────────────────────── */}
      <motion.div variants={fadeInUp} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Analytics</h1>
          <p className="mt-1 text-sm text-white/40">
            Real-time performance metrics and trend analysis
          </p>
        </div>
      </motion.div>

      {/* ─── KPI Cards Row ────────────────────────────────── */}
      <motion.div
        variants={staggerChildren}
        initial="initial"
        animate="animate"
        className="grid grid-cols-2 gap-4 lg:grid-cols-4"
      >
        <KPICard
          label="Order Volume"
          value={m.order_volume}
          icon={ShoppingCart}
          gradient="bg-gradient-to-br from-purple-500 to-pink-500"
        />
        <KPICard
          label="Total Spend"
          value={m.total_spend}
          format={formatCurrency}
          icon={DollarSign}
          gradient="bg-gradient-to-br from-cyan-500 to-blue-500"
        />
        <KPICard
          label="Approved"
          value={m.decisions_approved}
          icon={Brain}
          gradient="bg-gradient-to-br from-emerald-500 to-teal-500"
        />
        <KPICard
          label="Active Deliveries"
          value={m.active_deliveries}
          icon={Truck}
          gradient="bg-gradient-to-br from-amber-500 to-orange-500"
        />
      </motion.div>

      {/* ─── Confidence + Flagged/Low Stock ────────────────── */}
      <motion.div variants={fadeInUp} className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <GlassCard className="flex flex-col items-center justify-center p-6">
          <ConfidenceGauge
            value={m.forecast_accuracy ?? 0}
            label="Forecast Accuracy"
            size={160}
          />
        </GlassCard>
        <GlassCard className="flex flex-col items-center justify-center p-6">
          <ConfidenceGauge
            value={m.avg_confidence ?? 0}
            label="Avg Confidence"
            size={160}
          />
        </GlassCard>
        <GlassCard className="flex flex-col gap-4 p-6">
          <h3 className="text-sm font-semibold uppercase tracking-widest text-white/40">
            Alerts
          </h3>
          <div className="flex items-center gap-3 rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-3">
            <AlertTriangle className="h-5 w-5 text-amber-400" />
            <div>
              <p className="text-sm font-semibold text-amber-300">{m.decisions_flagged}</p>
              <p className="text-xs text-white/40">Flagged Decisions</p>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3">
            <AlertTriangle className="h-5 w-5 text-red-400" />
            <div>
              <p className="text-sm font-semibold text-red-300">{m.low_stock_count}</p>
              <p className="text-xs text-white/40">Low Stock Items</p>
            </div>
          </div>
        </GlassCard>
      </motion.div>

      {/* ─── Trend Charts ─────────────────────────────────── */}
      <motion.div variants={fadeInUp} className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TrendChart
          data={trends ?? []}
          dataKey="order_volume"
          label="Order Volume (7-Day)"
          color="#8B5CF6"
        />
        <TrendChart
          data={trends ?? []}
          dataKey="forecast_accuracy"
          label="Forecast Accuracy (%)"
          color="#06B6D4"
          format={(v) => `${v}%`}
        />
      </motion.div>

      <motion.div variants={fadeInUp} className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TrendChart
          data={trends ?? []}
          dataKey="total_spend"
          label="Daily Spend"
          color="#7C3AED"
          format={(v) => `$${v.toLocaleString()}`}
        />
        <TrendChart
          data={trends ?? []}
          dataKey="cost_savings"
          label="Cost Savings"
          color="#10B981"
          format={(v) => `$${v.toLocaleString()}`}
        />
      </motion.div>

      {/* ─── Supplier Performance + Agent Activity ─────── */}
      <motion.div variants={fadeInUp} className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SupplierPerfChart data={suppliers ?? []} />

        <GlassCard className="p-5">
          <h3 className="mb-4 text-sm font-semibold uppercase tracking-widest text-slate-500">
            Agent Activity Distribution
          </h3>
          {agentPieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={agentPieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  dataKey="value"
                  stroke="#FFFFFF"
                  strokeWidth={2}
                  animationDuration={1200}
                >
                  {agentPieData.map((_, i) => (
                    <Cell key={i} fill={AGENT_COLORS[i % AGENT_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip content={<ChartTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-[280px] items-center justify-center text-slate-500">
              <p className="text-sm">No agent activity data</p>
            </div>
          )}
          {/* Legend */}
          <div className="mt-2 flex flex-wrap gap-3">
            {agentPieData.map((d, i) => (
              <span key={d.name} className="flex items-center gap-1.5 text-xs text-slate-600">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ background: AGENT_COLORS[i % AGENT_COLORS.length] }}
                />
                {d.name} ({d.value})
              </span>
            ))}
          </div>
        </GlassCard>
      </motion.div>
    </motion.div>
  );
}
