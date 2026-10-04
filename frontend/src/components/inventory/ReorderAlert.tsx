import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, X } from "lucide-react";
import { wsClient } from "@/services/socket";
import { cn } from "@/lib/utils";

interface Alert {
  id: string;
  item_id: string;
  name: string;
  sku: string;
  current_stock: number;
  status: string;
  message: string;
  timestamp: number;
}

export function ReorderAlert() {
  const [alerts, setAlerts] = useState<Alert[]>([]);

  useEffect(() => {
    const unsub = wsClient.subscribe((event, data) => {
      if (event === "inventory:alert") {
        const d = data as Record<string, unknown>;
        setAlerts((prev) => [
          {
            id: `${d.item_id}-${Date.now()}`,
            item_id: d.item_id as string,
            name: d.name as string,
            sku: d.sku as string,
            current_stock: d.current_stock as number,
            status: d.status as string,
            message: d.message as string,
            timestamp: Date.now(),
          },
          ...prev.slice(0, 4), // Keep max 5 alerts
        ]);
      }
    });
    return unsub;
  }, []);

  const dismiss = (id: string) => {
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3">
      <AnimatePresence>
        {alerts.map((alert) => (
          <motion.div
            key={alert.id}
            initial={{ x: 300, opacity: 0, scale: 0.8 }}
            animate={{ x: 0, opacity: 1, scale: 1 }}
            exit={{ x: 300, opacity: 0, scale: 0.8 }}
            transition={{ type: "spring", stiffness: 300, damping: 25 }}
            className={cn(
              "flex items-start gap-3 rounded-xl border p-4 backdrop-blur-xl shadow-2xl max-w-sm",
              alert.status === "out_of_stock"
                ? "border-red-500/20 bg-red-500/5"
                : "border-amber-500/20 bg-amber-500/5"
            )}
          >
            <AlertTriangle
              className={cn(
                "mt-0.5 h-5 w-5 shrink-0",
                alert.status === "out_of_stock"
                  ? "text-red-400"
                  : "text-amber-400"
              )}
            />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-white">
                {alert.name}
              </p>
              <p className="text-xs text-white/50 mt-0.5">
                {alert.sku} &middot; Stock: {alert.current_stock}
              </p>
            </div>
            <button
              onClick={() => dismiss(alert.id)}
              className="text-white/30 hover:text-white/60 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
