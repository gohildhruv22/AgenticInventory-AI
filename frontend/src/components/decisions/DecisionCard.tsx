import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Brain,
  ShieldCheck,
  Package,
  Clock,
  TrendingUp,
  ChevronRight,
  Check,
  Loader2,
  X,
  Trash2,
} from "lucide-react";
import { cn, formatCurrency, formatDate } from "@/lib/utils";
import { fadeInUp, defaultTransition } from "@/lib/animations";
import { StatusIndicator } from "@/components/ui/StatusIndicator";
import { ReasoningTrace } from "@/components/decisions/ReasoningTrace";
import { DecisionSteps } from "@/components/decisions/DecisionSteps";
import { UndoButton } from "@/components/decisions/UndoButton";
import { RollbackTrail } from "@/components/decisions/RollbackTrail";
import type { AgentDecision } from "@/types/agent";

interface DecisionCardProps {
  decision: AgentDecision;
  isNew?: boolean;
  onApprove?: (id: string) => void;
  onUndoComplete?: () => void;
  onDelete?: (id: string) => Promise<void> | void;
  className?: string;
}

/* ─── Agent type metadata ─────────────────────────────────── */
const agentMeta: Record<string, { icon: typeof Brain; gradient: string; label: string }> = {
  decision_manager: { icon: Brain, gradient: "from-purple-500 to-pink-500", label: "Decision Manager" },
  forecast: { icon: TrendingUp, gradient: "from-cyan-500 to-blue-500", label: "Forecast Agent" },
  monitoring: { icon: Package, gradient: "from-emerald-500 to-teal-500", label: "Monitoring Agent" },
  supplier_email: { icon: ShieldCheck, gradient: "from-amber-500 to-orange-500", label: "Email Agent" },
};

const statusConfig: Record<string, { color: string; bg: string; border: string; label: string }> = {
  approved: { color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20", label: "Approved" },
  executed: { color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20", label: "Executed" },
  flagged: { color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20", label: "Flagged" },
  pending_review: { color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20", label: "Pending Review" },
  rejected: { color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/20", label: "Rejected" },
  rolled_back: { color: "text-slate-400", bg: "bg-slate-500/10", border: "border-slate-500/20", label: "Rolled Back" },
};

export function DecisionCard({ decision, isNew, onApprove, onUndoComplete, onDelete, className }: DecisionCardProps) {
  const [approvePhase, setApprovePhase] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [approveError, setApproveError] = useState("");
  const [deletePhase, setDeletePhase] = useState<"idle" | "confirm" | "loading" | "error">("idle");
  const [deleteError, setDeleteError] = useState("");
  const agent = agentMeta[decision.agent_type] ?? agentMeta.decision_manager;
  const Icon = agent.icon;
  const stCfg = statusConfig[decision.status] ?? statusConfig.executed;
  const confidence = decision.confidence_level ?? 0;
  const trace = decision.reasoning_trace;
  const itemName = trace.item_context?.name;
  const estimatedCost = trace.estimated_cost;

  const handleApprove = async () => {
    if (!onApprove || approvePhase === "loading") return;
    setApprovePhase("loading");
    setApproveError("");
    try {
      await onApprove(decision.id);
      setApprovePhase("success");
    } catch (err) {
      setApproveError(err instanceof Error ? err.message : "Approval failed");
      setApprovePhase("error");
      setTimeout(() => setApprovePhase("idle"), 3500);
    }
  };

  const handleDelete = async () => {
    if (!onDelete || deletePhase === "loading") return;
    setDeletePhase("loading");
    setDeleteError("");
    try {
      await onDelete(decision.id);
      // Card will unmount on success — no need to reset state.
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Delete failed");
      setDeletePhase("error");
      setTimeout(() => setDeletePhase("idle"), 3500);
    }
  };

  return (
    <motion.div
      layout
      variants={fadeInUp}
      initial="initial"
      animate="animate"
      exit="exit"
      transition={defaultTransition}
      className={cn(
        "group relative overflow-hidden rounded-2xl border backdrop-blur-xl",
        "bg-white/[0.03] shadow-[0_8px_32px_rgba(0,0,0,0.3)]",
        "hover:bg-white/[0.05] hover:border-white/[0.1]",
        "transition-all duration-300",
        isNew
          ? "border-purple-500/40 shadow-[0_0_30px_rgba(139,92,246,0.15)]"
          : "border-white/[0.06]",
        className
      )}
    >
      {/* New decision glow pulse */}
      {isNew && (
        <motion.div
          className="absolute inset-0 rounded-2xl border-2 border-purple-500/30"
          animate={{
            opacity: [0.6, 0, 0.6],
            scale: [1, 1.01, 1],
          }}
          transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
        />
      )}

      {/* Top gradient accent */}
      <div
        className={cn(
          "absolute left-0 top-0 h-[2px] w-full bg-gradient-to-r",
          agent.gradient
        )}
      />

      <div className="relative p-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div
              className={cn(
                "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br shadow-lg",
                agent.gradient
              )}
            >
              <Icon className="h-5 w-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-white/90">{agent.label}</h3>
                <span
                  className={cn(
                    "rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                    stCfg.color, stCfg.bg, stCfg.border
                  )}
                >
                  {stCfg.label}
                </span>
              </div>
              <p className="mt-0.5 text-xs text-white/40">
                {decision.action_type.replace(/_/g, " ")}
                {itemName && (
                  <>
                    {" "}
                    <ChevronRight className="inline h-3 w-3 text-white/20" />{" "}
                    <span className="text-white/50">{itemName}</span>
                  </>
                )}
              </p>
            </div>
          </div>

          {/* Confidence gauge + delete affordance */}
          <div className="flex items-center gap-2">
            <ConfidenceRing value={confidence} />
            {onDelete && (
              <AnimatePresence mode="wait" initial={false}>
                {deletePhase === "idle" && (
                  <motion.button
                    key="del-idle"
                    type="button"
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.9 }}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => setDeletePhase("confirm")}
                    aria-label="Delete decision"
                    title="Delete decision"
                    className={cn(
                      "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-400 shadow-[0_1px_2px_rgba(15,23,42,0.04)]",
                      "transition-all hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600"
                    )}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </motion.button>
                )}

                {deletePhase === "confirm" && (
                  <motion.div
                    key="del-confirm"
                    initial={{ opacity: 0, x: 8 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 8 }}
                    className="flex items-center gap-1 rounded-lg border border-rose-200 bg-white px-1.5 py-1 shadow-[0_4px_14px_rgba(244,63,94,0.12)]"
                  >
                    <span className="hidden px-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500 sm:inline">
                      Delete?
                    </span>
                    <button
                      type="button"
                      onClick={handleDelete}
                      className="rounded-md bg-rose-500 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white shadow-sm transition-colors hover:bg-rose-600"
                    >
                      Yes
                    </button>
                    <button
                      type="button"
                      onClick={() => setDeletePhase("idle")}
                      className="rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500 transition-colors hover:bg-slate-100"
                    >
                      No
                    </button>
                  </motion.div>
                )}

                {deletePhase === "loading" && (
                  <motion.div
                    key="del-loading"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-rose-200 bg-rose-50 text-rose-500"
                  >
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  </motion.div>
                )}

                {deletePhase === "error" && (
                  <motion.div
                    key="del-error"
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex items-center gap-1.5 rounded-lg border border-rose-200 bg-rose-50 px-2 py-1 text-[10px] font-semibold text-rose-700"
                    title={deleteError}
                  >
                    <X className="h-3 w-3" />
                    <span>Failed</span>
                  </motion.div>
                )}
              </AnimatePresence>
            )}
          </div>
        </div>

        {/* Summary row */}
        <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-white/50">
          <span className="flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5" />
            {formatDate(decision.created_at)}
          </span>
          {estimatedCost != null && estimatedCost > 0 && (
            <span className="flex items-center gap-1.5 text-white/60">
              <Package className="h-3.5 w-3.5" />
              {formatCurrency(estimatedCost)}
            </span>
          )}
          {trace.decision && (
            <span className="flex items-center gap-1.5">
              <StatusIndicator status={decision.status} />
              <span className="capitalize">{trace.decision}</span>
            </span>
          )}
        </div>

        {/* Quick reasoning summary */}
        {trace.reasoning && (
          <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-white/50">
            {trace.reasoning}
          </p>
        )}

        {/* Step-by-step thought process (always visible) */}
        <div className="mt-4">
          <DecisionSteps decision={decision} />
        </div>

        {/* Expandable reasoning trace */}
        <div className="mt-3">
          <ReasoningTrace
            trace={trace}
            alternatives={decision.alternatives_considered}
          />
        </div>

        {/* Approve action for flagged decisions */}
        {decision.status === "flagged" && onApprove && (
          <div className="mt-4 flex justify-end">
            <AnimatePresence mode="wait">
              {approvePhase === "idle" && (
                <motion.button
                  key="idle"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleApprove}
                  className={cn(
                    "flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium",
                    "bg-gradient-to-r from-emerald-500 to-teal-500 text-white",
                    "shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/30 transition-shadow"
                  )}
                >
                  <Check className="h-4 w-4" />
                  Approve
                </motion.button>
              )}

              {approvePhase === "loading" && (
                <motion.div
                  key="loading"
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  className="flex items-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-2 text-sm font-medium text-emerald-300"
                >
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Approving…
                </motion.div>
              )}

              {approvePhase === "success" && (
                <motion.div
                  key="success"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/15 px-4 py-2 text-sm font-semibold text-emerald-300"
                >
                  <motion.span
                    initial={{ scale: 0, rotate: -90 }}
                    animate={{ scale: 1, rotate: 0 }}
                    transition={{ type: "spring", stiffness: 400, damping: 14 }}
                  >
                    <Check className="h-4 w-4" />
                  </motion.span>
                  Approved & executed
                </motion.div>
              )}

              {approvePhase === "error" && (
                <motion.div
                  key="error"
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  className="flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-300"
                >
                  <X className="h-4 w-4" />
                  <span className="truncate max-w-[240px]">{approveError || "Approval failed"}</span>
                  <button
                    onClick={() => setApprovePhase("idle")}
                    className="ml-1 text-[10px] uppercase tracking-wider text-white/40 hover:text-white/70"
                  >
                    Retry
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* Undo action for executed/approved decisions */}
        {(decision.status === "executed" || decision.status === "approved") && (
          <div className="mt-4 flex justify-end">
            <UndoButton
              decisionId={decision.id}
              status={decision.status}
              onUndoComplete={onUndoComplete}
            />
          </div>
        )}

        {/* Rollback audit trail for rolled-back decisions */}
        {decision.status === "rolled_back" && (
          <RollbackTrail decisionId={decision.id} />
        )}
      </div>
    </motion.div>
  );
}

/* ─── Confidence Ring ──────────────────────────────────────── */

function ConfidenceRing({ value }: { value: number }) {
  const clamped = Math.min(100, Math.max(0, value));
  const circumference = 2 * Math.PI * 20;
  const offset = circumference - (clamped / 100) * circumference;
  const color =
    clamped >= 75 ? "text-emerald-400" : clamped >= 50 ? "text-amber-400" : "text-red-400";
  const strokeColor =
    clamped >= 75 ? "#4ade80" : clamped >= 50 ? "#fbbf24" : "#f87171";

  return (
    <div className="relative flex h-12 w-12 shrink-0 items-center justify-center">
      <svg className="h-12 w-12 -rotate-90" viewBox="0 0 48 48">
        <circle
          cx="24"
          cy="24"
          r="20"
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth="3"
        />
        <motion.circle
          cx="24"
          cy="24"
          r="20"
          fill="none"
          stroke={strokeColor}
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1, ease: "easeOut" }}
        />
      </svg>
      <span className={cn("absolute text-xs font-bold", color)}>
        {Math.round(clamped)}
      </span>
    </div>
  );
}
