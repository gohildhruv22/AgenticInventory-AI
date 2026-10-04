import { motion } from "framer-motion";
import {
  Database,
  TrendingUp,
  ShieldAlert,
  Scale,
  CheckCircle2,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { AgentDecision, ReasoningTrace } from "@/types/agent";

interface Step {
  label: string;
  detail: string;
  icon: LucideIcon;
  tone: "neutral" | "info" | "warn" | "good";
}

interface DecisionStepsProps {
  decision: AgentDecision;
  className?: string;
}

/**
 * Derives a human-readable, ordered list of "steps" the agent took to
 * reach a decision from its reasoning_trace + alternatives_considered.
 */
function buildSteps(decision: AgentDecision): Step[] {
  const trace: ReasoningTrace = decision.reasoning_trace ?? {};
  const steps: Step[] = [];

  // 1. Inspect item context / inputs
  const itemName = trace.item_context?.name;
  const sku = trace.item_context?.sku;
  const currentStock = trace.item_context?.current_stock;
  if (itemName || sku || currentStock != null) {
    const parts: string[] = [];
    if (itemName) parts.push(itemName);
    if (sku) parts.push(`SKU ${sku}`);
    if (currentStock != null) parts.push(`stock ${currentStock}`);
    steps.push({
      label: "Gathered item context",
      detail: parts.join(" · "),
      icon: Database,
      tone: "neutral",
    });
  } else if (trace.input_context) {
    steps.push({
      label: "Gathered input context",
      detail: String(trace.input_context).slice(0, 140),
      icon: Database,
      tone: "neutral",
    });
  }

  // 2. Forecast / demand analysis
  if (trace.predicted_demand != null || trace.forecast_confidence != null) {
    const parts: string[] = [];
    if (trace.predicted_demand != null) parts.push(`predicted demand ${trace.predicted_demand}`);
    if (trace.forecast_confidence != null) parts.push(`forecast confidence ${trace.forecast_confidence}%`);
    if (trace.suggested_order_qty != null) parts.push(`suggested qty ${trace.suggested_order_qty}`);
    steps.push({
      label: "Reviewed demand forecast",
      detail: parts.join(" · "),
      icon: TrendingUp,
      tone: "info",
    });
  }

  // 3. Risk evaluation
  if (trace.risk_factors && trace.risk_factors.length > 0) {
    steps.push({
      label: `Evaluated ${trace.risk_factors.length} risk factor${trace.risk_factors.length > 1 ? "s" : ""}`,
      detail: trace.risk_factors.slice(0, 2).join(" · "),
      icon: ShieldAlert,
      tone: "warn",
    });
  }

  // 4. Alternatives considered
  const alts = decision.alternatives_considered?.length
    ? decision.alternatives_considered
    : trace.alternatives ?? [];
  if (alts && alts.length > 0) {
    const first = alts[0] as Record<string, string>;
    const altLabel = first.action || first.option || "alternative path";
    steps.push({
      label: `Weighed ${alts.length} alternative${alts.length > 1 ? "s" : ""}`,
      detail: `e.g. ${altLabel}${first.rejected_because ? ` — rejected: ${first.rejected_because}` : ""}`,
      icon: Scale,
      tone: "neutral",
    });
  }

  // 5. Final decision
  const decisionLabel = trace.decision || decision.action_type.replace(/_/g, " ");
  const confidence = decision.confidence_level;
  const finalDetail =
    (trace.approved_order_qty != null ? `qty ${trace.approved_order_qty}` : "") +
    (trace.estimated_cost != null && trace.estimated_cost > 0
      ? `${trace.approved_order_qty != null ? " · " : ""}$${trace.estimated_cost.toFixed(2)}`
      : "") ||
    (confidence != null ? `${confidence}% confidence` : "");

  steps.push({
    label: `Decision: ${decisionLabel}`,
    detail: finalDetail || (trace.reasoning ? trace.reasoning.slice(0, 120) : "executed"),
    icon: CheckCircle2,
    tone: decision.status === "rolled_back"
      ? "warn"
      : decision.status === "flagged" || decision.status === "pending_review"
      ? "warn"
      : "good",
  });

  return steps;
}

const toneStyles: Record<Step["tone"], { ring: string; icon: string; line: string }> = {
  neutral: {
    ring: "border-white/15 bg-white/[0.04]",
    icon: "text-white/60",
    line: "bg-white/10",
  },
  info: {
    ring: "border-cyan-400/30 bg-cyan-500/10",
    icon: "text-cyan-300",
    line: "bg-cyan-400/20",
  },
  warn: {
    ring: "border-amber-400/30 bg-amber-500/10",
    icon: "text-amber-300",
    line: "bg-amber-400/20",
  },
  good: {
    ring: "border-emerald-400/30 bg-emerald-500/10",
    icon: "text-emerald-300",
    line: "bg-emerald-400/20",
  },
};

export function DecisionSteps({ decision, className }: DecisionStepsProps) {
  const steps = buildSteps(decision);
  if (steps.length === 0) return null;

  return (
    <div className={cn("rounded-xl border border-white/[0.06] bg-white/[0.015] p-4", className)}>
      <div className="mb-3 flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.16em] text-white/40">
          <Scale className="h-3.5 w-3.5 text-purple-300" />
          Agent's Thought Process
        </span>
        <span className="text-[10px] text-white/30">{steps.length} steps</span>
      </div>

      <ol className="relative space-y-3">
        {steps.map((step, i) => {
          const Icon = step.icon;
          const tone = toneStyles[step.tone];
          const isLast = i === steps.length - 1;
          return (
            <motion.li
              key={i}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.04 * i, duration: 0.25 }}
              className="relative flex gap-3"
            >
              {/* Step indicator + connector */}
              <div className="relative flex flex-col items-center">
                <div
                  className={cn(
                    "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border",
                    tone.ring
                  )}
                >
                  <Icon className={cn("h-3.5 w-3.5", tone.icon)} />
                </div>
                {!isLast && (
                  <div className={cn("mt-1 w-px flex-1 min-h-[18px]", tone.line)} />
                )}
              </div>

              {/* Step content */}
              <div className="flex-1 pb-1">
                <div className="flex items-baseline gap-2">
                  <span className="text-[10px] font-semibold text-white/35">
                    Step {i + 1}
                  </span>
                  <p className="text-sm font-medium text-white/85">{step.label}</p>
                </div>
                {step.detail && (
                  <p className="mt-0.5 text-xs leading-relaxed text-white/45">
                    {step.detail}
                  </p>
                )}
              </div>
            </motion.li>
          );
        })}
      </ol>
    </div>
  );
}
