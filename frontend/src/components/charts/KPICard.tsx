import { motion } from "framer-motion";
import { fadeInUp, defaultTransition } from "@/lib/animations";
import { AnimatedCounter } from "@/components/ui/AnimatedCounter";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface KPICardProps {
  label: string;
  value: number;
  format?: (v: number) => string;
  icon: LucideIcon;
  gradient: string;
  trend?: { value: number; label: string };
  className?: string;
}

export function KPICard({
  label,
  value,
  format,
  icon: Icon,
  gradient,
  trend,
  className,
}: KPICardProps) {
  return (
    <motion.div
      variants={fadeInUp}
      initial="initial"
      animate="animate"
      exit="exit"
      transition={defaultTransition}
      className={cn(
        "group relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-5",
        "shadow-[0_1px_3px_rgba(15,23,42,0.04),0_4px_14px_rgba(15,23,42,0.05)]",
        "hover:border-violet-200",
        "hover:shadow-[0_4px_14px_rgba(124,58,237,0.10),0_12px_28px_rgba(124,58,237,0.08)]",
        "transition-all duration-300",
        className
      )}
    >
      {/* Background gradient glow */}
      <div
        className={cn(
          "absolute -right-6 -top-6 h-24 w-24 rounded-full opacity-25 blur-2xl transition-opacity duration-500 group-hover:opacity-40",
          gradient
        )}
      />

      <div className="relative flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-2">
          <p className="truncate text-[11px] font-semibold uppercase tracking-widest text-slate-500">
            {label}
          </p>
          <AnimatedCounter
            value={value}
            format={format}
            className="block truncate text-2xl font-bold tracking-tight text-slate-900"
          />
          {trend && (
            <div className="flex items-center gap-1.5">
              <span
                className={cn(
                  "text-xs font-semibold",
                  trend.value >= 0 ? "text-emerald-600" : "text-red-600"
                )}
              >
                {trend.value >= 0 ? "+" : ""}
                {trend.value}%
              </span>
              <span className="text-xs text-slate-400">{trend.label}</span>
            </div>
          )}
        </div>

        <div
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
            gradient,
            "shadow-md transition-transform duration-300 group-hover:scale-110"
          )}
        >
          <Icon className="h-5 w-5 text-white" />
        </div>
      </div>
    </motion.div>
  );
}
