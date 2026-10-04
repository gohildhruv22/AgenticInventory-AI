import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import {
  Brain,
  Search,
  Filter,
  RefreshCw,
  ChevronDown,
  Loader2,
  Inbox,
} from "lucide-react";
import { fadeInUp, staggerChildren, pageTransition } from "@/lib/animations";
import { cn } from "@/lib/utils";
import { GlassCard } from "@/components/ui/GlassCard";
import { DecisionCard } from "@/components/decisions/DecisionCard";
import { useAgentDecisions } from "@/hooks/useAgentDecisions";
import { AnimatedCounter } from "@/components/ui/AnimatedCounter";
import { wsClient } from "@/services/socket";
import { queryKeys } from "@/services/queryKeys";

const AGENT_TYPES = [
  { value: "", label: "All Agents" },
  { value: "decision_manager", label: "Decision Manager" },
  { value: "forecast", label: "Forecast" },
  { value: "monitoring", label: "Monitoring" },
  { value: "supplier_email", label: "Email Agent" },
];

const STATUSES = [
  { value: "", label: "All Statuses" },
  { value: "approved", label: "Approved" },
  { value: "executed", label: "Executed" },
  { value: "flagged", label: "Flagged" },
  { value: "rejected", label: "Rejected" },
  { value: "rolled_back", label: "Rolled Back" },
];

export default function Decisions() {
  const [agentType, setAgentType] = useState("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const queryClient = useQueryClient();

  const {
    decisions,
    total,
    isLoading,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    approve,
    remove,
    isNewDecision,
  } = useAgentDecisions({
    agent_type: agentType || undefined,
    status: status || undefined,
    search: search || undefined,
  });

  // Infinite scroll observer
  const sentinelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!sentinelRef.current || !hasNextPage) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      { rootMargin: "200px" }
    );
    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // Subscribe to rollback events to invalidate decision list
  useEffect(() => {
    const unsub = wsClient.subscribe((event) => {
      if (event === "decision:updated" || event === "rollback:progress") {
        queryClient.invalidateQueries({ queryKey: queryKeys.decisions.all });
      }
    });
    return unsub;
  }, [queryClient]);

  const clearFilters = useCallback(() => {
    setAgentType("");
    setStatus("");
    setSearch("");
  }, []);

  const handleUndoComplete = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: queryKeys.decisions.all });
  }, [queryClient]);

  const hasActiveFilters = agentType || status || search;

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
          <h1 className="text-2xl font-bold tracking-tight text-white">Agent Decisions</h1>
          <p className="mt-1 text-sm text-white/40">
            AI reasoning traces and decision history
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 py-2">
            <Brain className="h-4 w-4 text-purple-400" />
            <AnimatedCounter value={total} className="text-sm font-semibold text-white" />
            <span className="text-xs text-white/40">decisions</span>
          </div>
        </div>
      </motion.div>

      {/* ─── Search & Filters ─────────────────────────────── */}
      <motion.div variants={fadeInUp} className="space-y-3">
        <div className="flex gap-3">
          {/* Search bar */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/30" />
            <input
              type="text"
              placeholder="Search decisions by agent, item, SKU, reasoning…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className={cn(
                "w-full rounded-xl border border-white/[0.06] bg-white/[0.03] py-2.5 pl-10 pr-4",
                "text-sm text-white placeholder:text-white/25",
                "focus:border-purple-500/40 focus:outline-none focus:ring-1 focus:ring-purple-500/20",
                "backdrop-blur-xl transition-colors"
              )}
            />
          </div>

          {/* Filter toggle */}
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => setShowFilters(!showFilters)}
            className={cn(
              "flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition-colors",
              showFilters || hasActiveFilters
                ? "border-purple-500/30 bg-purple-500/10 text-purple-300"
                : "border-white/[0.06] bg-white/[0.03] text-white/60 hover:text-white/80"
            )}
          >
            <Filter className="h-4 w-4" />
            Filters
            {hasActiveFilters && (
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-purple-500 text-[10px] font-bold text-white">
                {[agentType, status].filter(Boolean).length}
              </span>
            )}
          </motion.button>
        </div>

        {/* Filter dropdowns */}
        <AnimatePresence>
          {showFilters && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <GlassCard className="flex items-center gap-4 p-4">
                <FilterSelect
                  label="Agent Type"
                  value={agentType}
                  options={AGENT_TYPES}
                  onChange={setAgentType}
                />
                <FilterSelect
                  label="Status"
                  value={status}
                  options={STATUSES}
                  onChange={setStatus}
                />
                {hasActiveFilters && (
                  <button
                    onClick={clearFilters}
                    className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium text-white/40 hover:text-white/70 transition-colors"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    Clear
                  </button>
                )}
              </GlassCard>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* ─── Decision Feed ────────────────────────────────── */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-purple-400" />
        </div>
      ) : decisions.length === 0 ? (
        <GlassCard className="p-12">
          <div className="flex flex-col items-center justify-center text-white/30">
            <Inbox className="mb-4 h-14 w-14" />
            <p className="text-lg font-medium">No decisions found</p>
            <p className="mt-1 text-sm">
              {hasActiveFilters
                ? "Try adjusting your filters or search query."
                : "Decisions will appear here as agents process inventory."}
            </p>
          </div>
        </GlassCard>
      ) : (
        <motion.div
          variants={staggerChildren}
          initial="initial"
          animate="animate"
          className="space-y-4"
        >
          <AnimatePresence mode="popLayout">
            {decisions.map((d) => (
              <DecisionCard
                key={d.id}
                decision={d}
                isNew={isNewDecision(d.id)}
                onApprove={d.status === "flagged" ? approve : undefined}
                onUndoComplete={handleUndoComplete}
                onDelete={remove}
              />
            ))}
          </AnimatePresence>

          {/* Infinite scroll sentinel */}
          <div ref={sentinelRef} className="h-1" />

          {isFetchingNextPage && (
            <div className="flex justify-center py-4">
              <Loader2 className="h-6 w-6 animate-spin text-purple-400/60" />
            </div>
          )}

          {!hasNextPage && decisions.length > 0 && (
            <p className="py-4 text-center text-xs text-white/20">
              All {total} decisions loaded
            </p>
          )}
        </motion.div>
      )}
    </motion.div>
  );
}

/* ─── Filter Select ──────────────────────────────────────── */

interface FilterSelectProps {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}

function FilterSelect({ label, value, options, onChange }: FilterSelectProps) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-white/30">
        {label}
      </span>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={cn(
            "appearance-none rounded-lg border border-white/[0.06] bg-white/[0.03] py-2 pl-3 pr-8",
            "text-sm text-white/70",
            "focus:border-purple-500/40 focus:outline-none focus:ring-1 focus:ring-purple-500/20",
            "cursor-pointer transition-colors"
          )}
        >
          {options.map((o) => (
            <option key={o.value} value={o.value} className="bg-[#1a1a28] text-white">
              {o.label}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-white/30" />
      </div>
    </div>
  );
}
