export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const WS_URL =
  import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws";

export const AGENT_TYPES = {
  inventory_monitor: "Inventory Monitor",
  demand_forecast: "Demand Forecast",
  decision_manager: "Decision Manager",
  supplier_email: "Supplier Email",
  delivery_tracker: "Delivery Tracker",
  undo_rollback: "Undo & Rollback",
  reporting_kpi: "Reporting & KPI",
} as const;

export type AgentType = keyof typeof AGENT_TYPES;

export const DELIVERY_STAGES = [
  "ordered",
  "confirmed",
  "in_transit",
  "out_for_delivery",
  "delivered",
  "partial_delivery",
  "failed",
] as const;

export type DeliveryStage = (typeof DELIVERY_STAGES)[number];

export const STATUS_COLORS = {
  normal: "text-emerald-400",
  low_stock: "text-amber-400",
  out_of_stock: "text-red-400",
  reorder_pending: "text-purple-400",
  executed: "text-emerald-400",
  pending_review: "text-amber-400",
  rolled_back: "text-slate-400",
  healthy: "text-emerald-400",
  degraded: "text-amber-400",
  unhealthy: "text-red-400",
  processing: "text-purple-400",
} as const;

export const NAV_ITEMS = [
  { label: "Dashboard", path: "/dashboard", icon: "LayoutDashboard" },
  { label: "Inventory", path: "/inventory", icon: "Package" },
  { label: "Decisions", path: "/decisions", icon: "Brain" },
  { label: "Deliveries", path: "/deliveries", icon: "Truck" },
  { label: "Analytics", path: "/analytics", icon: "BarChart3" },
  { label: "Reports", path: "/reports", icon: "FileText" },
  { label: "Agents", path: "/agents", icon: "Bot" },
  { label: "Settings", path: "/settings", icon: "Settings" },
] as const;
