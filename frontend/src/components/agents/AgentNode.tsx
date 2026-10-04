import { motion } from "framer-motion";
import {
  Eye,
  TrendingUp,
  Brain,
  Mail,
  Truck,
  Undo2,
  BarChart3,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type AgentStatus = "idle" | "processing" | "completed" | "error";

interface AgentNodeProps {
  agentType: string;
  label: string;
  status: AgentStatus;
  summary?: string | null;
  isActive?: boolean;
  className?: string;
  onClick?: () => void;
}

const agentConfig: Record<string, { icon: LucideIcon; gradient: string; color: string }> = {
  inventory_monitor: { icon: Eye, gradient: "from-cyan-500 to-blue-500", color: "cyan" },
  demand_forecast: { icon: TrendingUp, gradient: "from-purple-500 to-indigo-500", color: "purple" },
  decision_manager: { icon: Brain, gradient: "from-pink-500 to-rose-500", color: "pink" },
  supplier_email: { icon: Mail, gradient: "from-amber-500 to-orange-500", color: "amber" },
  delivery_tracker: { icon: Truck, gradient: "from-emerald-500 to-teal-500", color: "emerald" },
  undo_rollback: { icon: Undo2, gradient: "from-slate-500 to-zinc-500", color: "slate" },
  reporting_kpi: { icon: BarChart3, gradient: "from-violet-500 to-purple-500", color: "violet" },
};

const statusColors: Record<AgentStatus, { ring: string; dot: string; bg: string }> = {
  idle: { ring: "border-white/[0.08]", dot: "bg-white/30", bg: "bg-white/[0.02]" },
  processing: { ring: "border-purple-500/40", dot: "bg-purple-400", bg: "bg-purple-500/[0.06]" },
  completed: { ring: "border-emerald-500/30", dot: "bg-emerald-400", bg: "bg-emerald-500/[0.04]" },
  error: { ring: "border-red-500/30", dot: "bg-red-400", bg: "bg-red-500/[0.04]" },
};

export function AgentNode({
  agentType,
  label,
  status,
  summary,
  isActive,
  className,
  onClick,
}: AgentNodeProps) {
  const config = agentConfig[agentType] ?? agentConfig.inventory_monitor;
  const Icon = config.icon;
  const stColors = statusColors[status] ?? statusColors.idle;

  return (
    <motion.div
      layout
      onClick={onClick}
      whileHover={{ scale: 1.03, y: -2 }}
      className={cn(
        "relative flex w-36 flex-col items-center gap-2 rounded-2xl border p-4 backdrop-blur-xl cursor-pointer",
        "transition-colors duration-300",
        stColors.ring,
        stColors.bg,
        isActive && "border-purple-500/50 shadow-[0_0_30px_rgba(139,92,246,0.2)]",
        className
      )}
    >
      {/* Processing glow pulse */}
      {status === "processing" && (
        <motion.div
          className="absolute inset-0 rounded-2xl border-2 border-purple-500/30"
          animate={{
            opacity: [0.5, 0, 0.5],
            scale: [1, 1.03, 1],
          }}
          transition={{ repeat: Infinity, duration: 1.5, ease: "easeInOut" }}
        />
      )}

      {/* Icon */}
      <div
        className={cn(
          "flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br shadow-lg",
          config.gradient,
          status === "idle" && "opacity-50",
        )}
      >
        <Icon className="h-5 w-5 text-white" />
      </div>

      {/* Label */}
      <span className="text-[11px] font-semibold text-white/80 text-center leading-tight">
        {label}
      </span>

      {/* Status dot */}
      <div className="flex items-center gap-1.5">
        <span className="relative flex h-2 w-2">
          {(status === "processing" || (status === "completed" && isActive)) && (
            <motion.span
              className={cn("absolute inline-flex h-full w-full rounded-full opacity-75", stColors.dot)}
              animate={{ scale: [1, 1.8, 1], opacity: [0.75, 0, 0.75] }}
              transition={{ repeat: Infinity, duration: 1.5 }}
            />
          )}
          <span className={cn("relative inline-flex h-2 w-2 rounded-full", stColors.dot)} />
        </span>
        <span className="text-[9px] uppercase tracking-wider text-white/30 font-semibold">
          {status}
        </span>
      </div>

      {/* Summary tooltip preview */}
      {summary && (
        <p className="mt-1 line-clamp-2 text-center text-[9px] leading-tight text-white/30">
          {summary}
        </p>
      )}
    </motion.div>
  );
}
