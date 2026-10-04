import { useEffect, useCallback, useState } from "react";
import { useQueryClient, useInfiniteQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { queryKeys } from "@/services/queryKeys";
import { wsClient } from "@/services/socket";
import { useAgentStore } from "@/stores/agentStore";
import type { AgentDecision, DecisionListResponse } from "@/types/agent";

interface DecisionFilters {
  agent_type?: string;
  status?: string;
  search?: string;
  [key: string]: unknown;
}

export function useAgentDecisions(filters: DecisionFilters = {}) {
  const queryClient = useQueryClient();
  const addDecision = useAgentStore((s) => s.addDecision);
  const [newDecisionIds, setNewDecisionIds] = useState<Set<string>>(new Set());

  const queryParams = new URLSearchParams();
  if (filters.agent_type) queryParams.set("agent_type", filters.agent_type);
  if (filters.status) queryParams.set("status", filters.status);

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    error,
  } = useInfiniteQuery<DecisionListResponse>({
    queryKey: queryKeys.decisions.list(filters),
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams(queryParams);
      params.set("page", String(pageParam));
      params.set("per_page", "20");
      return api.get<DecisionListResponse>(`/decisions?${params}`);
    },
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.pages ? lastPage.page + 1 : undefined,
  });

  // Flatten pages into a single list
  const decisions =
    data?.pages.flatMap((p) => p.decisions) ?? [];

  // Apply client-side search filter
  const filtered = filters.search
    ? decisions.filter((d) => {
        const q = filters.search!.toLowerCase();
        return (
          d.agent_type.toLowerCase().includes(q) ||
          d.action_type.toLowerCase().includes(q) ||
          (d.reasoning_trace.reasoning ?? "").toLowerCase().includes(q) ||
          (d.reasoning_trace.item_context?.name ?? "").toLowerCase().includes(q) ||
          (d.reasoning_trace.item_context?.sku ?? "").toLowerCase().includes(q)
        );
      })
    : decisions;

  const total = data?.pages[0]?.total ?? 0;

  // Subscribe to real-time decision events
  useEffect(() => {
    const unsub = wsClient.subscribe((event, payload) => {
      if (event === "decision:created" || event === "agent:decision") {
        const decision = payload as AgentDecision;
        addDecision(decision);
        setNewDecisionIds((prev) => new Set([...prev, decision.id]));
        // Invalidate cache so next fetch reflects new data
        queryClient.invalidateQueries({ queryKey: queryKeys.decisions.all });
        // Clear "new" highlight after 5 seconds
        setTimeout(() => {
          setNewDecisionIds((prev) => {
            const next = new Set(prev);
            next.delete(decision.id);
            return next;
          });
        }, 5000);
      }
      if (event === "decision:approved") {
        queryClient.invalidateQueries({ queryKey: queryKeys.decisions.all });
      }
    });
    return unsub;
  }, [addDecision, queryClient]);

  const approve = useCallback(
    async (decisionId: string) => {
      await api.post(`/decisions/${decisionId}/approve`);
      queryClient.invalidateQueries({ queryKey: queryKeys.decisions.all });
    },
    [queryClient]
  );

  const remove = useCallback(
    async (decisionId: string) => {
      await api.delete(`/decisions/${decisionId}`);
      queryClient.invalidateQueries({ queryKey: queryKeys.decisions.all });
    },
    [queryClient]
  );

  return {
    decisions: filtered,
    total,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    approve,
    remove,
    isNewDecision: (id: string) => newDecisionIds.has(id),
  };
}
