import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  Play,
  Loader2,
  Clock,
  CheckCircle2,
  AlertCircle,
  Activity,
  Zap,
} from "lucide-react";
import { fadeInUp, pageTransition } from "@/lib/animations";
import { cn, formatDate } from "@/lib/utils";
import { GlassCard } from "@/components/ui/GlassCard";
import { AgentFlowChart, type PipelineStage } from "@/components/agents/AgentFlowChart";
import type { AgentStatus } from "@/components/agents/AgentNode";
import { api } from "@/services/api";
import { wsClient } from "@/services/socket";

const PIPELINE_AGENTS = [
  "inventory_monitor",
  "demand_forecast",
  "decision_manager",
  "supplier_email",
  "delivery_tracker",
];

const DEFAULT_STAGES: PipelineStage[] = PIPELINE_AGENTS.map((a) => ({
  agent: a,
  status: "idle" as AgentStatus,
  summary: null,
}));

interface ReasoningStep {
  step: string;
  message: string;
  progress: number;
  timestamp: string;
}

interface PipelineRun {
  pipeline_id: string;
  item_id?: string;
  item_name?: string;
  status: string;
  current_agent: string | null;
  stages: PipelineStage[];
  started_at: string;
  completed_at?: string;
}

interface ActivityEntry {
  id: string;
  agent: string;
  message: string;
  timestamp: string;
  type: "reasoning" | "status";
}

export default function Agents() {
  const queryClient = useQueryClient();
  const [stages, setStages] = useState<PipelineStage[]>(DEFAULT_STAGES);
  const [currentAgent, setCurrentAgent] = useState<string | null>(null);
  const [reasoningSteps, setReasoningSteps] = useState<Record<string, ReasoningStep[]>>({});
  const [activityFeed, setActivityFeed] = useState<ActivityEntry[]>([]);
  const [triggering, setTriggering] = useState(false);
  const [, setActivePipelineId] = useState<string | null>(null);

  // Load pipeline history
  const { data: historyData } = useQuery({
    queryKey: ["pipeline", "history"],
    queryFn: () => api.get<{ runs: PipelineRun[] }>("/pipeline/history"),
  });

  const history = historyData?.runs ?? [];

  // Subscribe to pipeline WebSocket events
  useEffect(() => {
    const unsub = wsClient.subscribe((event, data) => {
      const payload = data as Record<string, unknown>;

      if (event === "pipeline:progress") {
        const pStages = payload.stages as PipelineStage[];
        setStages(pStages);
        setCurrentAgent(payload.current_agent as string | null);
        setActivePipelineId(payload.pipeline_id as string);

        if (!payload.current_agent) {
          // Pipeline completed
          queryClient.invalidateQueries({ queryKey: ["pipeline", "history"] });
        }
      }

      if (event === "agent:status") {
        const agentType = payload.agent_type as string;
        const status = payload.status as string;
        const message = payload.message as string;

        setActivityFeed((prev) => [
          {
            id: `${Date.now()}-${agentType}-${Math.random().toString(36).slice(2, 8)}`,
            agent: agentType,
            message,
            timestamp: payload.timestamp as string,
            type: "status" as const,
          },
          ...prev,
        ].slice(0, 50));

        if (status === "completed" || status === "processing") {
          setCurrentAgent(
            status === "processing" ? agentType : null
          );
        }
      }

      if (event === "agent:reasoning") {
        const agentType = payload.agent_type as string;
        const step: ReasoningStep = {
          step: payload.step as string,
          message: payload.message as string,
          progress: payload.progress as number,
          timestamp: payload.timestamp as string,
        };

        setReasoningSteps((prev) => ({
          ...prev,
          [agentType]: [...(prev[agentType] ?? []), step],
        }));

        setActivityFeed((prev) => [
          {
            id: `${Date.now()}-${agentType}-r-${Math.random().toString(36).slice(2, 8)}`,
            agent: agentType,
            message: payload.message as string,
            timestamp: payload.timestamp as string,
            type: "reasoning" as const,
          },
          ...prev,
        ].slice(0, 50));
      }
    });

    return unsub;
  }, [queryClient]);

  const triggerPipeline = useCallback(async () => {
    setTriggering(true);
    setStages(DEFAULT_STAGES);
    setReasoningSteps({});
    setActivityFeed([]);
    setCurrentAgent(null);

    try {
      const res = await api.post<{ pipeline_id: string }>("/pipeline/trigger", {});
      setActivePipelineId(res.pipeline_id);
    } catch {
      // ignore
    } finally {
      setTriggering(false);
    }
  }, []);

  const completedCount = stages.filter((s) => s.status === "completed").length;
  const totalAgents = stages.length;
  const progressPercent = Math.round((completedCount / totalAgents) * 100);
  const isRunning = stages.some((s) => s.status === "processing");

  return (
    <motion.div
      variants={pageTransition}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-6"
    >
      {/* ─── Header ───────────────────────────────────────── */}
      <motion.div variants={fadeInUp} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Agent Pipeline</h1>
          <p className="mt-1 text-sm text-white/40">
            Live visualization of the AI agent orchestration pipeline — running autonomously in the background
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Autonomous mode indicator */}
          <div className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            <span className="text-xs font-medium text-emerald-300">Autonomous • Active</span>
          </div>

          {/* Pipeline status badge */}
          <div
            className={cn(
              "flex items-center gap-2 rounded-xl border px-3 py-2",
              isRunning
                ? "border-purple-500/30 bg-purple-500/10"
                : "border-white/[0.06] bg-white/[0.03]"
            )}
          >
            {isRunning ? (
              <Loader2 className="h-4 w-4 animate-spin text-purple-400" />
            ) : (
              <Activity className="h-4 w-4 text-white/30" />
            )}
            <span className="text-xs font-medium text-white/60">
              {isRunning ? `${completedCount}/${totalAgents} agents` : "Idle"}
            </span>
          </div>

          {/* Trigger button */}
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={triggerPipeline}
            disabled={triggering || isRunning}
            className={cn(
              "flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-medium",
              "bg-gradient-to-r from-purple-500 to-pink-500 text-white",
              "shadow-lg shadow-purple-500/20 hover:shadow-purple-500/30 transition-shadow",
              "disabled:opacity-50 disabled:cursor-not-allowed"
            )}
          >
            {triggering ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            {triggering ? "Starting…" : "Run Now"}
          </motion.button>
        </div>
      </motion.div>

      {/* ─── Pipeline Progress Bar ────────────────────────── */}
      {(isRunning || completedCount > 0) && (
        <motion.div variants={fadeInUp}>
          <GlassCard className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-white/50">Pipeline Progress</span>
              <span className="text-xs font-bold text-purple-400">{progressPercent}%</span>
            </div>
            <div className="h-2 w-full rounded-full bg-white/[0.06] overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-purple-500 to-pink-500"
                initial={{ width: "0%" }}
                animate={{ width: `${progressPercent}%` }}
                transition={{ duration: 0.5, ease: "easeOut" }}
              />
            </div>
          </GlassCard>
        </motion.div>
      )}

      {/* ─── Flow Chart ───────────────────────────────────── */}
      <motion.div variants={fadeInUp}>
        <GlassCard className="p-6" glow>
          <div className="mb-4 flex items-center gap-2">
            <Bot className="h-5 w-5 text-purple-400" />
            <h2 className="text-sm font-semibold text-white/80">Agent Pipeline Flow</h2>
          </div>
          <AgentFlowChart
            stages={stages}
            currentAgent={currentAgent}
            reasoningSteps={reasoningSteps}
          />
        </GlassCard>
      </motion.div>

      {/* ─── Activity Feed + History ──────────────────────── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Activity Feed */}
        <motion.div variants={fadeInUp}>
          <GlassCard className="p-5">
            <div className="mb-4 flex items-center gap-2">
              <Zap className="h-4 w-4 text-amber-400" />
              <h3 className="text-sm font-semibold text-white/80">Live Activity</h3>
            </div>

            <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
              {activityFeed.length === 0 ? (
                <p className="py-8 text-center text-xs text-white/20">
                  Run the pipeline to see live agent activity
                </p>
              ) : (
                <AnimatePresence mode="popLayout">
                  {activityFeed.map((entry) => (
                    <motion.div
                      key={entry.id}
                      initial={{ opacity: 0, x: -12 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, height: 0 }}
                      className="flex items-start gap-3 rounded-lg border border-white/[0.03] bg-white/[0.015] p-3"
                    >
                      <div
                        className={cn(
                          "mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full",
                          entry.type === "reasoning" ? "bg-purple-400" : "bg-cyan-400"
                        )}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="text-[10px] font-semibold uppercase tracking-wider text-white/30">
                          {entry.agent.replace(/_/g, " ")}
                        </p>
                        <p className="mt-0.5 text-xs text-white/50">{entry.message}</p>
                      </div>
                      <span className="shrink-0 text-[9px] text-white/15">
                        {formatDate(entry.timestamp)}
                      </span>
                    </motion.div>
                  ))}
                </AnimatePresence>
              )}
            </div>
          </GlassCard>
        </motion.div>

        {/* Pipeline History */}
        <motion.div variants={fadeInUp}>
          <GlassCard className="p-5">
            <div className="mb-4 flex items-center gap-2">
              <Clock className="h-4 w-4 text-white/40" />
              <h3 className="text-sm font-semibold text-white/80">Pipeline History</h3>
            </div>

            <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
              {history.length === 0 ? (
                <p className="py-8 text-center text-xs text-white/20">
                  No pipeline runs yet
                </p>
              ) : (
                history.map((run) => (
                  <div
                    key={run.pipeline_id}
                    className="flex items-center gap-3 rounded-lg border border-white/[0.03] bg-white/[0.015] p-3"
                  >
                    {run.status === "completed" ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                    ) : run.status === "running" ? (
                      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-purple-400" />
                    ) : (
                      <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-white/70 truncate">
                        {run.item_name ?? "Unknown Item"}
                      </p>
                      <p className="mt-0.5 text-[10px] text-white/30">
                        {run.stages.filter((s) => s.status === "completed").length}/{run.stages.length} agents
                        {run.completed_at && ` · ${formatDate(run.completed_at)}`}
                      </p>
                    </div>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase",
                        run.status === "completed"
                          ? "bg-emerald-500/10 text-emerald-400"
                          : run.status === "running"
                            ? "bg-purple-500/10 text-purple-400"
                            : "bg-red-500/10 text-red-400"
                      )}
                    >
                      {run.status}
                    </span>
                  </div>
                ))
              )}
            </div>
          </GlassCard>
        </motion.div>
      </div>
    </motion.div>
  );
}
