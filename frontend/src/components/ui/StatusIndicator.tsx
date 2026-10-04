import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface StatusIndicatorProps {
  status: string;
  label?: string;
  className?: string;
}

const colorMap: Record<string, string> = {
  normal: "bg-emerald-400",
  healthy: "bg-emerald-400",
  connected: "bg-emerald-400",
  executed: "bg-emerald-400",
  delivered: "bg-emerald-400",
  low_stock: "bg-amber-400",
  degraded: "bg-amber-400",
  pending_review: "bg-amber-400",
  in_transit: "bg-blue-400",
  out_of_stock: "bg-red-400",
  unhealthy: "bg-red-400",
  failed: "bg-red-400",
  disconnected: "bg-red-400",
  reorder_pending: "bg-purple-400",
  processing: "bg-purple-400",
  connecting: "bg-yellow-400",
  rolled_back: "bg-slate-400",
};

export function StatusIndicator({
  status,
  label,
  className,
}: StatusIndicatorProps) {
  const dotColor = colorMap[status] ?? "bg-slate-400";

  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span className="relative flex h-2.5 w-2.5">
        <motion.span
          className={cn(
            "absolute inline-flex h-full w-full rounded-full opacity-75",
            dotColor
          )}
          animate={{ scale: [1, 1.6, 1], opacity: [0.75, 0, 0.75] }}
          transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
        />
        <span
          className={cn(
            "relative inline-flex h-2.5 w-2.5 rounded-full",
            dotColor
          )}
        />
      </span>
      {label && (
        <span className="text-xs font-medium capitalize text-slate-600">
          {label.replace(/_/g, " ")}
        </span>
      )}
    </span>
  );
}
