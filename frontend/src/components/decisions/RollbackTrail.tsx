import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { History, ChevronDown, Undo2, Mail, Truck, Package } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { cn, formatDate } from "@/lib/utils";
import { api } from "@/services/api";

interface RollbackAction {
  id: string;
  action_type: string;
  entity_type: string;
  entity_id: string;
  before_state: Record<string, unknown>;
  after_state: Record<string, unknown>;
  rolled_back_at: string | null;
  created_at: string;
}

interface RollbackTrailResponse {
  decision_id: string;
  actions: RollbackAction[];
}

interface RollbackTrailProps {
  decisionId: string;
}

const actionIcons: Record<string, typeof Mail> = {
  send_cancellation_email: Mail,
  create_order: Mail,
  cancel_delivery: Truck,
  restore_inventory: Package,
  evaluate_forecast: Package,
};

const actionLabels: Record<string, string> = {
  send_cancellation_email: "Cancellation email sent",
  create_order: "Order reversed",
  cancel_delivery: "Delivery cancelled",
  restore_inventory: "Inventory restored",
  evaluate_forecast: "Decision reversed",
};

export function RollbackTrail({ decisionId }: RollbackTrailProps) {
  const [expanded, setExpanded] = useState(false);

  const { data } = useQuery({
    queryKey: ["rollback-trail", decisionId],
    queryFn: () =>
      api.get<RollbackTrailResponse>(
        `/decisions/${decisionId}/rollback-trail`
      ),
    enabled: expanded,
  });

  const actions = data?.actions ?? [];

  return (
    <div className="mt-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className={cn(
          "flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-medium w-full",
          "border border-white/[0.04] bg-white/[0.02] text-white/40",
          "hover:text-white/60 hover:bg-white/[0.03] transition-colors"
        )}
      >
        <History className="h-3.5 w-3.5" />
        <span>Rollback Audit Trail</span>
        <motion.span
          className="ml-auto"
          animate={{ rotate: expanded ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronDown className="h-3.5 w-3.5" />
        </motion.span>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="mt-2 space-y-1 pl-2">
              {actions.length === 0 ? (
                <p className="py-3 text-center text-xs text-white/20">
                  No rollback actions recorded
                </p>
              ) : (
                actions.map((action, idx) => {
                  const Icon =
                    actionIcons[action.action_type] ?? Undo2;
                  const label =
                    actionLabels[action.action_type] ??
                    action.action_type.replace(/_/g, " ");

                  return (
                    <motion.div
                      key={action.id}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.05 }}
                      className="flex items-start gap-3 rounded-lg border border-white/[0.03] bg-white/[0.015] p-3"
                    >
                      {/* Timeline dot */}
                      <div className="relative flex flex-col items-center">
                        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-500/15">
                          <Icon className="h-3 w-3 text-slate-400" />
                        </div>
                        {idx < actions.length - 1 && (
                          <div className="mt-1 h-4 w-px bg-white/[0.06]" />
                        )}
                      </div>

                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-medium text-white/60 capitalize">
                          {label}
                        </p>
                        <p className="mt-0.5 text-[10px] text-white/25">
                          {action.entity_type} ·{" "}
                          {action.rolled_back_at
                            ? formatDate(action.rolled_back_at)
                            : formatDate(action.created_at)}
                        </p>

                        {/* Show restored values if present */}
                        {action.before_state &&
                          Object.keys(action.before_state).length > 0 && (
                            <div className="mt-1.5 flex flex-wrap gap-2">
                              {Object.entries(action.before_state)
                                .slice(0, 3)
                                .map(([key, val]) => (
                                  <span
                                    key={key}
                                    className="rounded bg-white/[0.04] px-1.5 py-0.5 text-[9px] text-white/30"
                                  >
                                    {key}: {String(val)}
                                  </span>
                                ))}
                            </div>
                          )}
                      </div>
                    </motion.div>
                  );
                })
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
