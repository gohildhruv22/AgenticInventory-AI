import { motion } from "framer-motion";
import { KPICard } from "@/components/charts/KPICard";
import { GlassCard } from "@/components/ui/GlassCard";
import { StatusIndicator } from "@/components/ui/StatusIndicator";
import { StockLevelBadge } from "@/components/inventory/StockLevelBadge";
import { fadeInUp, pageTransition } from "@/lib/animations";
import { formatCurrency, cn } from "@/lib/utils";
import { useKPIMetrics } from "@/hooks/useKPIMetrics";
import { useLowStockItems } from "@/hooks/useInventory";
import { useWebSocket } from "@/hooks/useWebSocket";
import {
  Package,
  DollarSign,
  AlertTriangle,
  ShieldCheck,
  Layers,
  TrendingDown,
  Cpu,
  FileText,
  Coffee,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

const categoryIcons: Record<string, { icon: LucideIcon; gradient: string }> = {
  Electronics: { icon: Cpu, gradient: "from-cyan-500 to-blue-500" },
  "Office Supplies": { icon: FileText, gradient: "from-amber-500 to-orange-500" },
  "Raw Materials": { icon: Layers, gradient: "from-violet-500 to-purple-500" },
  "Food & Beverage": { icon: Coffee, gradient: "from-emerald-500 to-teal-500" },
  "Cleaning Supplies": { icon: Sparkles, gradient: "from-pink-500 to-rose-500" },
};

export default function Dashboard() {
  const { data: stats } = useKPIMetrics();
  const { data: lowStockItems, isLoading: lowStockLoading } = useLowStockItems();
  const { status: wsStatus } = useWebSocket();

  return (
    <motion.div
      variants={pageTransition}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-6"
    >
      <motion.div variants={fadeInUp} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">
            Real-time inventory intelligence overview
          </p>
        </div>
        <StatusIndicator status={wsStatus} label={wsStatus} />
      </motion.div>

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <KPICard
          label="Total Items"
          value={stats?.total_items ?? 0}
          icon={Package}
          gradient="bg-gradient-to-br from-purple-500 to-pink-500"
        />
        <KPICard
          label="Inventory Value"
          value={stats?.total_value ?? 0}
          format={formatCurrency}
          icon={DollarSign}
          gradient="bg-gradient-to-br from-blue-500 to-cyan-500"
        />
        <KPICard
          label="Low Stock"
          value={stats?.low_stock_count ?? 0}
          icon={AlertTriangle}
          gradient="bg-gradient-to-br from-amber-500 to-orange-500"
        />
        <KPICard
          label="Out of Stock"
          value={stats?.out_of_stock_count ?? 0}
          icon={TrendingDown}
          gradient="bg-gradient-to-br from-red-500 to-rose-500"
        />
        <KPICard
          label="Healthy"
          value={stats?.healthy_count ?? 0}
          icon={ShieldCheck}
          gradient="bg-gradient-to-br from-emerald-500 to-teal-500"
        />
        <KPICard
          label="Categories"
          value={stats?.categories ?? 0}
          icon={Layers}
          gradient="bg-gradient-to-br from-violet-500 to-indigo-500"
        />
      </div>

      {/* Low Stock Alerts */}
      <motion.div variants={fadeInUp}>
        <GlassCard className="p-6">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                Low Stock Alerts
              </h2>
              <p className="mt-0.5 text-xs text-slate-500">
                Items at or below their reorder threshold
              </p>
            </div>
            <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700 ring-1 ring-amber-200">
              {lowStockItems?.length ?? 0} items
            </span>
          </div>

          {lowStockLoading ? (
            <div className="flex justify-center py-8">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
            </div>
          ) : !lowStockItems || lowStockItems.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-400">
              All items are well stocked
            </p>
          ) : (
            <div className="space-y-2">
              {lowStockItems.slice(0, 8).map((item, idx) => (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50/60 px-4 py-3 transition-colors hover:bg-white hover:border-violet-100"
                >
                  <div className="flex items-center gap-3">
                    {(() => {
                      const cfg = categoryIcons[item.category] ?? { icon: Package, gradient: "from-slate-500 to-zinc-500" };
                      const CatIcon = cfg.icon;
                      return (
                        <div className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br shadow-sm", cfg.gradient)}>
                          <CatIcon className="h-3.5 w-3.5 text-white" />
                        </div>
                      );
                    })()}
                    <div className="flex flex-col">
                      <span className="text-sm font-medium text-slate-900">
                        {item.name}
                      </span>
                      <span className="text-xs text-slate-500">
                        {item.sku} &middot; {item.category}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <span className="text-sm font-semibold tabular-nums text-slate-900">
                        {item.current_stock}
                      </span>
                      <span className="text-xs text-slate-400">
                        {" "}
                        / {item.reorder_threshold}
                      </span>
                    </div>
                    <StockLevelBadge
                      status={item.status}
                      currentStock={item.current_stock}
                      threshold={item.reorder_threshold}
                    />
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </GlassCard>
      </motion.div>

      {/* System Status */}
      <motion.div variants={fadeInUp}>
        <GlassCard className="p-6">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">System Status</h2>
          <div className="flex flex-wrap gap-6">
            <StatusIndicator status="healthy" label="API Server" />
            <StatusIndicator status={wsStatus} label="WebSocket" />
            <StatusIndicator status="healthy" label="Database" />
            <StatusIndicator status="healthy" label="Redis Cache" />
            <StatusIndicator status="processing" label="Agent Pipeline" />
          </div>
        </GlassCard>
      </motion.div>
    </motion.div>
  );
}
