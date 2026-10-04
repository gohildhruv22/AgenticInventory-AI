import { NavLink, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  Package,
  Brain,
  Truck,
  BarChart3,
  FileText,
  Bot,
  Settings,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

const icons = {
  LayoutDashboard,
  Package,
  Brain,
  Truck,
  BarChart3,
  FileText,
  Bot,
  Settings,
} as const;

const navItems = [
  { label: "Dashboard", path: "/dashboard", icon: "LayoutDashboard" as const },
  { label: "Inventory", path: "/inventory", icon: "Package" as const },
  { label: "Decisions", path: "/decisions", icon: "Brain" as const },
  { label: "Deliveries", path: "/deliveries", icon: "Truck" as const },
  { label: "Analytics", path: "/analytics", icon: "BarChart3" as const },
  { label: "Reports", path: "/reports", icon: "FileText" as const },
  { label: "Agents", path: "/agents", icon: "Bot" as const },
  { label: "Settings", path: "/settings", icon: "Settings" as const },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const location = useLocation();

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 72 : 240 }}
      transition={{ duration: 0.25, ease: "easeInOut" }}
      className="fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-slate-200 bg-white/95 backdrop-blur-xl"
    >
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b border-slate-200 px-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-fuchsia-600 shadow-md shadow-violet-500/25">
          <Bot className="h-5 w-5 text-white" />
        </div>
        <AnimatePresence>
          {!collapsed && (
            <motion.span
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: "auto" }}
              exit={{ opacity: 0, width: 0 }}
              className="overflow-hidden whitespace-nowrap text-[15px] font-bold tracking-tight text-slate-900"
            >
              AgenticInventory
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      {/* Nav Items */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {navItems.map((item) => {
          const Icon = icons[item.icon];
          const isActive = location.pathname.startsWith(item.path);

          return (
            <NavLink key={item.path} to={item.path}>
              <motion.div
                className={cn(
                  "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                  isActive
                    ? "text-violet-700"
                    : "text-slate-500 hover:text-slate-900"
                )}
                whileHover={{ x: 2 }}
              >
                {isActive && (
                  <motion.div
                    layoutId="sidebar-active"
                    className="absolute inset-0 rounded-xl bg-gradient-to-r from-violet-100 via-violet-50 to-fuchsia-50 border border-violet-200/80 shadow-sm shadow-violet-500/5"
                    transition={{ type: "spring", stiffness: 350, damping: 30 }}
                  />
                )}
                <Icon className="relative z-10 h-5 w-5 shrink-0" />
                <AnimatePresence>
                  {!collapsed && (
                    <motion.span
                      initial={{ opacity: 0, width: 0 }}
                      animate={{ opacity: 1, width: "auto" }}
                      exit={{ opacity: 0, width: 0 }}
                      className="relative z-10 overflow-hidden whitespace-nowrap"
                    >
                      {item.label}
                    </motion.span>
                  )}
                </AnimatePresence>
              </motion.div>
            </NavLink>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={onToggle}
        className="flex h-12 items-center justify-center border-t border-slate-200 text-slate-400 hover:text-violet-600 hover:bg-violet-50 transition-colors"
      >
        {collapsed ? (
          <ChevronRight className="h-4 w-4" />
        ) : (
          <ChevronLeft className="h-4 w-4" />
        )}
      </button>
    </motion.aside>
  );
}
