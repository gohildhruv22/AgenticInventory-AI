import { motion } from "framer-motion";
import { AgentNode, type AgentStatus } from "@/components/agents/AgentNode";
import { ReasoningTooltip } from "@/components/agents/ReasoningTooltip";
import { cn } from "@/lib/utils";

export interface PipelineStage {
  agent: string;
  status: AgentStatus;
  summary?: string | null;
  duration_ms?: number;
  started_at?: string;
}

interface ReasoningStep {
  step: string;
  message: string;
  progress: number;
  timestamp: string;
}

interface AgentFlowChartProps {
  stages: PipelineStage[];
  currentAgent: string | null;
  reasoningSteps: Record<string, ReasoningStep[]>;
  className?: string;
}

const AGENT_LABELS: Record<string, string> = {
  inventory_monitor: "Inventory Monitor",
  demand_forecast: "Demand Forecast",
  decision_manager: "Decision Manager",
  supplier_email: "Supplier Email",
  delivery_tracker: "Delivery Tracker",
  undo_rollback: "Undo & Rollback",
  reporting_kpi: "Reporting & KPI",
};

export function AgentFlowChart({
  stages,
  currentAgent,
  reasoningSteps,
  className,
}: AgentFlowChartProps) {
  return (
    <div className={cn("w-full overflow-x-auto", className)}>
      <div className="flex items-center justify-center gap-0 min-w-[700px] py-6 px-4">
        {stages.map((stage, idx) => {
          const isActive = stage.agent === currentAgent;
          const steps = reasoningSteps[stage.agent] ?? [];

          return (
            <div key={stage.agent} className="flex items-center">
              {/* Agent Node with Tooltip */}
              <div className="relative flex flex-col items-center">
                <AgentNode
                  agentType={stage.agent}
                  label={AGENT_LABELS[stage.agent] ?? stage.agent}
                  status={stage.status as AgentStatus}
                  summary={stage.summary}
                  isActive={isActive}
                />

                {/* Reasoning tooltip below */}
                {steps.length > 0 && (
                  <div className="mt-2">
                    <ReasoningTooltip
                      agentType={stage.agent}
                      agentLabel={AGENT_LABELS[stage.agent] ?? stage.agent}
                      steps={steps}
                    />
                  </div>
                )}

                {/* Duration badge */}
                {stage.duration_ms != null && stage.status === "completed" && (
                  <span className="mt-1 text-[9px] text-white/20">
                    {(stage.duration_ms / 1000).toFixed(1)}s
                  </span>
                )}
              </div>

              {/* Connection Line */}
              {idx < stages.length - 1 && (
                <ConnectionLine
                  fromStatus={stage.status as AgentStatus}
                  toStatus={stages[idx + 1].status as AgentStatus}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Connection Line ──────────────────────────────────────── */

function ConnectionLine({
  fromStatus,
  toStatus,
}: {
  fromStatus: AgentStatus;
  toStatus: AgentStatus;
}) {
  const isActive =
    fromStatus === "completed" && toStatus === "processing";
  const isCompleted =
    fromStatus === "completed" && toStatus === "completed";
  const isPending = fromStatus !== "completed";

  return (
    <div className="relative mx-1 flex h-[2px] w-12 items-center">
      {/* Base line */}
      <div
        className={cn(
          "absolute inset-0 rounded-full",
          isPending && "bg-white/[0.06]",
          isCompleted && "bg-emerald-500/30",
          isActive && "bg-purple-500/20",
        )}
      />

      {/* Animated flow for active connection */}
      {isActive && (
        <motion.div
          className="absolute left-0 top-0 h-full w-4 rounded-full bg-gradient-to-r from-transparent via-purple-400 to-transparent"
          animate={{ x: [0, 32, 0] }}
          transition={{ repeat: Infinity, duration: 1.2, ease: "easeInOut" }}
        />
      )}

      {/* Completed fill animation */}
      {isCompleted && (
        <motion.div
          className="absolute left-0 top-0 h-full rounded-full bg-emerald-400/50"
          initial={{ width: "0%" }}
          animate={{ width: "100%" }}
          transition={{ duration: 0.4, ease: "easeOut" }}
        />
      )}

      {/* Arrow head */}
      <div className="absolute -right-1 top-1/2 -translate-y-1/2">
        <svg width="6" height="8" viewBox="0 0 6 8" fill="none">
          <path
            d="M0 0L6 4L0 8V0Z"
            fill={
              isCompleted
                ? "rgba(52,211,153,0.4)"
                : isActive
                  ? "rgba(139,92,246,0.4)"
                  : "rgba(255,255,255,0.08)"
            }
          />
        </svg>
      </div>
    </div>
  );
}
