import { motion } from "framer-motion";
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Search,
  ChevronLeft,
  ChevronRight,
  Cpu,
  FileText,
  Layers,
  Coffee,
  Sparkles,
  Package,
  type LucideIcon,
} from "lucide-react";
import { StockLevelBadge } from "./StockLevelBadge";
import { GlassCard } from "@/components/ui/GlassCard";
import { cn, formatCurrency } from "@/lib/utils";
import type { InventoryItem } from "@/types/inventory";

interface InventoryTableProps {
  items: InventoryItem[];
  total: number;
  page: number;
  pages: number;
  search: string;
  onSearchChange: (q: string) => void;
  categoryFilter: string | null;
  categories: string[];
  onCategoryChange: (cat: string | null) => void;
  statusFilter: string | null;
  onStatusChange: (status: string | null) => void;
  sortBy: string;
  sortOrder: string;
  onSort: (field: string) => void;
  onPageChange: (page: number) => void;
  isLoading: boolean;
}

const statuses = [
  { value: null, label: "All Status" },
  { value: "normal", label: "Normal" },
  { value: "low_stock", label: "Low Stock" },
  { value: "out_of_stock", label: "Out of Stock" },
  { value: "reorder_pending", label: "Reorder Pending" },
];

const categoryConfig: Record<string, { icon: LucideIcon; gradient: string }> = {
  Electronics: { icon: Cpu, gradient: "from-cyan-500 to-blue-500" },
  "Office Supplies": { icon: FileText, gradient: "from-amber-500 to-orange-500" },
  "Raw Materials": { icon: Layers, gradient: "from-violet-500 to-purple-500" },
  "Food & Beverage": { icon: Coffee, gradient: "from-emerald-500 to-teal-500" },
  "Cleaning Supplies": { icon: Sparkles, gradient: "from-pink-500 to-rose-500" },
};

function getCategoryConfig(cat: string) {
  return categoryConfig[cat] ?? { icon: Package, gradient: "from-slate-500 to-zinc-500" };
}

export function InventoryTable({
  items,
  total,
  page,
  pages,
  search,
  onSearchChange,
  categoryFilter,
  categories,
  onCategoryChange,
  statusFilter,
  onStatusChange,
  sortBy,
  sortOrder,
  onSort,
  onPageChange,
  isLoading,
}: InventoryTableProps) {
  const SortIcon = ({ field }: { field: string }) => {
    if (sortBy !== field) return <ArrowUpDown className="h-3.5 w-3.5 text-white/20" />;
    return sortOrder === "asc" ? (
      <ArrowUp className="h-3.5 w-3.5 text-purple-400" />
    ) : (
      <ArrowDown className="h-3.5 w-3.5 text-purple-400" />
    );
  };

  return (
    <GlassCard className="overflow-hidden">
      {/* Filters Bar */}
      <div className="flex flex-wrap items-center gap-3 border-b border-white/[0.06] p-4">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/30" />
          <input
            type="text"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search by name or SKU..."
            className="w-full rounded-xl border border-white/[0.06] bg-white/[0.03] py-2 pl-10 pr-4 text-sm text-white placeholder:text-white/30 outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/20 transition-all"
          />
        </div>

        {/* Category Filter */}
        <select
          value={categoryFilter ?? ""}
          onChange={(e) => onCategoryChange(e.target.value || null)}
          className="rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-sm text-white outline-none focus:border-purple-500/50 appearance-none cursor-pointer"
        >
          <option value="" className="bg-white text-slate-900">All Categories</option>
          {categories.map((c) => (
            <option key={c} value={c} className="bg-white text-slate-900">
              {c}
            </option>
          ))}
        </select>

        {/* Status Filter */}
        <select
          value={statusFilter ?? ""}
          onChange={(e) => onStatusChange(e.target.value || null)}
          className="rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-sm text-white outline-none focus:border-purple-500/50 appearance-none cursor-pointer"
        >
          {statuses.map((s) => (
            <option key={s.label} value={s.value ?? ""} className="bg-white text-slate-900">
              {s.label}
            </option>
          ))}
        </select>

        <span className="text-xs text-white/30">
          {total} item{total !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-white/[0.06] text-left text-xs font-medium uppercase tracking-wider text-white/40">
              <th
                className="cursor-pointer px-4 py-3 hover:text-white/60 transition-colors"
                onClick={() => onSort("name")}
              >
                <span className="inline-flex items-center gap-1.5">
                  Product <SortIcon field="name" />
                </span>
              </th>
              <th
                className="cursor-pointer px-4 py-3 hover:text-white/60 transition-colors"
                onClick={() => onSort("sku")}
              >
                <span className="inline-flex items-center gap-1.5">
                  SKU <SortIcon field="sku" />
                </span>
              </th>
              <th
                className="cursor-pointer px-4 py-3 hover:text-white/60 transition-colors"
                onClick={() => onSort("category")}
              >
                <span className="inline-flex items-center gap-1.5">
                  Category <SortIcon field="category" />
                </span>
              </th>
              <th
                className="cursor-pointer px-4 py-3 text-right hover:text-white/60 transition-colors"
                onClick={() => onSort("current_stock")}
              >
                <span className="inline-flex items-center gap-1.5">
                  Stock <SortIcon field="current_stock" />
                </span>
              </th>
              <th className="px-4 py-3">Status</th>
              <th
                className="cursor-pointer px-4 py-3 text-right hover:text-white/60 transition-colors"
                onClick={() => onSort("unit_cost")}
              >
                <span className="inline-flex items-center gap-1.5">
                  Unit Cost <SortIcon field="unit_cost" />
                </span>
              </th>
              <th className="px-4 py-3 text-right">Value</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={7} className="py-16 text-center">
                  <div className="flex justify-center">
                    <div className="h-6 w-6 animate-spin rounded-full border-2 border-purple-500 border-t-transparent" />
                  </div>
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-16 text-center text-sm text-white/30">
                  No inventory items found
                </td>
              </tr>
            ) : (
              items.map((item, idx) => (
                <motion.tr
                  key={item.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.03, duration: 0.25 }}
                  className="group border-b border-white/[0.03] hover:bg-white/[0.03] transition-colors"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      {/* Category icon */}
                      {(() => {
                        const cfg = getCategoryConfig(item.category);
                        const CatIcon = cfg.icon;
                        return (
                          <div
                            className={cn(
                              "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br shadow-md",
                              cfg.gradient
                            )}
                          >
                            <CatIcon className="h-4 w-4 text-white" />
                          </div>
                        );
                      })()}
                      <div>
                        <span className="text-sm font-medium text-white group-hover:text-white/90 transition-colors">
                          {item.name}
                        </span>
                        <p className="text-[10px] text-white/25 mt-0.5 uppercase tracking-wider">
                          {item.category}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center rounded-lg bg-white/[0.04] px-2.5 py-1 font-mono text-[11px] text-white/50 border border-white/[0.04]">
                      {item.sku}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {(() => {
                      return (
                        <span className={cn(
                          "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium",
                          "bg-white/[0.03] text-white/50 border border-white/[0.04]"
                        )}>
                          {item.category}
                        </span>
                      );
                    })()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex flex-col items-end gap-1">
                      <div>
                        <span
                          className={cn(
                            "text-sm font-semibold tabular-nums",
                            item.status === "out_of_stock"
                              ? "text-red-400"
                              : item.status === "low_stock"
                              ? "text-amber-400"
                              : "text-white"
                          )}
                        >
                          {item.current_stock.toLocaleString()}
                        </span>
                        <span className="text-[10px] text-white/20 ml-1">
                          / {item.reorder_threshold}
                        </span>
                      </div>
                      {/* Mini stock bar */}
                      <div className="h-1 w-16 overflow-hidden rounded-full bg-white/[0.06]">
                        <motion.div
                          className={cn(
                            "h-full rounded-full",
                            item.status === "out_of_stock"
                              ? "bg-red-500"
                              : item.status === "low_stock"
                              ? "bg-amber-500"
                              : "bg-emerald-500"
                          )}
                          initial={{ width: 0 }}
                          animate={{
                            width: `${Math.min((item.current_stock / Math.max(item.reorder_threshold * 2, 1)) * 100, 100)}%`,
                          }}
                          transition={{ duration: 0.6, delay: idx * 0.03 }}
                        />
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <StockLevelBadge
                      status={item.status}
                      currentStock={item.current_stock}
                      threshold={item.reorder_threshold}
                    />
                  </td>
                  <td className="px-4 py-3 text-right text-sm text-white/60 tabular-nums">
                    {formatCurrency(item.unit_cost)}
                  </td>
                  <td className="px-4 py-3 text-right text-sm font-medium text-white tabular-nums">
                    {formatCurrency(item.unit_cost * item.current_stock)}
                  </td>
                </motion.tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between border-t border-white/[0.06] px-4 py-3">
          <span className="text-xs text-white/30">
            Page {page} of {pages}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="rounded-lg p-1.5 text-white/40 hover:bg-white/5 hover:text-white/70 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page >= pages}
              className="rounded-lg p-1.5 text-white/40 hover:bg-white/5 hover:text-white/70 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </GlassCard>
  );
}
