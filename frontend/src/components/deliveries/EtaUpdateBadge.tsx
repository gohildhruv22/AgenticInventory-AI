import { Bell, AlertCircle } from "lucide-react";

interface EtaUpdateBadgeProps {
  /** Total timeline entries on this delivery. */
  entryCount?: number;
  /** Entries appended since the row was last viewed. */
  unreadCount?: number;
  /** When true, render the red-dot variant (FR-009). */
  hasPendingReview?: boolean;
}

/**
 * Tiny pill summarising activity on a delivery row.
 *
 *   - When ``hasPendingReview``: red-dot variant; clicking the row should
 *     open the review queue / timeline.
 *   - Otherwise renders the number of unread updates.
 */
export function EtaUpdateBadge({
  entryCount = 0,
  unreadCount = 0,
  hasPendingReview = false,
}: EtaUpdateBadgeProps) {
  if (hasPendingReview) {
    return (
      <span
        data-testid="eta-update-badge-review"
        title="Pending review"
        className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-[11px] font-semibold text-rose-700"
      >
        <span className="relative inline-flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-rose-400 opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-rose-500" />
        </span>
        <AlertCircle className="h-3 w-3" />
        Review
      </span>
    );
  }

  if (unreadCount > 0) {
    return (
      <span
        data-testid="eta-update-badge-unread"
        title={`${unreadCount} new updates`}
        className="inline-flex items-center gap-1 rounded-full bg-sky-50 px-2 py-0.5 text-[11px] font-semibold text-sky-700"
      >
        <Bell className="h-3 w-3" />
        {unreadCount}
      </span>
    );
  }

  if (entryCount > 0) {
    return (
      <span
        data-testid="eta-update-badge-count"
        title={`${entryCount} timeline entries`}
        className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600"
      >
        {entryCount}
      </span>
    );
  }

  return null;
}

export default EtaUpdateBadge;
