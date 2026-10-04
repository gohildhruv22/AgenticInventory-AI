import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

type StockStatus = "normal" | "low_stock" | "out_of_stock" | "reorder_pending";

interface StockLevelBadgeProps {
  status: StockStatus;
  currentStock: number;
  threshold: number;
  className?: string;
}

const statusConfig: Record<
  StockStatus,
  { label: string; bg: string; text: string; dot: string }
> = {
  normal: {
    label: "Normal",
    bg: "bg-emerald-500/10",
    text: "text-emerald-400",
    dot: "bg-emerald-400",
  },
  low_stock: {
    label: "Low Stock",
    bg: "bg-amber-500/10",
    text: "text-amber-400",
    dot: "bg-amber-400",
  },
  out_of_stock: {
    label: "Out of Stock",
    bg: "bg-red-500/10",
    text: "text-red-400",
    dot: "bg-red-400",
  },
  reorder_pending: {
    label: "Reorder Pending",
    bg: "bg-purple-500/10",
    text: "text-purple-400",
    dot: "bg-purple-400",
  },
};

export function StockLevelBadge({
  status,
  currentStock,
  threshold,
  className,
}: StockLevelBadgeProps) {
  const config = statusConfig[status];
  const ratio = threshold > 0 ? Math.min(currentStock / threshold, 2) : 1;

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={status}
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        transition={{ duration: 0.2 }}
        className={cn(
          "inline-flex items-center gap-2 rounded-full px-3 py-1",
          config.bg,
          className
        )}
      >
        {/* Pulsing dot */}
        <span className="relative flex h-2 w-2">
          {status !== "normal" && (
            <motion.span
              className={cn(
                "absolute inline-flex h-full w-full rounded-full opacity-75",
                config.dot
              )}
              animate={{ scale: [1, 1.5, 1], opacity: [0.75, 0, 0.75] }}
              transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
            />
          )}
          <span
            className={cn(
              "relative inline-flex h-2 w-2 rounded-full",
              config.dot
            )}
          />
        </span>

        <span className={cn("text-xs font-semibold", config.text)}>
          {config.label}
        </span>

        {/* Stock level bar */}
        <div className="ml-1 h-1.5 w-10 overflow-hidden rounded-full bg-white/5">
          <motion.div
            className={cn("h-full rounded-full", config.dot)}
            initial={{ width: 0 }}
            animate={{ width: `${Math.min(ratio * 50, 100)}%` }}
            transition={{ duration: 0.6, ease: "easeOut" }}
          />
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
