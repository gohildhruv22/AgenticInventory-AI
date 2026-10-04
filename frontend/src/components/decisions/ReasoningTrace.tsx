import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, Brain, AlertTriangle, Target, Lightbulb, BarChart3 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ReasoningTrace as ReasoningTraceType } from "@/types/agent";

interface ReasoningTraceProps {
  trace: ReasoningTraceType;
  alternatives?: Record<string, unknown>[];
  className?: string;
}

export function ReasoningTrace({ trace, alternatives, className }: ReasoningTraceProps) {
  const [isOpen, setIsOpen] = useState(false);

  const sections = buildSections(trace, alternatives);

  return (
    <div className={cn("overflow-hidden rounded-xl border border-white/[0.06]", className)}>
      {/* Toggle header */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "flex w-full items-center justify-between px-4 py-3",
          "bg-white/[0.02] hover:bg-white/[0.04] transition-colors",
          "text-left"
        )}
      >
        <span className="flex items-center gap-2 text-sm font-medium text-white/60">
          <Brain className="h-4 w-4 text-purple-400" />
          Reasoning Trace
        </span>
        <motion.span
          animate={{ rotate: isOpen ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronDown className="h-4 w-4 text-white/40" />
        </motion.span>
      </button>

      {/* Collapsible content */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="space-y-3 border-t border-white/[0.04] px-4 py-4">
              {sections.map((section, i) => (
                <TraceSection
                  key={section.label}
                  icon={section.icon}
                  label={section.label}
                  content={section.content}
                  variant={section.variant}
                  index={i}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ─── Section Renderer ───────────────────────────────────────────── */

interface TraceSectionProps {
  icon: React.ReactNode;
  label: string;
  content: React.ReactNode;
  variant?: "default" | "warn" | "info";
  index: number;
}

function TraceSection({ icon, label, content, variant = "default", index }: TraceSectionProps) {
  const borderColor =
    variant === "warn"
      ? "border-amber-500/20"
      : variant === "info"
      ? "border-cyan-500/20"
      : "border-white/[0.04]";

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05, duration: 0.2 }}
      className={cn(
        "rounded-lg border bg-white/[0.015] p-3",
        borderColor
      )}
    >
      <div className="mb-1.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-white/40">
        {icon}
        {label}
      </div>
      <div className="text-sm leading-relaxed text-white/70">{content}</div>
    </motion.div>
  );
}

/* ─── Build sections from trace data ─────────────────────────────── */

function buildSections(
  trace: ReasoningTraceType,
  alternatives?: Record<string, unknown>[]
) {
  const sections: {
    icon: React.ReactNode;
    label: string;
    content: React.ReactNode;
    variant?: "default" | "warn" | "info";
  }[] = [];

  // Reasoning / Rationale
  const reasoning = trace.reasoning || trace.rationale;
  if (reasoning) {
    sections.push({
      icon: <Brain className="h-3.5 w-3.5 text-purple-400" />,
      label: "Reasoning",
      content: reasoning,
    });
  }

  // Risk factors
  if (trace.risk_factors && trace.risk_factors.length > 0) {
    sections.push({
      icon: <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />,
      label: "Risk Factors",
      variant: "warn",
      content: (
        <ul className="space-y-1">
          {trace.risk_factors.map((r, i) => (
            <li key={i} className="flex items-start gap-2">
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-amber-400" />
              <span>{r}</span>
            </li>
          ))}
        </ul>
      ),
    });
  }

  // Forecast data
  if (trace.predicted_demand != null || trace.forecast_confidence != null) {
    sections.push({
      icon: <BarChart3 className="h-3.5 w-3.5 text-cyan-400" />,
      label: "Forecast Data",
      variant: "info",
      content: (
        <div className="grid grid-cols-2 gap-2 text-xs">
          {trace.predicted_demand != null && (
            <div>
              <span className="text-white/40">Predicted Demand:</span>{" "}
              <span className="font-medium text-white/80">{trace.predicted_demand}</span>
            </div>
          )}
          {trace.forecast_confidence != null && (
            <div>
              <span className="text-white/40">Forecast Confidence:</span>{" "}
              <span className="font-medium text-white/80">{trace.forecast_confidence}%</span>
            </div>
          )}
          {trace.suggested_order_qty != null && (
            <div>
              <span className="text-white/40">Suggested Qty:</span>{" "}
              <span className="font-medium text-white/80">{trace.suggested_order_qty}</span>
            </div>
          )}
          {trace.approved_order_qty != null && (
            <div>
              <span className="text-white/40">Approved Qty:</span>{" "}
              <span className="font-medium text-white/80">{trace.approved_order_qty}</span>
            </div>
          )}
        </div>
      ),
    });
  }

  // Item context
  if (trace.item_context) {
    sections.push({
      icon: <Target className="h-3.5 w-3.5 text-emerald-400" />,
      label: "Item Context",
      content: (
        <div className="grid grid-cols-2 gap-2 text-xs">
          {trace.item_context.name && (
            <div>
              <span className="text-white/40">Name:</span>{" "}
              <span className="font-medium text-white/80">{trace.item_context.name}</span>
            </div>
          )}
          {trace.item_context.sku && (
            <div>
              <span className="text-white/40">SKU:</span>{" "}
              <span className="font-mono text-white/80">{trace.item_context.sku}</span>
            </div>
          )}
          {trace.item_context.current_stock != null && (
            <div>
              <span className="text-white/40">Current Stock:</span>{" "}
              <span className="font-medium text-white/80">{trace.item_context.current_stock}</span>
            </div>
          )}
          {trace.item_context.unit_cost != null && (
            <div>
              <span className="text-white/40">Unit Cost:</span>{" "}
              <span className="font-medium text-white/80">
                ${trace.item_context.unit_cost.toFixed(2)}
              </span>
            </div>
          )}
        </div>
      ),
    });
  }

  // Alternatives considered
  const alts = alternatives && alternatives.length > 0 ? alternatives : trace.alternatives;
  if (alts && alts.length > 0) {
    sections.push({
      icon: <Lightbulb className="h-3.5 w-3.5 text-yellow-400" />,
      label: "Alternatives Considered",
      content: (
        <div className="space-y-2">
          {alts.map((alt, i) => (
            <div
              key={i}
              className="rounded-md border border-white/[0.04] bg-white/[0.01] px-3 py-2"
            >
              <div className="text-xs font-medium text-white/60">
                {(alt as Record<string, string>).action || JSON.stringify(alt)}
              </div>
              {(alt as Record<string, string>).reason && (
                <div className="mt-0.5 text-xs text-white/40">
                  {(alt as Record<string, string>).reason}
                </div>
              )}
            </div>
          ))}
        </div>
      ),
    });
  }

  return sections;
}
