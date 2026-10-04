import { useLocation } from "react-router-dom";
import { Bell, User } from "lucide-react";
import { StatusIndicator } from "@/components/ui/StatusIndicator";
import { useWebSocket } from "@/hooks/useWebSocket";

const pathLabels: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/inventory": "Inventory",
  "/decisions": "Decisions",
  "/deliveries": "Deliveries",
  "/analytics": "Analytics",
  "/reports": "Reports",
  "/agents": "Agents",
  "/settings": "Settings",
};

export function Header() {
  const location = useLocation();
  const { status } = useWebSocket();

  const pageLabel =
    pathLabels[location.pathname] ??
    location.pathname.slice(1).replace(/^\w/, (c) => c.toUpperCase());

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-white/85 px-6 backdrop-blur-xl">
      {/* Left – breadcrumb */}
      <div className="flex items-center gap-2 text-sm">
        <span className="text-slate-400">Home</span>
        <span className="text-slate-300">/</span>
        <span className="font-semibold text-slate-900">{pageLabel}</span>
      </div>

      {/* Right – actions */}
      <div className="flex items-center gap-3">
        <StatusIndicator status={status} label={status} />

        <div className="hidden h-6 w-px bg-slate-200 sm:block" />

        <button
          aria-label="Notifications"
          className="relative rounded-xl p-2 text-slate-500 transition-colors hover:bg-violet-50 hover:text-violet-600"
        >
          <Bell className="h-5 w-5" />
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-rose-500 ring-2 ring-white" />
        </button>

        <button
          aria-label="Account"
          className="flex items-center gap-2 rounded-xl p-1.5 transition-colors hover:bg-violet-50"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-violet-600 to-fuchsia-600 shadow-md shadow-violet-500/20 ring-2 ring-white">
            <User className="h-4 w-4 text-white" />
          </div>
        </button>
      </div>
    </header>
  );
}
