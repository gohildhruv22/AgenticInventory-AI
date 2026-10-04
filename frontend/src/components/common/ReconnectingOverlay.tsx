import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { WifiOff, Loader2 } from "lucide-react";
import { wsClient } from "@/services/socket";

export function ReconnectingOverlay() {
  const [disconnected, setDisconnected] = useState(false);

  useEffect(() => {
    const unsub = wsClient.onStatusChange((status: string) => {
      setDisconnected(status === "disconnected" || status === "reconnecting");
    });
    return unsub;
  }, []);

  return (
    <AnimatePresence>
      {disconnected && (
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          className="fixed left-1/2 top-4 z-[100] -translate-x-1/2"
        >
          <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white/95 px-5 py-3 shadow-[0_10px_30px_rgba(15,23,42,0.12)] backdrop-blur-xl">
            <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-rose-50 text-rose-500">
              <WifiOff className="h-3.5 w-3.5" />
            </span>
            <span className="text-sm font-semibold text-slate-700">
              Connection lost
            </span>
            <span className="h-3 w-px bg-slate-200" />
            <Loader2 className="h-3.5 w-3.5 animate-spin text-violet-500" />
            <span className="text-xs font-medium text-slate-500">Reconnecting…</span>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
