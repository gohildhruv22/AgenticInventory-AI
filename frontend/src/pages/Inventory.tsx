import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Plus,
  Package,
  AlertTriangle,
  TrendingDown,
  DollarSign,
  Cpu,
  FileText,
  Layers,
  Coffee,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { InventoryTable } from "@/components/inventory/InventoryTable";
import { ReorderAlert } from "@/components/inventory/ReorderAlert";
import { GradientButton } from "@/components/ui/GradientButton";
import { GlassCard } from "@/components/ui/GlassCard";
import { useInventory, useCategories } from "@/hooks/useInventory";
import { fadeInUp, pageTransition } from "@/lib/animations";
import { debounce, formatCurrency, cn } from "@/lib/utils";
import type { InventoryItemCreate } from "@/types/inventory";

const categoryIcons: Record<string, { icon: LucideIcon; gradient: string }> = {
  Electronics: { icon: Cpu, gradient: "from-cyan-500 to-blue-500" },
  "Office Supplies": { icon: FileText, gradient: "from-amber-500 to-orange-500" },
  "Raw Materials": { icon: Layers, gradient: "from-violet-500 to-purple-500" },
  "Food & Beverage": { icon: Coffee, gradient: "from-emerald-500 to-teal-500" },
  "Cleaning Supplies": { icon: Sparkles, gradient: "from-pink-500 to-rose-500" },
};

export default function Inventory() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState("name");
  const [sortOrder, setSortOrder] = useState("asc");
  const [showAddDialog, setShowAddDialog] = useState(false);

  const debouncedSetSearch = useCallback(
    debounce((q: string) => {
      setDebouncedSearch(q);
      setPage(1);
    }, 300),
    []
  );

  const handleSearchChange = (q: string) => {
    setSearch(q);
    debouncedSetSearch(q);
  };

  const { data: categories } = useCategories();

  const {
    items,
    total,
    pages,
    isLoading,
    createItem,
    isCreating,
  } = useInventory({
    page,
    per_page: 50,
    category: categoryFilter,
    status: statusFilter,
    search: debouncedSearch || undefined,
    sort_by: sortBy,
    sort_order: sortOrder,
  });

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setSortOrder("asc");
    }
    setPage(1);
  };

  const handleCategoryChange = (cat: string | null) => {
    setCategoryFilter(cat);
    setPage(1);
  };

  const handleStatusChange = (status: string | null) => {
    setStatusFilter(status);
    setPage(1);
  };

  const handleAddItem = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const data: InventoryItemCreate = {
      name: fd.get("name") as string,
      sku: fd.get("sku") as string,
      category: fd.get("category") as string,
      current_stock: Number(fd.get("current_stock")) || 0,
      reorder_threshold: Number(fd.get("reorder_threshold")),
      safety_stock: Number(fd.get("safety_stock")) || 0,
      lead_time_days: Number(fd.get("lead_time_days")) || 7,
      unit_cost: Number(fd.get("unit_cost")),
    };
    await createItem(data);
    setShowAddDialog(false);
  };

  return (
    <>
      <motion.div
        variants={pageTransition}
        initial="initial"
        animate="animate"
        exit="exit"
        className="space-y-6"
      >
        <motion.div
          variants={fadeInUp}
          className="flex items-center justify-between"
        >
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">Inventory</h1>
            <p className="text-sm text-slate-500 mt-1">
              Manage stock levels with AI-powered monitoring
            </p>
          </div>
          <GradientButton onClick={() => setShowAddDialog(true)}>
            <Plus className="h-4 w-4" />
            Add Item
          </GradientButton>
        </motion.div>

        {/* ─── KPI Summary Cards ──────────────────────────── */}
        <motion.div variants={fadeInUp} className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition-all hover:border-violet-200 hover:shadow-[0_4px_14px_rgba(124,58,237,0.08)]">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 shadow-md">
              <Package className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="text-lg font-bold text-slate-900 tabular-nums">{total}</p>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Total Items</p>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition-all hover:border-violet-200 hover:shadow-[0_4px_14px_rgba(124,58,237,0.08)]">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-amber-500 to-orange-500 shadow-md">
              <AlertTriangle className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="text-lg font-bold text-amber-600 tabular-nums">
                {items.filter((i) => i.status === "low_stock").length}
              </p>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Low Stock</p>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition-all hover:border-violet-200 hover:shadow-[0_4px_14px_rgba(124,58,237,0.08)]">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-red-500 to-rose-500 shadow-md">
              <TrendingDown className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="text-lg font-bold text-red-600 tabular-nums">
                {items.filter((i) => i.status === "out_of_stock").length}
              </p>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Out of Stock</p>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition-all hover:border-violet-200 hover:shadow-[0_4px_14px_rgba(124,58,237,0.08)]">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 shadow-md">
              <DollarSign className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="text-lg font-bold text-slate-900 tabular-nums">
                {formatCurrency(
                  items.reduce((sum, i) => sum + i.unit_cost * i.current_stock, 0)
                )}
              </p>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Total Value</p>
            </div>
          </div>
        </motion.div>

        {/* ─── Category Quick Filters ─────────────────────── */}
        {(categories ?? []).length > 0 && (
          <motion.div variants={fadeInUp} className="flex flex-wrap gap-2">
            <button
              onClick={() => handleCategoryChange(null)}
              className={cn(
                "flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-medium transition-all",
                !categoryFilter
                  ? "border-violet-200 bg-violet-50 text-violet-700 shadow-sm shadow-violet-500/5"
                  : "border-slate-200 bg-white text-slate-600 hover:border-violet-200 hover:bg-violet-50/40 hover:text-violet-700"
              )}
            >
              <Package className="h-3.5 w-3.5" />
              All
            </button>
            {(categories ?? []).map((cat) => {
              const cfg = categoryIcons[cat] ?? { icon: Package, gradient: "from-slate-500 to-zinc-500" };
              const CatIcon = cfg.icon;
              const active = categoryFilter === cat;
              return (
                <button
                  key={cat}
                  onClick={() => handleCategoryChange(active ? null : cat)}
                  className={cn(
                    "flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-medium transition-all",
                    active
                      ? "border-violet-200 bg-violet-50 text-violet-700 shadow-sm shadow-violet-500/5"
                      : "border-slate-200 bg-white text-slate-600 hover:border-violet-200 hover:bg-violet-50/40 hover:text-violet-700"
                  )}
                >
                  <CatIcon className="h-3.5 w-3.5" />
                  {cat}
                </button>
              );
            })}
          </motion.div>
        )}

        <motion.div variants={fadeInUp}>
          <InventoryTable
            items={items}
            total={total}
            page={page}
            pages={pages}
            search={search}
            onSearchChange={handleSearchChange}
            categoryFilter={categoryFilter}
            categories={categories ?? []}
            onCategoryChange={handleCategoryChange}
            statusFilter={statusFilter}
            onStatusChange={handleStatusChange}
            sortBy={sortBy}
            sortOrder={sortOrder}
            onSort={handleSort}
            onPageChange={setPage}
            isLoading={isLoading}
          />
        </motion.div>
      </motion.div>

      {/* Add Item Dialog */}
      {showAddDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4 backdrop-blur-sm">
          <GlassCard className="w-full max-w-lg p-6">
            <div className="mb-5">
              <h2 className="text-lg font-semibold text-slate-900">Add Inventory Item</h2>
              <p className="mt-0.5 text-xs text-slate-500">
                Create a new item — the AI pipeline will start monitoring it immediately.
              </p>
            </div>
            <form onSubmit={handleAddItem} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Name
                  </label>
                  <input
                    name="name"
                    required
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition-all focus:border-violet-400 focus:bg-white focus:ring-4 focus:ring-violet-100"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                    SKU
                  </label>
                  <input
                    name="sku"
                    required
                    pattern="^[A-Za-z0-9_-]+$"
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition-all focus:border-violet-400 focus:bg-white focus:ring-4 focus:ring-violet-100"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Category
                  </label>
                  <input
                    name="category"
                    required
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition-all focus:border-violet-400 focus:bg-white focus:ring-4 focus:ring-violet-100"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Unit Cost ($)
                  </label>
                  <input
                    name="unit_cost"
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition-all focus:border-violet-400 focus:bg-white focus:ring-4 focus:ring-violet-100"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Current Stock
                  </label>
                  <input
                    name="current_stock"
                    type="number"
                    min="0"
                    defaultValue={0}
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition-all focus:border-violet-400 focus:bg-white focus:ring-4 focus:ring-violet-100"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Reorder Threshold
                  </label>
                  <input
                    name="reorder_threshold"
                    type="number"
                    min="0"
                    required
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition-all focus:border-violet-400 focus:bg-white focus:ring-4 focus:ring-violet-100"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Safety Stock
                  </label>
                  <input
                    name="safety_stock"
                    type="number"
                    min="0"
                    defaultValue={0}
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition-all focus:border-violet-400 focus:bg-white focus:ring-4 focus:ring-violet-100"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Lead Time (days)
                  </label>
                  <input
                    name="lead_time_days"
                    type="number"
                    min="1"
                    defaultValue={7}
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition-all focus:border-violet-400 focus:bg-white focus:ring-4 focus:ring-violet-100"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <GradientButton
                  type="button"
                  variant="secondary"
                  onClick={() => setShowAddDialog(false)}
                >
                  Cancel
                </GradientButton>
                <GradientButton type="submit" loading={isCreating}>
                  Create Item
                </GradientButton>
              </div>
            </form>
          </GlassCard>
        </div>
      )}

      <ReorderAlert />
    </>
  );
}
