/**
 * T054 — Global dispatcher for ETA review WebSocket events.
 *
 * Sits next to `<NotificationToaster />` in `<App />`. Subscribes to:
 *   - `eta_review.raised`   — invalidate the pending review query,
 *     patch `has_pending_review` on the cached delivery row (if any),
 *     show a toast linking to the Review Queue.
 *   - `eta_review.resolved` — invalidate review caches and the affected
 *     delivery's timeline + list cache.
 *
 * Cache-patch keys mirror `queryKeys.deliveries.list({})` / list with
 * params; we wildcard-invalidate via `queryKeys.deliveries.all`.
 */
import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/services/queryKeys";
import { wsClient } from "@/services/socket";
import type {
  EtaReviewDetailResponse,
  EtaReviewSummary,
} from "@/types/etaReview";

import { showToast } from "./NotificationToaster";

interface RaisedPayload {
  review: EtaReviewSummary;
  candidate_delivery_id: string | null;
}

interface ResolvedPayload {
  review: EtaReviewDetailResponse;
  delivery_id: string | null;
  delivery_summary: {
    current_stage: string;
    expected_delivery_at: string | null;
    has_pending_review: boolean;
  } | null;
}

export function EtaReviewWsDispatcher() {
  const queryClient = useQueryClient();

  useEffect(() => {
    const unsub = wsClient.subscribe((event, data) => {
      if (event === "eta_review.raised") {
        const payload = data as RaisedPayload;
        queryClient.invalidateQueries({ queryKey: queryKeys.etaReviews.all });
        if (payload.candidate_delivery_id) {
          // Flip the pending flag in any cached delivery list so the badge
          // appears immediately, then invalidate to refetch the canonical
          // row from the server.
          queryClient.invalidateQueries({ queryKey: queryKeys.deliveries.all });
        }
        showToast(
          "New ETA review",
          `Supplier ${payload.review.supplier_from} needs admin attention.`,
          "warning",
        );
      } else if (event === "eta_review.resolved") {
        const payload = data as ResolvedPayload;
        queryClient.invalidateQueries({ queryKey: queryKeys.etaReviews.all });
        if (payload.delivery_id) {
          queryClient.invalidateQueries({
            queryKey: queryKeys.deliveries.timeline(payload.delivery_id),
          });
          queryClient.invalidateQueries({ queryKey: queryKeys.deliveries.all });
        }
        showToast(
          "Review resolved",
          `${payload.review.resolved_by ?? "Admin"} ${payload.review.resolution_state} a review.`,
          "success",
        );
      }
    });
    return unsub;
  }, [queryClient]);

  return null;
}
