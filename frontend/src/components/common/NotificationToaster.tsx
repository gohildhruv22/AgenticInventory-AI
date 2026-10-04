import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Info,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { wsClient } from "@/services/socket";

export type ToastVariant = "success" | "warning" | "error" | "info";

interface Toast {
  id: string;
  title: string;
  message?: string;
  variant: ToastVariant;
  createdAt: number;
}

const TOAST_DURATION = 6000;

const variantConfig: Record<
  ToastVariant,
  { icon: typeof CheckCircle2; border: string; bg: string; iconColor: string; iconBg: string }
> = {
  success: {
    icon: CheckCircle2,
    border: "border-emerald-200",
    bg: "bg-white",
    iconColor: "text-emerald-600",
    iconBg: "bg-emerald-50",
  },
  warning: {
    icon: AlertTriangle,
    border: "border-amber-200",
    bg: "bg-white",
    iconColor: "text-amber-600",
    iconBg: "bg-amber-50",
  },
  error: {
    icon: XCircle,
    border: "border-red-200",
    bg: "bg-white",
    iconColor: "text-red-600",
    iconBg: "bg-red-50",
  },
  info: {
    icon: Info,
    border: "border-violet-200",
    bg: "bg-white",
    iconColor: "text-violet-600",
    iconBg: "bg-violet-50",
  },
};

// Global toast emitter
type ToastListener = (toast: Omit<Toast, "id" | "createdAt">) => void;
let _listener: ToastListener | null = null;

export function showToast(
  title: string,
  message?: string,
  variant: ToastVariant = "info"
) {
  _listener?.({ title, message, variant });
}

export function NotificationToaster() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback(
    (toast: Omit<Toast, "id" | "createdAt">) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
      setToasts((prev) => [...prev.slice(-4), { ...toast, id, createdAt: Date.now() }]);
    },
    []
  );

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Register global listener
  useEffect(() => {
    _listener = addToast;
    return () => {
      _listener = null;
    };
  }, [addToast]);

  // Listen for WebSocket notification events
  useEffect(() => {
    const unsub = wsClient.subscribe((event, data) => {
      if (event === "notification") {
        const payload = data as { title: string; message?: string; variant?: ToastVariant };
        addToast({
          title: payload.title,
          message: payload.message,
          variant: payload.variant ?? "info",
        });
      }
      if (event === "agent:status") {
        const payload = data as { agent_type: string; status: string; message: string };
        if (payload.status === "completed") {
          addToast({
            title: `${payload.agent_type.replace(/_/g, " ")} completed`,
            message: payload.message,
            variant: "success",
          });
        }
      }
    });
    return unsub;
  }, [addToast]);

  // Auto-remove after duration
  useEffect(() => {
    if (toasts.length === 0) return;
    const timer = setInterval(() => {
      const now = Date.now();
      setToasts((prev) => prev.filter((t) => now - t.createdAt < TOAST_DURATION));
    }, 1000);
    return () => clearInterval(timer);
  }, [toasts.length]);

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[110] flex flex-col gap-2 w-96">
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => {
          const config = variantConfig[toast.variant];
          const Icon = config.icon;

          return (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: 80, scale: 0.95 }}
              transition={{ duration: 0.25, ease: "easeOut" }}
              className={cn(
                "pointer-events-auto flex items-start gap-3 rounded-2xl border p-4 shadow-[0_10px_30px_rgba(15,23,42,0.10),0_4px_12px_rgba(15,23,42,0.06)]",
                config.border,
                config.bg
              )}
            >
              <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-xl", config.iconBg)}>
                <Icon className={cn("h-5 w-5", config.iconColor)} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-900">{toast.title}</p>
                {toast.message && (
                  <p className="mt-0.5 text-xs text-slate-500 line-clamp-2">{toast.message}</p>
                )}
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="shrink-0 rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
