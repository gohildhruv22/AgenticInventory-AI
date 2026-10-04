import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { api } from "@/services/api";
import { queryKeys } from "@/services/queryKeys";
import { wsClient } from "@/services/socket";
import type { DeliveryTimelineResponse } from "@/types/delivery";

interface UseDeliveryTimelineOptions {
  /** Only fetch entries with `occurred_at > since` for incremental refresh. */
  since?: string | null;
  limit?: number;
  enabled?: boolean;
}

/**
 * Fetches the append-only timeline for a single delivery via
 * `GET /api/v1/deliveries/{id}/timeline` (T036).
 *
 * Subscribes to the `delivery.timeline.appended` WS event for this
 * delivery and invalidates the query when a matching event arrives so
 * the open panel grows without manual polling (T043 — partial wiring).
 */
export function useDeliveryTimeline(
  deliveryId: string | null | undefined,
  opts: UseDeliveryTimelineOptions = {}
) {
  const queryClient = useQueryClient();
  const { since, limit, enabled = true } = opts;

  const qs = new URLSearchParams();
  if (since) qs.set("since", since);
  if (typeof limit === "number") qs.set("limit", String(limit));
  const search = qs.toString();

  const query = useQuery({
    queryKey: queryKeys.deliveries.timeline(deliveryId ?? ""),
    enabled: Boolean(deliveryId) && enabled,
    queryFn: () =>
      api.get<DeliveryTimelineResponse>(
        `/deliveries/${deliveryId}/timeline${search ? `?${search}` : ""}`
      ),
  });

  useEffect(() => {
    if (!deliveryId) return undefined;
    const unsub = wsClient.subscribe((event, payload) => {
      if (event !== "delivery.timeline.appended") return;
      const evDeliveryId =
        (payload as { delivery_id?: string } | null)?.delivery_id ?? null;
      if (evDeliveryId && evDeliveryId !== deliveryId) return;
      queryClient.invalidateQueries({
        queryKey: queryKeys.deliveries.timeline(deliveryId),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.deliveries.all });
    });
    return unsub;
  }, [deliveryId, queryClient]);

  return query;
}
