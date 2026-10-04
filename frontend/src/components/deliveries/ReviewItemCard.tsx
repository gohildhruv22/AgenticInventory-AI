/**
 * T051 — `<ReviewItemCard />` for a single ETA review item.
 *
 * Shows the supplier excerpt, agent reasoning, agent intent + confidence,
 * candidate delivery summary, and three actions: Approve / Correct (opens
 * an inline form with delivery picker + date picker) / Dismiss (opens an
 * optional note input).
 *
 * Light-theme palette to match the existing Review Queue surface
 * (constitution carve-out — see plan.md complexity tracking).
 */
import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Calendar,
  Check,
  CheckCircle2,
  Clock,
  Edit3,
  MailQuestion,
  MessageSquare,
  PackageX,
  ShieldCheck,
  Sparkles,
  X,
  XCircle,
} from "lucide-react";

import { useResolveEtaReview } from "@/hooks/useEtaReviews";
import type {
  CorrectIntent,
  EtaIntent,
  EtaReviewDetailResponse,
  EtaReviewSummary,
  RaisedReason,
  ResolutionState,
} from "@/types/etaReview";

interface ReviewItemCardProps {
  review: EtaReviewSummary | EtaReviewDetailResponse;
  /** Detail flag — when true, full reasoning/order ids are visible. */
  expanded?: boolean;
  onToggle?: () => void;
}

const RAISED_REASON_LABEL: Record<RaisedReason, string> = {
  low_confidence: "Low confidence",
  unmatched_order: "Unmatched order",
  ambiguous_match: "Ambiguous match",
  negative_intent: "Negative intent",
  past_date: "Past date",
  non_english: "Non-English",
};

const INTENT_META: Record<
  EtaIntent,
  { label: string; tone: string; Icon: typeof CheckCircle2 }
> = {
  confirm: { label: "Confirm", tone: "bg-emerald-50 text-emerald-700", Icon: CheckCircle2 },
  delay: { label: "Delay", tone: "bg-amber-50 text-amber-700", Icon: Clock },
  cancel: { label: "Cancel", tone: "bg-rose-50 text-rose-700", Icon: PackageX },
  acknowledge: { label: "Acknowledge", tone: "bg-sky-50 text-sky-700", Icon: MessageSquare },
  unclear: { label: "Unclear", tone: "bg-slate-100 text-slate-700", Icon: MailQuestion },
};

const STATE_META: Record<
  ResolutionState,
  { label: string; tone: string; Icon: typeof CheckCircle2 }
> = {
  pending: { label: "Pending", tone: "bg-amber-100 text-amber-800", Icon: AlertTriangle },
  approved: { label: "Approved", tone: "bg-emerald-100 text-emerald-800", Icon: ShieldCheck },
  corrected: { label: "Corrected", tone: "bg-violet-100 text-violet-800", Icon: Edit3 },
  dismissed: { label: "Dismissed", tone: "bg-slate-200 text-slate-700", Icon: XCircle },
};

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function toIsoLocalInput(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function ReviewItemCard({
  review,
  expanded = false,
  onToggle,
}: ReviewItemCardProps) {
  const resolve = useResolveEtaReview();
  const [mode, setMode] = useState<"idle" | "correct" | "dismiss">("idle");
  const [error, setError] = useState<string | null>(null);

  // Correct form state.
  const [correctDeliveryId, setCorrectDeliveryId] = useState(
    review.candidate_delivery_id ?? "",
  );
  const [correctDate, setCorrectDate] = useState(
    toIsoLocalInput(review.agent_parsed_date),
  );
  const [correctIntent, setCorrectIntent] = useState<CorrectIntent>(
    review.agent_intent === "unclear" ? "confirm" : (review.agent_intent as CorrectIntent),
  );
  const [correctNote, setCorrectNote] = useState("");

  // Dismiss form state.
  const [dismissNote, setDismissNote] = useState("");

  const isPending = review.resolution_state === "pending";
  const intent = INTENT_META[review.agent_intent];
  const state = STATE_META[review.resolution_state];

  const submitApprove = async () => {
    setError(null);
    try {
      await resolve.mutateAsync({ kind: "approve", reviewId: review.id });
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const submitCorrect = async () => {
    setError(null);
    if (!correctDeliveryId || !correctDate) {
      setError("Delivery and parsed date are required.");
      return;
    }
    try {
      await resolve.mutateAsync({
        kind: "correct",
        reviewId: review.id,
        payload: {
          delivery_id: correctDeliveryId,
          parsed_date: new Date(correctDate).toISOString(),
          intent: correctIntent,
          note: correctNote || undefined,
        },
      });
      setMode("idle");
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const submitDismiss = async () => {
    setError(null);
    try {
      await resolve.mutateAsync({
        kind: "dismiss",
        reviewId: review.id,
        payload: dismissNote ? { note: dismissNote } : undefined,
      });
      setMode("idle");
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const detail = "agent_reasoning" in review ? review : null;

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.18 }}
      data-testid={`review-card-${review.resolution_state}`}
      className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className={`flex h-9 w-9 items-center justify-center rounded-full ${intent.tone}`}>
            <intent.Icon className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-slate-900">
                {review.supplier_from}
              </h3>
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${state.tone}`}
                data-testid="review-state-badge"
              >
                <state.Icon className="h-3 w-3" /> {state.label}
              </span>
            </div>
            <p className="mt-0.5 text-xs text-slate-500">
              Raised {formatDate(review.raised_at)} · {RAISED_REASON_LABEL[review.raised_reason]}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5">
            <Sparkles className="h-3 w-3" />
            {Math.round(review.agent_confidence)}%
          </span>
          {onToggle ? (
            <button
              type="button"
              onClick={onToggle}
              className="rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
            >
              {expanded ? "Collapse" : "Details"}
            </button>
          ) : null}
        </div>
      </header>

      <div className="mt-3 rounded-md bg-slate-50 p-3 text-sm text-slate-700">
        <p className="line-clamp-3 whitespace-pre-line">
          {review.supplier_reply_excerpt || "(no excerpt)"}
        </p>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-3 text-xs">
        <div>
          <dt className="font-medium text-slate-500">Agent intent</dt>
          <dd className="text-slate-800">{intent.label}</dd>
        </div>
        <div>
          <dt className="font-medium text-slate-500">Proposed date</dt>
          <dd className="text-slate-800">
            {review.agent_parsed_date ? formatDate(review.agent_parsed_date) : "—"}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-slate-500">Candidate delivery</dt>
          <dd className="text-slate-800 break-all">
            {review.candidate_delivery_id ?? "(unmatched)"}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-slate-500">Subject</dt>
          <dd className="text-slate-800">
            {detail?.supplier_reply?.subject ?? "—"}
          </dd>
        </div>
      </dl>

      {expanded && detail ? (
        <div className="mt-3 rounded-md border border-slate-200 bg-slate-50/60 p-3 text-xs text-slate-700">
          <p className="font-medium text-slate-600">Agent reasoning</p>
          <p className="mt-1 whitespace-pre-line">{detail.agent_reasoning}</p>
          {detail.candidate_order_ids.length ? (
            <p className="mt-2 text-[11px] text-slate-500">
              Order IDs:{" "}
              <span className="break-all">
                {detail.candidate_order_ids.join(", ")}
              </span>
            </p>
          ) : null}
        </div>
      ) : null}

      {isPending ? (
        <>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button
              type="button"
              data-testid="review-approve-btn"
              onClick={submitApprove}
              disabled={resolve.isPending}
              className="inline-flex items-center gap-1 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              <Check className="h-3 w-3" /> Approve
            </button>
            <button
              type="button"
              data-testid="review-correct-btn"
              onClick={() => setMode(mode === "correct" ? "idle" : "correct")}
              disabled={resolve.isPending}
              className="inline-flex items-center gap-1 rounded-md border border-violet-300 bg-violet-50 px-3 py-1.5 text-xs font-medium text-violet-700 hover:bg-violet-100 disabled:opacity-50"
            >
              <Edit3 className="h-3 w-3" /> Correct
            </button>
            <button
              type="button"
              data-testid="review-dismiss-btn"
              onClick={() => setMode(mode === "dismiss" ? "idle" : "dismiss")}
              disabled={resolve.isPending}
              className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              <X className="h-3 w-3" /> Dismiss
            </button>
          </div>

          <AnimatePresence>
            {mode === "correct" ? (
              <motion.div
                key="correct"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-3 space-y-2 rounded-md border border-violet-200 bg-violet-50/40 p-3 text-xs"
                data-testid="review-correct-form"
              >
                <label className="block">
                  <span className="font-medium text-slate-600">Delivery ID</span>
                  <input
                    type="text"
                    value={correctDeliveryId}
                    onChange={(e) => setCorrectDeliveryId(e.target.value)}
                    placeholder="00000000-0000-..."
                    className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-xs"
                  />
                </label>
                <label className="block">
                  <span className="font-medium text-slate-600 inline-flex items-center gap-1">
                    <Calendar className="h-3 w-3" /> Parsed date
                  </span>
                  <input
                    type="datetime-local"
                    value={correctDate}
                    onChange={(e) => setCorrectDate(e.target.value)}
                    className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-xs"
                  />
                </label>
                <label className="block">
                  <span className="font-medium text-slate-600">Intent</span>
                  <select
                    value={correctIntent}
                    onChange={(e) =>
                      setCorrectIntent(e.target.value as CorrectIntent)
                    }
                    className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-xs"
                  >
                    <option value="confirm">confirm</option>
                    <option value="delay">delay</option>
                    <option value="acknowledge">acknowledge</option>
                  </select>
                </label>
                <label className="block">
                  <span className="font-medium text-slate-600">Note (optional)</span>
                  <textarea
                    rows={2}
                    value={correctNote}
                    onChange={(e) => setCorrectNote(e.target.value)}
                    className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-xs"
                  />
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={submitCorrect}
                    disabled={resolve.isPending}
                    className="rounded-md bg-violet-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-violet-700 disabled:opacity-50"
                  >
                    Save correction
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode("idle")}
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                </div>
              </motion.div>
            ) : null}
            {mode === "dismiss" ? (
              <motion.div
                key="dismiss"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-3 space-y-2 rounded-md border border-slate-200 bg-slate-50/60 p-3 text-xs"
                data-testid="review-dismiss-form"
              >
                <label className="block">
                  <span className="font-medium text-slate-600">
                    Note (optional)
                  </span>
                  <textarea
                    rows={2}
                    value={dismissNote}
                    onChange={(e) => setDismissNote(e.target.value)}
                    placeholder="Why are you dismissing this?"
                    className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-xs"
                  />
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={submitDismiss}
                    disabled={resolve.isPending}
                    className="rounded-md bg-slate-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-50"
                  >
                    Dismiss
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode("idle")}
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                </div>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </>
      ) : (
        <div
          className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600"
          data-testid="review-resolved-meta"
        >
          Resolved by{" "}
          <span className="font-medium text-slate-800">
            {(review as EtaReviewDetailResponse).resolved_by ?? "—"}
          </span>{" "}
          on{" "}
          <span className="font-medium text-slate-800">
            {formatDate((review as EtaReviewDetailResponse).resolved_at ?? null)}
          </span>
        </div>
      )}

      {error ? (
        <p className="mt-2 text-xs text-rose-600" role="alert">
          {error}
        </p>
      ) : null}
    </motion.article>
  );
}
