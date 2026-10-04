import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Truck,
  PackageCheck,
  Clock,
  MapPin,
  CheckCircle2,
  Circle,
  Loader2,
  Filter,
  ChevronDown,
  ChevronUp,
  Package,
  ClipboardCheck,
  Plane,
  Calendar,
  Hash,
  Activity,
  Sparkles,
  Search,
  X,
  Trash2,
  AlertCircle,
} from "lucide-react";

import { GlassCard } from "@/components/ui/GlassCard";
import { fadeInUp, pageTransition } from "@/lib/animations";
import { cn } from "@/lib/utils";
import { api } from "@/services/api";
import { queryKeys } from "@/services/queryKeys";
import type { Delivery, DeliveryListResponse } from "@/types/delivery";

type StageKey =
  | "ordered"
  | "confirmed"
  | "shipped"
  | "in_transit"
  | "delivered";

type StageMeta = {
  key: StageKey;
  label: string;
  Icon: typeof Truck;
  gradient: string;
  pill: string;
  text: string;
  ring: string;
};

const stages: StageMeta[] = [
  {
    key: "ordered",
    label: "Ordered",
    Icon: Package,
    gradient: "from-amber-400 to-orange-500",
    pill: "bg-amber-50 text-amber-700 border-amber-200",
    text: "text-amber-600",
    ring: "ring-amber-200",
  },
  {
    key: "confirmed",
    label: "Confirmed",
    Icon: ClipboardCheck,
    gradient: "from-violet-400 to-purple-500",
    pill: "bg-violet-50 text-violet-700 border-violet-200",
    text: "text-violet-600",
    ring: "ring-violet-200",
  },
  {
    key: "shipped",
    label: "Shipped",
    Icon: Plane,
    gradient: "from-sky-400 to-blue-500",
    pill: "bg-sky-50 text-sky-700 border-sky-200",
    text: "text-sky-600",
    ring: "ring-sky-200",
  },
  {
    key: "in_transit",
    label: "In Transit",
    Icon: Truck,
    gradient: "from-cyan-400 to-blue-500",
    pill: "bg-cyan-50 text-cyan-700 border-cyan-200",
    text: "text-cyan-600",
    ring: "ring-cyan-200",
  },
  {
    key: "delivered",
    label: "Delivered",
    Icon: PackageCheck,
    gradient: "from-emerald-400 to-teal-500",
    pill: "bg-emerald-50 text-emerald-700 border-emerald-200",
    text: "text-emerald-600",
    ring: "ring-emerald-200",
  },
];

const stageByKey: Record<string, StageMeta> = Object.fromEntries(
  stages.map((s) => [s.key, s])
);

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function relativeFromNow(iso: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diff = Date.now() - then;
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hr ago`;
  const days = Math.floor(hrs / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

function daysUntil(iso: string | null): { label: string; tone: "ok" | "warn" | "late" } {
  if (!iso) return { label: "—", tone: "ok" };
  const d = new Date(iso).getTime();
  if (Number.isNaN(d)) return { label: iso, tone: "ok" };
  const diff = d - Date.now();
  const days = Math.round(diff / (1000 * 60 * 60 * 24));
  if (days > 1) return { label: `in ${days} days`, tone: days <= 2 ? "warn" : "ok" };
  if (days === 1) return { label: "tomorrow", tone: "warn" };
  if (days === 0) return { label: "today", tone: "warn" };
  return { label: `${Math.abs(days)} day${Math.abs(days) === 1 ? "" : "s"} overdue`, tone: "late" };
}

function progressPercent(d: Delivery): number {
  const idx = stages.findIndex((s) => s.key === d.current_stage);
  if (idx === -1) return 0;
  return Math.round(((idx + 1) / stages.length) * 100);
}

interface StageProgressProps {
  current: string;
}

function StageProgress({ current }: StageProgressProps) {
  const currentIdx = stages.findIndex((s) => s.key === current);
  const meta = stageByKey[current];

  return (
    <div className="flex items-center gap-2">
      {stages.map((s, i) => {
        const done = i <= currentIdx;
        const active = i === currentIdx;
        const isLast = i === stages.length - 1;
        const StepIcon = s.Icon;
        return (
          <div key={s.key} className="flex items-center gap-1.5">
            <div className="relative flex flex-col items-center">
              <div
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full border transition-all",
                  done
                    ? `bg-gradient-to-br ${s.gradient} border-transparent text-white shadow-sm`
                    : "border-slate-200 bg-white text-slate-300",
                  active && current !== "delivered" && `ring-2 ring-offset-1 ${s.ring}`
                )}
              >
                {active && current !== "delivered" ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : done ? (
                  <StepIcon className="h-3.5 w-3.5" />
                ) : (
                  <Circle className="h-3 w-3" />
                )}
              </div>
              <span
                className={cn(
                  "absolute -bottom-5 whitespace-nowrap text-[9px] font-medium",
                  done ? (meta?.text ?? "text-slate-700") : "text-slate-300"
                )}
              >
                {s.label}
              </span>
            </div>
            {!isLast && (
              <div
                className={cn(
                  "h-[2px] w-5 rounded-full transition-colors",
                  i < currentIdx
                    ? `bg-gradient-to-r ${s.gradient}`
                    : "bg-slate-200"
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

interface DeliveryRowProps {
  delivery: Delivery;
  expanded: boolean;
  onToggle: () => void;
  onDelete?: (id: string) => Promise<void> | void;
}

function DeliveryRow({ delivery, expanded, onToggle, onDelete }: DeliveryRowProps) {
  const meta =
    stageByKey[delivery.current_stage] ?? stageByKey.ordered;
  const StageIcon = meta.Icon;
  const progress = progressPercent(delivery);
  const eta = daysUntil(delivery.expected_delivery_at);
  const isDelivered = delivery.current_stage === "delivered";
  const [deletePhase, setDeletePhase] = useState<"idle" | "confirm" | "loading" | "error">("idle");
  const [deleteError, setDeleteError] = useState("");

  const handleDelete = async () => {
    if (!onDelete || deletePhase === "loading") return;
    setDeletePhase("loading");
    setDeleteError("");
    try {
      await onDelete(delivery.id);
      // Row will unmount on success.
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Delete failed");
      setDeletePhase("error");
      setTimeout(() => setDeletePhase("idle"), 3500);
    }
  };

  return (
    <GlassCard className="overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        data-testid={`delivery-row-${delivery.id}`}
        className="flex w-full flex-col gap-4 p-5 text-left transition-colors hover:bg-slate-50/60 sm:flex-row sm:items-center sm:justify-between"
      >
        <div className="flex items-start gap-4">
          <div
            className={cn(
              "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl shadow-sm",
              `bg-gradient-to-br ${meta.gradient}`
            )}
          >
            <StageIcon className="h-6 w-6 text-white" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-slate-900">
                Order #{delivery.order_id.slice(0, 8).toUpperCase()}
              </span>
              <span
                className={cn(
                  "rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                  meta.pill
                )}
              >
                {meta.label}
              </span>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1.5">
                <Calendar className="h-3.5 w-3.5" />
                <span className="font-medium text-slate-700">
                  {formatDate(delivery.expected_delivery_at)}
                </span>
                <span
                  className={cn(
                    "ml-1 rounded-md px-1.5 py-0.5 text-[10px] font-semibold",
                    eta.tone === "ok" && "bg-emerald-50 text-emerald-700",
                    eta.tone === "warn" && "bg-amber-50 text-amber-700",
                    eta.tone === "late" && "bg-rose-50 text-rose-700"
                  )}
                >
                  {eta.label}
                </span>
              </span>
              <span className="inline-flex items-center gap-1 text-slate-400">
                <Hash className="h-3 w-3" />
                <span className="font-mono">{delivery.id.slice(0, 8)}</span>
              </span>
              <span className="inline-flex items-center gap-1 text-slate-400">
                <Activity className="h-3 w-3" />
                {relativeFromNow(delivery.updated_at)}
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-4 pl-16 sm:pl-0">
          <div className="hidden md:block">
            <StageProgress current={delivery.current_stage} />
          </div>
          <div className="flex flex-col items-end gap-1">
            <div className="flex items-center gap-2">
              <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100">
                <div
                  className={cn(
                    "h-full rounded-full bg-gradient-to-r transition-all",
                    meta.gradient
                  )}
                  style={{ width: `${progress}%` }}
                />
              </div>
              <span className="text-xs font-semibold tabular-nums text-slate-600">
                {progress}%
              </span>
            </div>
            <span className="text-[10px] text-slate-400">
              {isDelivered ? "Complete" : "In progress"}
            </span>
          </div>
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-slate-400" />
          ) : (
            <ChevronDown className="h-4 w-4 text-slate-400" />
          )}
        </div>
      </button>
      <AnimatePresence initial={false}>
        {expanded ? (
          <motion.div
            key="details"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="border-t border-slate-100 bg-gradient-to-br from-slate-50/80 to-white p-6"
          >
            <div className="md:hidden mb-6 flex justify-center">
              <StageProgress current={delivery.current_stage} />
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <DetailTile
                icon={<Hash className="h-4 w-4" />}
                label="Order ID"
                value={delivery.order_id.slice(0, 8).toUpperCase()}
                hint={`Full: ${delivery.order_id}`}
              />
              <DetailTile
                icon={<Calendar className="h-4 w-4" />}
                label="Expected delivery"
                value={formatDate(delivery.expected_delivery_at)}
                hint={eta.label}
                tone={eta.tone}
              />
              <DetailTile
                icon={<Sparkles className="h-4 w-4" />}
                label="Current stage"
                value={meta.label}
                hint={`Progress ${progress}%`}
              />
              <DetailTile
                icon={<Activity className="h-4 w-4" />}
                label="Last update"
                value={relativeFromNow(delivery.updated_at)}
                hint={formatDate(delivery.updated_at)}
              />
            </div>

            <div className="mt-6">
              <h4 className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-500">
                Shipment timeline
              </h4>
              <ol className="relative space-y-3 border-l-2 border-slate-100 pl-5">
                {stages.map((s) => {
                  const StepIcon = s.Icon;
                  const idx = stages.findIndex((x) => x.key === s.key);
                  const currentIdx = stages.findIndex(
                    (x) => x.key === delivery.current_stage
                  );
                  const done = idx <= currentIdx;
                  const active = idx === currentIdx && !isDelivered;
                  return (
                    <li key={s.key} className="relative">
                      <span
                        className={cn(
                          "absolute -left-[27px] flex h-5 w-5 items-center justify-center rounded-full border-2",
                          done
                            ? `bg-gradient-to-br ${s.gradient} border-white shadow-sm`
                            : "border-slate-200 bg-white"
                        )}
                      >
                        {done ? (
                          active ? (
                            <Loader2 className="h-2.5 w-2.5 animate-spin text-white" />
                          ) : (
                            <CheckCircle2 className="h-2.5 w-2.5 text-white" />
                          )
                        ) : (
                          <Circle className="h-2 w-2 text-slate-300" />
                        )}
                      </span>
                      <div className="flex items-center gap-2">
                        <StepIcon
                          className={cn(
                            "h-3.5 w-3.5",
                            done ? s.text : "text-slate-300"
                          )}
                        />
                        <span
                          className={cn(
                            "text-sm font-medium",
                            done ? "text-slate-900" : "text-slate-400"
                          )}
                        >
                          {s.label}
                        </span>
                        {active ? (
                          <span
                            className={cn(
                              "rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider",
                              s.pill
                            )}
                          >
                            Now
                          </span>
                        ) : null}
                      </div>
                    </li>
                  );
                })}
              </ol>
            </div>

            {onDelete && (
              <div className="mt-6 flex items-center justify-end gap-2 border-t border-slate-100 pt-4">
                <AnimatePresence mode="wait" initial={false}>
                  {deletePhase === "idle" && (
                    <motion.button
                      key="del-idle"
                      type="button"
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => setDeletePhase("confirm")}
                      className={cn(
                        "inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-500 shadow-[0_1px_2px_rgba(15,23,42,0.04)]",
                        "transition-all hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600"
                      )}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Delete delivery
                    </motion.button>
                  )}

                  {deletePhase === "confirm" && (
                    <motion.div
                      key="del-confirm"
                      initial={{ opacity: 0, x: 8 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: 8 }}
                      className="flex items-center gap-1.5 rounded-lg border border-rose-200 bg-white px-2 py-1 shadow-[0_4px_14px_rgba(244,63,94,0.12)]"
                    >
                      <span className="px-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                        Delete this delivery?
                      </span>
                      <button
                        type="button"
                        onClick={handleDelete}
                        className="rounded-md bg-rose-500 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-white shadow-sm transition-colors hover:bg-rose-600"
                      >
                        Yes, delete
                      </button>
                      <button
                        type="button"
                        onClick={() => setDeletePhase("idle")}
                        className="rounded-md px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500 transition-colors hover:bg-slate-100"
                      >
                        Cancel
                      </button>
                    </motion.div>
                  )}

                  {deletePhase === "loading" && (
                    <motion.div
                      key="del-loading"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-600"
                    >
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Deleting…
                    </motion.div>
                  )}

                  {deletePhase === "error" && (
                    <motion.div
                      key="del-error"
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700"
                      title={deleteError}
                    >
                      <AlertCircle className="h-3.5 w-3.5" />
                      {deleteError || "Delete failed"}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </GlassCard>
  );
}

interface DetailTileProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint?: string;
  tone?: "ok" | "warn" | "late";
}

function DetailTile({ icon, label, value, hint, tone }: DetailTileProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-[0_1px_2px_rgba(15,23,42,0.03)]">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
        <span className="text-slate-400">{icon}</span>
        {label}
      </div>
      <p className="mt-2 truncate font-mono text-sm font-semibold text-slate-900">
        {value}
      </p>
      {hint ? (
        <p
          className={cn(
            "mt-1 text-[11px]",
            tone === "ok" && "text-emerald-600",
            tone === "warn" && "text-amber-600",
            tone === "late" && "text-rose-600",
            !tone && "text-slate-400"
          )}
        >
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export default function Deliveries() {
  const [filter, setFilter] = useState<StageKey | "all">("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const queryClient = useQueryClient();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: queryKeys.deliveries.list({}),
    queryFn: () => api.get<DeliveryListResponse>("/deliveries?per_page=100"),
    refetchInterval: 30_000,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete<void>(`/deliveries/${id}`),
    onSuccess: (_data, id) => {
      // Collapse the deleted row if it was expanded.
      setExpandedId((prev) => (prev === id ? null : prev));
      queryClient.invalidateQueries({ queryKey: queryKeys.deliveries.list({}) });
    },
  });

  const handleDeleteDelivery = async (id: string) => {
    await deleteMutation.mutateAsync(id);
  };

  const deliveries = data?.deliveries ?? [];

  const filtered = useMemo(() => {
    const byStage =
      filter === "all"
        ? deliveries
        : deliveries.filter((d) => d.current_stage === filter);
    const q = query.trim().toLowerCase();
    if (!q) return byStage;
    return byStage.filter((d) => {
      const orderId = d.order_id?.toLowerCase() ?? "";
      const deliveryId = d.id?.toLowerCase() ?? "";
      const stage = (d.current_stage ?? "").toLowerCase();
      return (
        orderId.includes(q) ||
        deliveryId.includes(q) ||
        stage.includes(q)
      );
    });
  }, [filter, deliveries, query]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: deliveries.length };
    for (const d of deliveries) {
      c[d.current_stage] = (c[d.current_stage] ?? 0) + 1;
    }
    return c;
  }, [deliveries]);

  const inTransitTotal =
    (counts.shipped ?? 0) + (counts.in_transit ?? 0);
  const pendingTotal =
    (counts.ordered ?? 0) + (counts.confirmed ?? 0);

  return (
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
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Deliveries
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Track supplier shipments in real time — status updates automatically based on the expected delivery date.
          </p>
        </div>
      </motion.div>

      <motion.div
        variants={fadeInUp}
        className="grid grid-cols-2 gap-3 sm:grid-cols-4"
      >
        <SummaryTile
          label="Total"
          value={counts.all ?? 0}
          icon={<Truck className="h-5 w-5 text-white" />}
          gradient="from-violet-500 to-purple-600"
          accent="text-violet-700"
        />
        <SummaryTile
          label="In Transit"
          value={inTransitTotal}
          icon={<MapPin className="h-5 w-5 text-white" />}
          gradient="from-sky-500 to-blue-600"
          accent="text-sky-700"
        />
        <SummaryTile
          label="Pending"
          value={pendingTotal}
          icon={<Clock className="h-5 w-5 text-white" />}
          gradient="from-amber-500 to-orange-500"
          accent="text-amber-700"
        />
        <SummaryTile
          label="Delivered"
          value={counts.delivered ?? 0}
          icon={<PackageCheck className="h-5 w-5 text-white" />}
          gradient="from-emerald-500 to-teal-600"
          accent="text-emerald-700"
        />
      </motion.div>

      <motion.div variants={fadeInUp} className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1 sm:max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by order, delivery ID, or stage…"
            className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-9 text-sm text-slate-900 placeholder:text-slate-400 shadow-[0_1px_2px_rgba(15,23,42,0.04)] outline-none transition-all focus:border-violet-300 focus:shadow-[0_4px_14px_rgba(124,58,237,0.08)] focus:ring-4 focus:ring-violet-100"
          />
          {query ? (
            <button
              type="button"
              onClick={() => setQuery("")}
              aria-label="Clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {[{ key: "all" as const, label: "All" }, ...stages.map((s) => ({ key: s.key, label: s.label }))].map((s) => (
            <button
              key={s.key}
              onClick={() => setFilter(s.key as StageKey | "all")}
              className={cn(
                "rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-all",
                filter === s.key
                  ? "border-violet-300 bg-violet-50 text-violet-700 shadow-sm"
                  : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50"
              )}
            >
              {s.label}
              {counts[s.key] ? (
                <span
                  className={cn(
                    "ml-1.5 rounded-full px-1.5 py-0.5 text-[10px]",
                    filter === s.key
                      ? "bg-violet-100 text-violet-700"
                      : "bg-slate-100 text-slate-500"
                  )}
                >
                  {counts[s.key]}
                </span>
              ) : null}
            </button>
          ))}
        </div>
      </motion.div>

      <motion.div variants={fadeInUp} className="space-y-3">
        {isLoading ? (
          <GlassCard className="p-12">
            <div className="flex items-center justify-center gap-2 text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin text-violet-500" />
              <span className="text-sm">Loading deliveries…</span>
            </div>
          </GlassCard>
        ) : isError ? (
          <GlassCard className="p-8 text-center text-sm text-rose-600">
            Failed to load deliveries: {(error as Error)?.message ?? "unknown"}
          </GlassCard>
        ) : filtered.length === 0 ? (
          <GlassCard className="p-12">
            <div className="flex flex-col items-center justify-center text-slate-400">
              <Filter className="mb-3 h-8 w-8" />
              <p className="text-sm font-medium text-slate-500">
                {query.trim()
                  ? `No deliveries match “${query.trim()}”`
                  : "No deliveries match this filter"}
              </p>
              <p className="mt-1 text-xs">
                {query.trim()
                  ? "Try a different search term or clear the search."
                  : "Switch filter or place a new order to see it here."}
              </p>
            </div>
          </GlassCard>
        ) : (
          filtered.map((d, idx) => (
            <motion.div
              key={d.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.04 }}
            >
              <DeliveryRow
                delivery={d}
                expanded={expandedId === d.id}
                onToggle={() =>
                  setExpandedId((prev) => (prev === d.id ? null : d.id))
                }
                onDelete={handleDeleteDelivery}
              />
            </motion.div>
          ))
        )}
      </motion.div>
    </motion.div>
  );
}

interface SummaryTileProps {
  label: string;
  value: number;
  icon: React.ReactNode;
  gradient: string;
  accent: string;
}

function SummaryTile({ label, value, icon, gradient, accent }: SummaryTileProps) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_1px_3px_rgba(15,23,42,0.04)]">
      <div
        className={cn(
          "flex h-11 w-11 items-center justify-center rounded-xl shadow-md",
          `bg-gradient-to-br ${gradient}`
        )}
      >
        {icon}
      </div>
      <div>
        <p className={cn("text-xl font-bold tabular-nums", accent)}>{value}</p>
        <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
          {label}
        </p>
      </div>
    </div>
  );
}
