import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Undo2, AlertTriangle, Check, X, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/services/api";
import { wsClient } from "@/services/socket";

interface RollbackProgress {
  decision_id: string;
  status: "in_progress" | "completed";
  actions_total: number;
  actions_completed: number;
  current_action?: string;
  summary?: string;
}

interface RollbackSummaryItem {
  action: string;
  entity: string;
  entity_id: string;
  restored_to?: number;
}

interface UndoResult {
  message: string;
  decision_id: string;
  actions_reversed: number;
  rollback_summary: RollbackSummaryItem[];
}

interface UndoButtonProps {
  decisionId: string;
  status: string;
  onUndoComplete?: () => void;
  className?: string;
}

export function UndoButton({ decisionId, status, onUndoComplete, className }: UndoButtonProps) {
  const [phase, setPhase] = useState<"idle" | "confirm" | "progress" | "success" | "error">("idle");
  const [progress, setProgress] = useState<RollbackProgress | null>(null);
  const [result, setResult] = useState<UndoResult | null>(null);
  const [error, setError] = useState("");

  const canUndo = status === "executed" || status === "approved";

  // Listen for rollback progress events
  useEffect(() => {
    const unsub = wsClient.subscribe((event, data) => {
      if (event === "rollback:progress") {
        const payload = data as RollbackProgress;
        if (payload.decision_id === decisionId) {
          setProgress(payload);
          if (payload.status === "completed") {
            setPhase("success");
            setTimeout(() => {
              onUndoComplete?.();
            }, 1500);
          }
        }
      }
    });
    return unsub;
  }, [decisionId, onUndoComplete]);

  const handleUndo = useCallback(async () => {
    setPhase("progress");
    setError("");
    setProgress(null);

    try {
      const res = await api.post<UndoResult>(`/decisions/${decisionId}/undo`);
      setResult(res);
      setPhase("success");
      setTimeout(() => {
        onUndoComplete?.();
      }, 1500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Undo failed";
      setError(msg);
      setPhase("error");
    }
  }, [decisionId, onUndoComplete]);

  if (!canUndo) return null;

  const progressPercent = progress
    ? Math.round((progress.actions_completed / Math.max(progress.actions_total, 1)) * 100)
    : 0;

  return (
    <div className={cn("relative", className)}>
      <AnimatePresence mode="wait">
        {/* ─── Idle State ──────────────────────── */}
        {phase === "idle" && (
          <motion.button
            key="idle"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => setPhase("confirm")}
            className={cn(
              "flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium",
              "border border-red-500/20 bg-red-500/10 text-red-400",
              "hover:bg-red-500/15 hover:border-red-500/30",
              "transition-colors"
            )}
          >
            <Undo2 className="h-4 w-4" />
            Undo
          </motion.button>
        )}

        {/* ─── Confirmation Dialog ─────────────── */}
        {phase === "confirm" && (
          <motion.div
            key="confirm"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className={cn(
              "flex items-center gap-3 rounded-xl border border-amber-500/20",
              "bg-amber-500/10 px-4 py-2.5 backdrop-blur-xl"
            )}
          >
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
            <span className="text-xs text-amber-300">Reverse this decision?</span>
            <div className="flex items-center gap-1.5">
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={handleUndo}
                className="flex items-center gap-1 rounded-lg bg-red-500/20 px-3 py-1.5 text-xs font-semibold text-red-400 hover:bg-red-500/30 transition-colors"
              >
                <Check className="h-3 w-3" />
                Yes
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => setPhase("idle")}
                className="flex items-center gap-1 rounded-lg bg-white/[0.06] px-3 py-1.5 text-xs font-medium text-white/50 hover:text-white/70 transition-colors"
              >
                <X className="h-3 w-3" />
                No
              </motion.button>
            </div>
          </motion.div>
        )}

        {/* ─── Progress State ─────────────────── */}
        {phase === "progress" && (
          <motion.div
            key="progress"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className={cn(
              "rounded-xl border border-purple-500/20",
              "bg-purple-500/10 px-4 py-3 backdrop-blur-xl"
            )}
          >
            <div className="flex items-center gap-2 mb-2">
              <Loader2 className="h-4 w-4 animate-spin text-purple-400" />
              <span className="text-xs font-medium text-purple-300">
                Rolling back…
              </span>
              <span className="ml-auto text-[10px] font-bold text-purple-400">
                {progressPercent}%
              </span>
            </div>

            {/* Progress bar */}
            <div className="h-1.5 w-full rounded-full bg-white/[0.06] overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-purple-500 to-pink-500"
                initial={{ width: "0%" }}
                animate={{ width: `${progressPercent}%` }}
                transition={{ duration: 0.3, ease: "easeOut" }}
              />
            </div>

            {progress?.current_action && (
              <p className="mt-2 text-[10px] text-white/30 truncate">
                {progress.current_action}
              </p>
            )}
          </motion.div>
        )}

        {/* ─── Success State ──────────────────── */}
        {phase === "success" && (
          <motion.div
            key="success"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className={cn(
              "flex items-center gap-2 rounded-xl border border-emerald-500/20",
              "bg-emerald-500/10 px-4 py-2.5"
            )}
          >
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 400, damping: 15 }}
            >
              <Check className="h-4 w-4 text-emerald-400" />
            </motion.div>
            <span className="text-xs font-medium text-emerald-300">
              Rolled back
              {result ? ` — ${result.actions_reversed} action(s) reversed` : ""}
            </span>
          </motion.div>
        )}

        {/* ─── Error State ────────────────────── */}
        {phase === "error" && (
          <motion.div
            key="error"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className={cn(
              "flex items-center gap-2 rounded-xl border border-red-500/20",
              "bg-red-500/10 px-4 py-2.5"
            )}
          >
            <X className="h-4 w-4 text-red-400" />
            <span className="text-xs text-red-300 truncate">{error}</span>
            <button
              onClick={() => setPhase("idle")}
              className="ml-auto text-[10px] text-white/40 hover:text-white/60 transition-colors"
            >
              Dismiss
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
