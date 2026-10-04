import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "@/services/api";
import { queryKeys } from "@/services/queryKeys";
import { useInventoryStore } from "@/stores/inventoryStore";
import { wsClient } from "@/services/socket";
import type {
  InventoryItem,
  InventoryListResponse,
  InventoryItemCreate,
  InventoryItemUpdate,
} from "@/types/inventory";

interface UseInventoryParams {
  page?: number;
  per_page?: number;
  category?: string | null;
  status?: string | null;
  search?: string | null;
  sort_by?: string;
  sort_order?: string;
}

export function useInventory(params: UseInventoryParams = {}) {
  const queryClient = useQueryClient();
  const setItems = useInventoryStore((s) => s.setItems);

  const queryParams: Record<string, unknown> = {};
  if (params.page) queryParams.page = params.page;
  if (params.per_page) queryParams.per_page = params.per_page;
  if (params.category) queryParams.category = params.category;
  if (params.status) queryParams.status = params.status;
  if (params.search) queryParams.search = params.search;
  if (params.sort_by) queryParams.sort_by = params.sort_by;
  if (params.sort_order) queryParams.sort_order = params.sort_order;

  const qs = new URLSearchParams(
    Object.entries(queryParams).map(([k, v]) => [k, String(v)])
  ).toString();

  const query = useQuery({
    queryKey: queryKeys.inventory.list(queryParams),
    queryFn: () => api.get<InventoryListResponse>(`/inventory${qs ? `?${qs}` : ""}`),
  });

  // Sync fetched items to Zustand store
  useEffect(() => {
    if (query.data?.items) {
      setItems(query.data.items);
    }
  }, [query.data, setItems]);

  // Subscribe to real-time inventory updates
  useEffect(() => {
    const unsub = wsClient.subscribe((event) => {
      if (event === "inventory:update" || event === "inventory:batch_update") {
        queryClient.invalidateQueries({ queryKey: queryKeys.inventory.all });
      }
    });
    return unsub;
  }, [queryClient]);

  const createMutation = useMutation({
    mutationFn: (data: InventoryItemCreate) =>
      api.post<InventoryItem>("/inventory", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.inventory.all });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: InventoryItemUpdate }) =>
      api.patch<InventoryItem>(`/inventory/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.inventory.all });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/inventory/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.inventory.all });
    },
  });

  return {
    ...query,
    items: query.data?.items ?? [],
    total: query.data?.total ?? 0,
    pages: query.data?.pages ?? 0,
    createItem: createMutation.mutateAsync,
    updateItem: updateMutation.mutateAsync,
    deleteItem: deleteMutation.mutateAsync,
    isCreating: createMutation.isPending,
    isUpdating: updateMutation.isPending,
    isDeleting: deleteMutation.isPending,
  };
}

export function useCategories() {
  return useQuery({
    queryKey: ["inventory", "categories"],
    queryFn: () => api.get<string[]>("/inventory/categories"),
  });
}

export function useLowStockItems() {
  return useQuery({
    queryKey: ["inventory", "low-stock"],
    queryFn: () => api.get<InventoryItem[]>("/inventory/low-stock"),
    refetchInterval: 30_000,
  });
}
