import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "@/services/api";
import { wsClient } from "@/services/socket";
import { queryKeys } from "@/services/queryKeys";
import type { DashboardMetrics } from "@/types/report";

export interface InventoryStats {
  total_items: number;
  total_value: number;
  low_stock_count: number;
  out_of_stock_count: number;
  categories: number;
  healthy_count: number;
}

export function useKPIMetrics() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["inventory", "stats"],
    queryFn: () => api.get<InventoryStats>("/inventory/stats"),
    refetchInterval: 60_000,
  });

  // Re-fetch stats on real-time inventory changes
  useEffect(() => {
    const unsub = wsClient.subscribe((event) => {
      if (
        event === "inventory:update" ||
        event === "inventory:batch_update"
      ) {
        queryClient.invalidateQueries({ queryKey: ["inventory", "stats"] });
      }
    });
    return unsub;
  }, [queryClient]);

  return query;
}

export function useDashboardMetrics() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: queryKeys.reports.dashboard,
    queryFn: () => api.get<DashboardMetrics>("/reports/dashboard"),
    refetchInterval: 30_000,
  });

  useEffect(() => {
    const unsub = wsClient.subscribe((event) => {
      if (
        event === "kpi:update" ||
        event === "decision:created" ||
        event === "order:created" ||
        event === "delivery:updated"
      ) {
        queryClient.invalidateQueries({ queryKey: queryKeys.reports.dashboard });
      }
    });
    return unsub;
  }, [queryClient]);

  return query;
}

export function useTrendData(days: number = 7) {
  return useQuery({
    queryKey: ["reports", "trends", days],
    queryFn: () => api.get<Record<string, unknown>[]>(`/reports/trends?days=${days}`),
    refetchInterval: 120_000,
  });
}

export function useSupplierPerformance() {
  return useQuery({
    queryKey: ["reports", "suppliers"],
    queryFn: () =>
      api.get<{ supplier: string; orders: number; value: number; success_rate: number }[]>(
        "/reports/suppliers"
      ),
    refetchInterval: 120_000,
  });
}

export function useAgentActivity() {
  return useQuery({
    queryKey: ["reports", "agents"],
    queryFn: () => api.get<{ agent: string; count: number }[]>("/reports/agents"),
    refetchInterval: 120_000,
  });
}
