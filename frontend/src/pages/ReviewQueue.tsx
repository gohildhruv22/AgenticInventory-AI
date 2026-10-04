/**
 * T052 — `<ReviewQueue />` page listing `<ReviewItemCard />` items.
 *
 * State filter tabs: pending / approved / corrected / dismissed / all.
 * Paginated via the `per_page` query parameter.
 */
import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Inbox, Loader2 } from "lucide-react";

import { ReviewItemCard } from "@/components/deliveries/ReviewItemCard";
import { useEtaReviews } from "@/hooks/useEtaReviews";
import type { ReviewStateFilter } from "@/types/etaReview";

const TABS: { key: ReviewStateFilter; label: string }[] = [
  { key: "pending", label: "Pending" },
  { key: "approved", label: "Approved" },
  { key: "corrected", label: "Corrected" },
  { key: "dismissed", label: "Dismissed" },
  { key: "all", label: "All" },
];

const PER_PAGE = 25;

export default function ReviewQueue() {
  const [tab, setTab] = useState<ReviewStateFilter>("pending");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const { data, isLoading, isError, error } = useEtaReviews(tab, {
    page,
    perPage: PER_PAGE,
  });

  const items = data?.items ?? [];
  const totalPages = data?.pages ?? 0;

  return (
    <div className="space-y-6 p-1">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold text-slate-100">ETA Review Queue</h1>
        <p className="text-sm text-slate-400">
          Supplier replies the agent could not auto-apply — approve, correct,
          or dismiss each item.
        </p>
      </header>

      <div className="flex flex-wrap gap-2">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            data-testid={`review-tab-${key}`}
            onClick={() => {
              setTab(key);
              setPage(1);
            }}
            className={
              tab === key
                ? "rounded-full bg-sky-500 px-3 py-1 text-xs font-semibold text-white"
                : "rounded-full border border-slate-600 bg-slate-800/40 px-3 py-1 text-xs text-slate-300 hover:bg-slate-700/40"
            }
          >
            {label}
          </button>
        ))}
      </div>

      <div className="rounded-xl border border-slate-200/10 bg-white/95 p-4">
        {isLoading ? (
          <div className="flex items-center gap-2 py-12 text-sm text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading reviews…
          </div>
        ) : isError ? (
          <div className="py-12 text-sm text-rose-600">
            Failed to load reviews: {(error as Error)?.message ?? "unknown error"}
          </div>
        ) : items.length === 0 ? (
          <div
            className="flex flex-col items-center gap-2 py-12 text-sm text-slate-500"
            data-testid="review-empty"
          >
            <Inbox className="h-6 w-6" />
            <p>No reviews in this state.</p>
          </div>
        ) : (
          <ul className="space-y-3">
            <AnimatePresence initial={false}>
              {items.map((review) => (
                <motion.li key={review.id} layout>
                  <ReviewItemCard
                    review={review}
                    expanded={expandedId === review.id}
                    onToggle={() =>
                      setExpandedId((id) => (id === review.id ? null : review.id))
                    }
                  />
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        )}

        {totalPages > 1 ? (
          <div className="mt-4 flex items-center justify-between text-xs text-slate-500">
            <span>
              Page {page} of {totalPages} · {data?.total ?? 0} total
            </span>
            <div className="flex gap-1">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="rounded-md border border-slate-300 p-1 disabled:opacity-50"
                aria-label="Previous page"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="rounded-md border border-slate-300 p-1 disabled:opacity-50"
                aria-label="Next page"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
