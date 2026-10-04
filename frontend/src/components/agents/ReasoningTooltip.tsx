import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageSquare, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

interface ReasoningStep {
  step: string;
  message: string;
  progress: number;
  timestamp: string;
}

interface ReasoningTooltipProps {
  agentType: string;
  agentLabel: string;
  steps: ReasoningStep[];
  confidence?: number;
  className?: string;
}

export function ReasoningTooltip({
  agentType: _agentType,
  agentLabel,
  steps,
  confidence,
  className,
}: ReasoningTooltipProps) {
  void _agentType;
  const [open, setOpen] = useState(false);

  if (steps.length === 0) return null;

  return (
    <div
      className={cn("relative", className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-[10px] text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition-colors">
        <MessageSquare className="h-3 w-3" />
        {steps.length} steps
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 4, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className={cn(
              "absolute bottom-full left-1/2 z-50 mb-2 w-72 -translate-x-1/2",
              "rounded-xl border border-slate-200 bg-white p-4",
              "shadow-[0_10px_30px_rgba(15,23,42,0.10),0_4px_12px_rgba(15,23,42,0.06)]"
            )}
          >
            {/* Header */}
            <div className="mb-3 flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-900">{agentLabel}</span>
              {confidence != null && (
                <span className="flex items-center gap-1 rounded-full bg-violet-50 px-2 py-0.5 text-[10px] font-bold text-violet-600">
                  <Zap className="h-3 w-3" />
                  {confidence}%
                </span>
              )}
            </div>

            {/* Steps */}
            <div className="space-y-2">
              {steps.map((step, idx) => (
                <motion.div
                  key={step.step}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.04 }}
                  className="flex gap-2"
                >
                  <div className="flex flex-col items-center pt-1">
                    <div className="h-1.5 w-1.5 rounded-full bg-violet-500" />
                    {idx < steps.length - 1 && (
                      <div className="mt-0.5 h-full w-px bg-slate-200" />
                    )}
                  </div>
                  <p className="text-[10px] leading-relaxed text-slate-600">
                    {step.message}
                  </p>
                </motion.div>
              ))}
            </div>

            {/* Arrow */}
            <div className="absolute -bottom-1.5 left-1/2 h-3 w-3 -translate-x-1/2 rotate-45 border-b border-r border-slate-200 bg-white" />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
