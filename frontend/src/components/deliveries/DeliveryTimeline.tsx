import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  CheckCircle2,
  CalendarClock,
  MessageSquare,
  AlertTriangle,
  PackageCheck,
  UserCog,
  StickyNote,
  ChevronDown,
  ChevronUp,
  Loader2,
} from "lucide-react";

import { useDeliveryTimeline } from "@/hooks/useDeliveryTimeline";
import type {
  DeliveryTimelineEntry,
  DeliveryTimelineEventType,
} from "@/types/delivery";

interface DeliveryTimelineProps {
  deliveryId: string;
  /** When false, the hook is paused (used when row is collapsed). */
  enabled?: boolean;
}

const EVENT_META: Record<
  DeliveryTimelineEventType,
  { label: string; Icon: typeof CheckCircle2; tone: string }
> = {
  eta_confirmed: {
    label: "ETA confirmed",
    Icon: CheckCircle2,
    tone: "text-emerald-600 bg-emerald-50",
  },
  eta_revised: {
    label: "ETA revised",
    Icon: CalendarClock,
    tone: "text-amber-700 bg-amber-50",
  },
  acknowledged: {
    label: "Acknowledged",
    Icon: MessageSquare,
    tone: "text-sky-700 bg-sky-50",
  },
  at_risk: {
    label: "At risk",
    Icon: AlertTriangle,
    tone: "text-rose-700 bg-rose-50",
  },
  delivered: {
    label: "Delivered",
    Icon: PackageCheck,
    tone: "text-emerald-700 bg-emerald-50",
  },
  manual_override: {
    label: "Manual override",
    Icon: UserCog,
    tone: "text-violet-700 bg-violet-50",
  },
  note: {
    label: "Note",
    Icon: StickyNote,
    tone: "text-slate-700 bg-slate-100",
  },
};

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function ExcerptBlock({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const showToggle = text.length > 180;
  return (
    <div className="text-sm text-slate-700">
      <p
        className={
          expanded || !showToggle
            ? "whitespace-pre-line"
            : "line-clamp-2 whitespace-pre-line"
        }
      >
        {text}
      </p>
      {showToggle ? (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-sky-600 hover:underline"
        >
          {expanded ? (
            <>
              <ChevronUp className="h-3 w-3" /> Show less
            </>
          ) : (
            <>
              <ChevronDown className="h-3 w-3" /> Show more
            </>
          )}
        </button>
      ) : null}
    </div>
  );
}

function TimelineRow({ entry }: { entry: DeliveryTimelineEntry }) {
  const meta = EVENT_META[entry.event_type] ?? EVENT_META.note;
  const { Icon } = meta;
  return (
    <li
      data-testid={`timeline-row-${entry.event_type}`}
      className="relative flex gap-3 pb-4"
    >
      <span
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${meta.tone}`}
      >
        <Icon className="h-4 w-4" />
      </span>
      <div className="flex-1 rounded-md border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-900">
              {meta.label}
            </span>
            {entry.confidence != null ? (
              <span
                data-testid="timeline-confidence-badge"
                className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700"
              >
                {Math.round(Number(entry.confidence))}%
              </span>
            ) : null}
          </div>
          <time
            className="text-xs text-slate-500"
            dateTime={entry.occurred_at}
          >
            {formatDateTime(entry.occurred_at)}
          </time>
        </div>
        {entry.parsed_date ? (
          <p
            className="mt-1 text-xs text-slate-600"
            data-testid="timeline-parsed-date"
          >
            New expected date:{" "}
            <span className="font-medium text-slate-800">
              {formatDateTime(entry.parsed_date)}
            </span>
          </p>
        ) : null}
        {entry.supplier_excerpt ? (
          <div className="mt-2" data-testid="timeline-supplier-excerpt">
            <ExcerptBlock text={entry.supplier_excerpt} />
          </div>
        ) : null}
        {entry.note ? (
          <p className="mt-2 text-xs italic text-slate-600">{entry.note}</p>
        ) : null}
        <p className="mt-2 text-[11px] uppercase tracking-wide text-slate-400">
          {entry.actor_type}
          {entry.actor_id ? ` · ${entry.actor_id}` : ""}
        </p>
      </div>
    </li>
  );
}

export function DeliveryTimeline({
  deliveryId,
  enabled = true,
}: DeliveryTimelineProps) {
  const { data, isLoading, isError, error } = useDeliveryTimeline(deliveryId, {
    enabled,
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-2 py-4 text-sm text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading timeline…
      </div>
    );
  }
  if (isError) {
    return (
      <div className="px-2 py-4 text-sm text-rose-600">
        Failed to load timeline: {(error as Error)?.message ?? "unknown error"}
      </div>
    );
  }

  const entries = data?.entries ?? [];

  if (entries.length === 0) {
    return (
      <p
        className="px-2 py-4 text-sm italic text-slate-500"
        data-testid="timeline-empty"
      >
        No timeline entries yet.
      </p>
    );
  }

  return (
    <AnimatePresence initial={false}>
      <motion.ol
        key="timeline"
        initial={{ opacity: 0, height: 0 }}
        animate={{ opacity: 1, height: "auto" }}
        exit={{ opacity: 0, height: 0 }}
        transition={{ duration: 0.2 }}
        className="relative list-none border-l border-slate-200 pl-2"
        data-testid="delivery-timeline"
      >
        {entries.map((entry) => (
          <TimelineRow key={entry.id} entry={entry} />
        ))}
      </motion.ol>
    </AnimatePresence>
  );
}

export default DeliveryTimeline;
