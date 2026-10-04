/**
 * T050 — Hooks for the ETA Review Queue (US3).
 *
 * - `useEtaReviews(state)` — paginated list of reviews.
 * - `useResolveEtaReview()` — approve / correct / dismiss mutation.
 *
 * Both subscribe to the `eta_review.raised` and `eta_review.resolved` WS
 * events and invalidate the review caches in the dispatcher (T054 wires
 * a more global handler; the hook keeps the queue page responsive on its
 * own).
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect } from "react";

import { api } from "@/services/api";
import { queryKeys } from "@/services/queryKeys";
import { wsClient } from "@/services/socket";
import type {
  EtaReviewCorrectRequest,
  EtaReviewDetailResponse,
  EtaReviewDismissRequest,
  EtaReviewListResponse,
  ReviewStateFilter,
} from "@/types/etaReview";

interface UseEtaReviewsOptions {
  page?: number;
  perPage?: number;
  enabled?: boolean;
}

export function useEtaReviews(
  state: ReviewStateFilter = "pending",
  opts: UseEtaReviewsOptions = {},
) {
  const queryClient = useQueryClient();
  const { page = 1, perPage = 25, enabled = true } = opts;

  const qs = new URLSearchParams();
  qs.set("state", state);
  qs.set("page", String(page));
  qs.set("per_page", String(perPage));

  const query = useQuery({
    queryKey: [...queryKeys.etaReviews.list(state), page, perPage] as const,
    enabled,
    queryFn: () =>
      api.get<EtaReviewListResponse>(`/eta-reviews?${qs.toString()}`),
  });

  useEffect(() => {
    const unsub = wsClient.subscribe((event) => {
      if (event === "eta_review.raised" || event === "eta_review.resolved") {
        queryClient.invalidateQueries({ queryKey: queryKeys.etaReviews.all });
      }
    });
    return unsub;
  }, [queryClient]);

  return query;
}

export function useEtaReview(reviewId: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.etaReviews.detail(reviewId ?? ""),
    enabled: Boolean(reviewId),
    queryFn: () =>
      api.get<EtaReviewDetailResponse>(`/eta-reviews/${reviewId}`),
  });
}

type ResolveAction =
  | { kind: "approve"; reviewId: string }
  | { kind: "correct"; reviewId: string; payload: EtaReviewCorrectRequest }
  | { kind: "dismiss"; reviewId: string; payload?: EtaReviewDismissRequest };

export function useResolveEtaReview() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (action: ResolveAction) => {
      switch (action.kind) {
        case "approve":
          return api.post<EtaReviewDetailResponse>(
            `/eta-reviews/${action.reviewId}/approve`,
            {},
          );
        case "correct":
          return api.post<EtaReviewDetailResponse>(
            `/eta-reviews/${action.reviewId}/correct`,
            action.payload,
          );
        case "dismiss":
          return api.post<EtaReviewDetailResponse>(
            `/eta-reviews/${action.reviewId}/dismiss`,
            action.payload ?? {},
          );
      }
    },
    onSuccess: (detail) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.etaReviews.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.etaReviews.detail(detail.id),
      });
      // The resolution may have mutated a delivery — refresh the
      // delivery list and its timeline so the Deliveries page stays
      // consistent.
      queryClient.invalidateQueries({ queryKey: queryKeys.deliveries.all });
      if (detail.candidate_delivery_id) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.deliveries.timeline(detail.candidate_delivery_id),
        });
      }
    },
  });
}
