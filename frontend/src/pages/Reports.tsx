import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  ChevronDown,
  Calendar,
  Mail,
  MailX,
  Loader2,
  Inbox,
  TrendingUp,
  ShoppingCart,
  Brain,
  Truck,
  RefreshCw,
  Eye,
  X,
  AlertTriangle,
  Lightbulb,
  Sparkles,
  Package,
  Send,
  CheckCircle2,
  CircleDollarSign,
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  AlertCircle,
} from "lucide-react";
import { fadeInUp, staggerChildren, pageTransition } from "@/lib/animations";
import { cn, formatCurrency, formatDate } from "@/lib/utils";
import { GlassCard } from "@/components/ui/GlassCard";
import { api } from "@/services/api";
import { queryKeys } from "@/services/queryKeys";
import type { KPIReport } from "@/types/report";

interface ReportListResponse {
  reports: KPIReport[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

interface SeedReportEntry {
  date: string;
  report_id: string;
  score?: number | null;
}

interface SeedFailure {
  date: string;
  error: string;
}

interface SeedResponse {
  status: string;
  created: SeedReportEntry[];
  skipped: string[];
  failed: SeedFailure[];
  total_created: number;
}

type Toast =
  | { kind: "success"; message: string }
  | { kind: "error"; message: string }
  | null;

export default function Reports() {
  const queryClient = useQueryClient();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detailReport, setDetailReport] = useState<KPIReport | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [generating, setGenerating] = useState(false);
  const [toast, setToast] = useState<Toast>(null);

  const params = new URLSearchParams();
  params.set("per_page", "30");
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);

  const { data, isLoading, refetch } = useQuery({
    queryKey: queryKeys.reports.list({ dateFrom, dateTo }),
    queryFn: () => api.get<ReportListResponse>(`/reports?${params}`),
  });

  const reports = data?.reports ?? [];

  const showToast = (t: Toast) => {
    setToast(t);
    if (t) window.setTimeout(() => setToast(null), 6000);
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setToast(null);
    try {
      // Backfill the last 7 days, regenerating any existing reports so each
      // day gets a fresh AI summary. This guarantees the user always has a
      // full week of insight-rich reports after one click.
      const res = await api.post<SeedResponse>(
        "/reports/seed-demo?days=7&refresh=true",
        {}
      );
      await queryClient.invalidateQueries({ queryKey: queryKeys.reports.all });
      await refetch();

      const created = res.total_created ?? 0;
      const failed = res.failed?.length ?? 0;

      if (created === 0 && failed > 0) {
        showToast({
          kind: "error",
          message: `Could not generate any reports. ${failed} day${failed === 1 ? "" : "s"} failed: ${
            res.failed[0]?.error ?? "unknown error"
          }`,
        });
      } else {
        const failedTag =
          failed > 0
            ? ` · ${failed} day${failed === 1 ? "" : "s"} failed`
            : "";
        showToast({
          kind: "success",
          message: `Generated ${created} daily report${created === 1 ? "" : "s"} for the last 7 days${failedTag}.`,
        });
      }
    } catch (e) {
      const msg =
        e instanceof Error
          ? e.message
          : "Failed to generate reports. Try again.";
      showToast({ kind: "error", message: msg });
    } finally {
      setGenerating(false);
    }
  };

  return (
    <motion.div
      variants={pageTransition}
      initial="initial"
      animate="animate"
      exit="exit"
      className="space-y-6"
    >
      {/* ─── Page Header ──────────────────────────────────── */}
      <motion.div variants={fadeInUp} className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Daily Reports</h1>
          <p className="mt-1 text-sm text-slate-500">
            Operations brief — orders, decisions, KPIs, and AI-generated insights for each day.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={handleGenerate}
            disabled={generating}
            className={cn(
              "group inline-flex items-center gap-2.5 rounded-xl border border-slate-200 bg-white py-1.5 pl-1.5 pr-4 text-sm font-semibold text-slate-900 shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition-all hover:border-violet-200 hover:shadow-[0_8px_24px_rgba(124,58,237,0.12)]",
              generating && "cursor-wait opacity-70"
            )}
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-sm shadow-violet-500/30 transition-transform group-hover:scale-105">
              {generating ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5" />
              )}
            </span>
            <span className="transition-colors group-hover:text-violet-700">
              {generating ? "Generating…" : "generate report"}
            </span>
          </motion.button>
        </div>
      </motion.div>

      {/* ─── Toast ────────────────────────────────────────── */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className={cn(
              "flex items-start gap-3 rounded-xl border px-4 py-3 text-sm shadow-sm",
              toast.kind === "success"
                ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                : "border-red-200 bg-red-50 text-red-800"
            )}
          >
            {toast.kind === "success" ? (
              <CheckCircle2 className="h-5 w-5 flex-none text-emerald-600" />
            ) : (
              <AlertCircle className="h-5 w-5 flex-none text-red-600" />
            )}
            <span className="leading-relaxed">{toast.message}</span>
            <button
              onClick={() => setToast(null)}
              className="ml-auto rounded-md p-1 text-current/60 hover:bg-black/5"
              aria-label="Dismiss"
            >
              <X className="h-4 w-4" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── Date Filters ─────────────────────────────────── */}
      <motion.div variants={fadeInUp}>
        <GlassCard className="flex flex-wrap items-center gap-4 p-4">
          <div className="flex items-center gap-2 text-slate-500">
            <Calendar className="h-4 w-4" />
            <span className="text-xs font-semibold uppercase tracking-wider">Filter</span>
          </div>
          <DateField label="From" value={dateFrom} onChange={setDateFrom} />
          <DateField label="To" value={dateTo} onChange={setDateTo} />
          {(dateFrom || dateTo) && (
            <button
              onClick={() => {
                setDateFrom("");
                setDateTo("");
              }}
              className="text-xs font-semibold text-violet-600 hover:text-violet-700 transition-colors"
            >
              Clear filters
            </button>
          )}
          <span className="ml-auto text-xs text-slate-500">
            {reports.length} report{reports.length === 1 ? "" : "s"}
          </span>
        </GlassCard>
      </motion.div>

      {/* ─── Report List ──────────────────────────────────── */}
      {isLoading ? (
        <div className="flex h-40 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-violet-500" />
        </div>
      ) : reports.length === 0 ? (
        <GlassCard className="p-12">
          <div className="flex flex-col items-center justify-center text-slate-400">
            <Inbox className="mb-4 h-14 w-14" />
            <p className="text-lg font-semibold text-slate-700">No reports yet</p>
            <p className="mt-1 text-sm text-slate-500">
              Click <span className="font-medium text-violet-700">generate report</span> to backfill the last week of briefs.
            </p>
          </div>
        </GlassCard>
      ) : (
        <motion.div variants={staggerChildren} initial="initial" animate="animate" className="space-y-3">
          {reports.map((report) => (
            <ReportRow
              key={report.id}
              report={report}
              isExpanded={expandedId === report.id}
              onToggle={() => setExpandedId(expandedId === report.id ? null : report.id)}
              onViewDetails={() => setDetailReport(report)}
            />
          ))}
        </motion.div>
      )}

      <AnimatePresence>
        {detailReport && (
          <ReportDetailModal
            report={detailReport}
            onClose={() => setDetailReport(null)}
          />
        )}
      </AnimatePresence>
    </motion.div>
  );
}

/* ─── Date field ───────────────────────────────────────────── */

function DateField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</span>
      <input
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 focus:border-violet-400 focus:outline-none focus:ring-2 focus:ring-violet-100"
      />
    </div>
  );
}

/* ─── Report Row ───────────────────────────────────────────── */

interface ReportRowProps {
  report: KPIReport;
  isExpanded: boolean;
  onToggle: () => void;
  onViewDetails: () => void;
}

function ReportRow({ report, isExpanded, onToggle, onViewDetails }: ReportRowProps) {
  const score = report.report_data?.ai_summary?.score;
  const conf = report.avg_confidence_score;
  return (
    <motion.div
      layout
      variants={fadeInUp}
      className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm shadow-slate-200/40 hover:shadow-md hover:shadow-slate-200/60 transition-shadow"
    >
      {/* Summary row */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <button
          onClick={onToggle}
          className="-mx-2 -my-2 flex min-w-0 flex-1 items-center gap-4 rounded-lg px-2 py-2 text-left hover:bg-slate-50 transition-colors"
        >
          <div className="flex h-11 w-11 flex-none items-center justify-center rounded-xl bg-violet-50 text-violet-600 ring-1 ring-violet-100">
            <FileText className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-900">{report.report_date}</p>
            <p className="mt-0.5 text-xs text-slate-500">
              <span className="font-medium text-slate-700">{report.order_volume}</span> orders ·{" "}
              <span className="font-medium text-slate-700">{formatCurrency(report.total_spend)}</span> spend
              {report.decisions_approved + report.decisions_flagged > 0 && (
                <>
                  {" "}·{" "}
                  <span className="font-medium text-slate-700">{report.decisions_approved}</span> approved
                </>
              )}
            </p>
          </div>
        </button>

        <div className="flex flex-wrap items-center gap-2">
          {score != null && <ScorePill score={score} />}
          {conf != null && <ConfidencePill confidence={conf} />}
          {report.email_sent ? (
            <span className="flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-emerald-700">
              <Mail className="h-3 w-3" /> Sent
            </span>
          ) : (
            <span className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              <MailX className="h-3 w-3" /> Not sent
            </span>
          )}

          <motion.button
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.96 }}
            onClick={onViewDetails}
            className="flex items-center gap-1.5 rounded-lg border border-violet-200 bg-violet-50 px-3 py-1.5 text-xs font-semibold text-violet-700 hover:bg-violet-100 transition-colors"
          >
            <Eye className="h-3.5 w-3.5" /> View Details
          </motion.button>

          <button
            onClick={onToggle}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
            aria-label="Toggle quick view"
          >
            <motion.span animate={{ rotate: isExpanded ? 180 : 0 }} transition={{ duration: 0.2 }}>
              <ChevronDown className="h-4 w-4" />
            </motion.span>
          </button>
        </div>
      </div>

      {/* Expandable quick metrics */}
      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="space-y-4 border-t border-slate-100 bg-slate-50/60 px-5 py-5">
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <QuickStat
                  icon={<ShoppingCart className="h-4 w-4 text-violet-500" />}
                  label="Orders"
                  value={String(report.order_volume)}
                />
                <QuickStat
                  icon={<CircleDollarSign className="h-4 w-4 text-emerald-500" />}
                  label="Total Spend"
                  value={formatCurrency(report.total_spend)}
                />
                <QuickStat
                  icon={<TrendingUp className="h-4 w-4 text-cyan-500" />}
                  label="Forecast Acc."
                  value={report.forecast_accuracy != null ? `${report.forecast_accuracy}%` : "—"}
                />
                <QuickStat
                  icon={<Truck className="h-4 w-4 text-amber-500" />}
                  label="Deliveries"
                  value={`${report.deliveries_completed} ✓ / ${report.deliveries_failed} ✗`}
                />
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-slate-500">
                  Generated {formatDate(report.created_at)}
                  {report.cost_savings_estimate != null && report.cost_savings_estimate > 0 && (
                    <>
                      {" "}·{" "}
                      <span className="font-semibold text-emerald-600">
                        {formatCurrency(report.cost_savings_estimate)} saved
                      </span>
                    </>
                  )}
                </p>
                <button
                  onClick={onViewDetails}
                  className="text-xs font-semibold text-violet-600 hover:text-violet-700 transition-colors"
                >
                  Open full report →
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

/* ─── Compact pills used in the row ────────────────────────── */

function ScorePill({ score }: { score: number }) {
  const tone =
    score >= 80
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : score >= 60
      ? "border-amber-200 bg-amber-50 text-amber-700"
      : "border-red-200 bg-red-50 text-red-700";
  return (
    <span className={cn("flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide", tone)}>
      <Sparkles className="h-3 w-3" /> {score}/100
    </span>
  );
}

function ConfidencePill({ confidence }: { confidence: number }) {
  const tone =
    confidence >= 80
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : confidence >= 60
      ? "border-amber-200 bg-amber-50 text-amber-700"
      : "border-red-200 bg-red-50 text-red-700";
  return (
    <span className={cn("flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide", tone)}>
      <Brain className="h-3 w-3" /> {confidence}% conf
    </span>
  );
}

function QuickStat({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
        {icon}
        {label}
      </div>
      <p className="mt-1.5 text-base font-bold text-slate-900">{value}</p>
    </div>
  );
}

/* ─── Detailed Report Modal ────────────────────────────────── */

interface ReportDetailModalProps {
  report: KPIReport;
  onClose: () => void;
}

function ReportDetailModal({ report, onClose }: ReportDetailModalProps) {
  const [sending, setSending] = useState(false);
  const [sendMsg, setSendMsg] = useState<string | null>(null);

  const ai = report.report_data?.ai_summary;
  const kpis = report.report_data?.industry_kpis ?? {};
  const score = ai?.score ?? null;

  const health = useMemo(() => {
    const checks: boolean[] = [];
    if (report.forecast_accuracy != null) checks.push(report.forecast_accuracy >= 85);
    if (kpis.otif_rate != null) checks.push(kpis.otif_rate >= 95);
    if (kpis.stockout_rate != null) checks.push(kpis.stockout_rate <= 2);
    if (kpis.rollback_rate != null) checks.push(kpis.rollback_rate <= 5);
    return { passing: checks.filter(Boolean).length, total: checks.length };
  }, [report, kpis]);

  const handleSendEmail = async () => {
    setSending(true);
    setSendMsg(null);
    try {
      const res = await api.post<{ success: boolean; to: string }>(
        `/reports/${report.id}/email`,
        {}
      );
      setSendMsg(
        res.success ? `Emailed report to ${res.to}.` : `Failed to email report to ${res.to}.`
      );
    } catch (e) {
      const detail =
        e instanceof Error && "message" in e ? e.message : "Failed to send email.";
      setSendMsg(String(detail));
    } finally {
      setSending(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-3 sm:p-6"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.96, opacity: 0, y: 16 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.96, opacity: 0, y: 16 }}
        transition={{ duration: 0.22 }}
        onClick={(e) => e.stopPropagation()}
        className="relative flex h-[94vh] w-full max-w-[1280px] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl shadow-slate-900/20"
      >
        {/* Header — light theme with violet accent */}
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-violet-100 bg-gradient-to-r from-violet-50 via-fuchsia-50/40 to-rose-50/30 px-7 py-5">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-violet-600">
              Daily Operations Brief
            </p>
            <h2 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">
              {report.report_date}
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Generated {formatDate(report.created_at)}
              {report.email_sent && report.email_sent_at && (
                <> · Emailed {formatDate(report.email_sent_at)}</>
              )}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {health.total > 0 && (
              <div className="rounded-full border border-violet-200 bg-white px-3.5 py-1.5 text-xs font-semibold text-violet-700">
                {health.passing}/{health.total} KPIs healthy
              </div>
            )}
            {score != null && (
              <div
                className={cn(
                  "rounded-full border px-3.5 py-1.5 text-sm font-bold",
                  score >= 80
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : score >= 60
                    ? "border-amber-200 bg-amber-50 text-amber-700"
                    : "border-red-200 bg-red-50 text-red-700"
                )}
              >
                Score {score}/100
              </div>
            )}
            <button
              onClick={onClose}
              className="rounded-lg p-2 text-slate-500 hover:bg-white hover:text-slate-700 transition-colors"
              aria-label="Close"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Body — scrollable */}
        <div className="flex-1 space-y-6 overflow-y-auto bg-slate-50/40 px-5 py-6 sm:px-7">
          {/* ── Headline metrics ── */}
          <Section icon={<Activity className="h-3.5 w-3.5" />} title="Headline">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <HeroStat
                icon={<ShoppingCart className="h-5 w-5" />}
                label="Orders Placed"
                value={String(report.order_volume)}
                accent="indigo"
              />
              <HeroStat
                icon={<CircleDollarSign className="h-5 w-5" />}
                label="Total Spend"
                value={formatCurrency(report.total_spend)}
                accent="emerald"
                hint={
                  kpis.avg_order_value != null
                    ? `Avg ${formatCurrency(kpis.avg_order_value)} / order`
                    : undefined
                }
              />
              <HeroStat
                icon={<TrendingUp className="h-5 w-5" />}
                label="Forecast Accuracy"
                value={report.forecast_accuracy != null ? `${report.forecast_accuracy}%` : "—"}
                accent={
                  report.forecast_accuracy == null
                    ? "slate"
                    : report.forecast_accuracy >= 85
                    ? "emerald"
                    : report.forecast_accuracy >= 70
                    ? "amber"
                    : "red"
                }
                hint="Target 85%+"
              />
              <HeroStat
                icon={<Brain className="h-5 w-5" />}
                label="Avg AI Confidence"
                value={
                  report.avg_confidence_score != null ? `${report.avg_confidence_score}%` : "—"
                }
                accent={
                  report.avg_confidence_score == null
                    ? "slate"
                    : report.avg_confidence_score >= 80
                    ? "emerald"
                    : report.avg_confidence_score >= 60
                    ? "amber"
                    : "red"
                }
              />
            </div>
          </Section>

          {/* ── Executive summary ── */}
          {ai?.summary && (
            <Section
              icon={<Brain className="h-3.5 w-3.5" />}
              title="Executive Summary"
              subtitle="LLM-generated, grounded in today's data."
            >
              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <p className="text-sm leading-relaxed text-slate-700">{ai.summary}</p>
              </div>
            </Section>
          )}

          {/* ── Decision health ── */}
          <Section icon={<CheckCircle2 className="h-3.5 w-3.5" />} title="Decision Health">
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
              <Pill
                label="Approved"
                value={report.decisions_approved}
                tone="good"
                icon={<CheckCircle2 className="h-3.5 w-3.5" />}
              />
              <Pill
                label="Flagged"
                value={report.decisions_flagged}
                tone="warn"
                icon={<AlertTriangle className="h-3.5 w-3.5" />}
              />
              <Pill
                label="Rolled Back"
                value={report.decisions_rolled_back}
                tone="bad"
                icon={<RefreshCw className="h-3.5 w-3.5" />}
              />
              <Pill
                label="Delivered"
                value={report.deliveries_completed}
                tone="good"
                icon={<Truck className="h-3.5 w-3.5" />}
              />
              <Pill
                label="Failed"
                value={report.deliveries_failed}
                tone="bad"
                icon={<Truck className="h-3.5 w-3.5" />}
              />
            </div>
          </Section>

          {/* ── Operational KPIs (only render tiles with data) ── */}
          {(() => {
            const tiles: React.ReactNode[] = [];
            if (kpis.otif_rate != null) {
              tiles.push(
                <KpiTile
                  key="otif"
                  label="OTIF Rate"
                  value={`${kpis.otif_rate}%`}
                  hint="On-time in-full · target 95%+"
                  tone={
                    kpis.otif_rate >= 95
                      ? "emerald"
                      : kpis.otif_rate >= 85
                      ? "amber"
                      : "red"
                  }
                  trend={kpis.otif_rate >= 95 ? "up" : "down"}
                />
              );
            }
            if (kpis.automation_rate != null) {
              tiles.push(
                <KpiTile
                  key="auto"
                  label="Automation Rate"
                  value={`${kpis.automation_rate}%`}
                  hint="Decisions auto-approved"
                  tone="indigo"
                />
              );
            }
            if (kpis.stockout_rate != null) {
              tiles.push(
                <KpiTile
                  key="stockout"
                  label="Stockout Rate"
                  value={`${kpis.stockout_rate}%`}
                  hint={
                    kpis.stockout_count != null && kpis.active_skus != null
                      ? `${kpis.stockout_count} of ${kpis.active_skus} SKUs`
                      : "Target ≤ 2%"
                  }
                  tone={
                    kpis.stockout_rate <= 2
                      ? "emerald"
                      : kpis.stockout_rate <= 5
                      ? "amber"
                      : "red"
                  }
                />
              );
            }
            if (kpis.rollback_rate != null) {
              tiles.push(
                <KpiTile
                  key="rollback"
                  label="Rollback Rate"
                  value={`${kpis.rollback_rate}%`}
                  hint={`${report.decisions_rolled_back} reversed today`}
                  tone={
                    kpis.rollback_rate <= 5
                      ? "emerald"
                      : kpis.rollback_rate <= 10
                      ? "amber"
                      : "red"
                  }
                />
              );
            }
            if (kpis.at_risk_count != null) {
              tiles.push(
                <KpiTile
                  key="atrisk"
                  label="At-Risk SKUs"
                  value={String(kpis.at_risk_count)}
                  hint="Below reorder threshold"
                  tone={
                    kpis.at_risk_count === 0
                      ? "emerald"
                      : kpis.at_risk_count <= 3
                      ? "amber"
                      : "red"
                  }
                />
              );
            }
            if (kpis.perfect_order_rate != null) {
              tiles.push(
                <KpiTile
                  key="perfect"
                  label="Perfect Order Rate"
                  value={`${kpis.perfect_order_rate}%`}
                  hint="No issues end-to-end"
                  tone={
                    kpis.perfect_order_rate >= 95
                      ? "emerald"
                      : kpis.perfect_order_rate >= 85
                      ? "amber"
                      : "red"
                  }
                />
              );
            }
            if (report.email_delivery_rate != null) {
              tiles.push(
                <KpiTile
                  key="email"
                  label="Email Delivery"
                  value={`${report.email_delivery_rate}%`}
                  hint="Supplier inbox success"
                  tone={
                    report.email_delivery_rate >= 95
                      ? "emerald"
                      : report.email_delivery_rate >= 85
                      ? "amber"
                      : "red"
                  }
                />
              );
            }
            const totalDec =
              kpis.total_decisions ??
              report.decisions_approved +
                report.decisions_flagged +
                report.decisions_rolled_back;
            if (totalDec > 0) {
              tiles.push(
                <KpiTile
                  key="totaldec"
                  label="Total Decisions"
                  value={String(totalDec)}
                  hint="Approved + flagged + rolled back"
                  tone="slate"
                />
              );
            }

            if (tiles.length === 0) {
              return (
                <Section
                  icon={<Sparkles className="h-3.5 w-3.5" />}
                  title="Operational KPIs"
                  subtitle="No measurable activity yet — generate today's report or run the pipeline."
                >
                  <div className="rounded-xl border border-dashed border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
                    KPIs will populate as orders, decisions, and deliveries land for this date.
                  </div>
                </Section>
              );
            }

            return (
              <Section
                icon={<Sparkles className="h-3.5 w-3.5" />}
                title="Operational KPIs"
                subtitle="Targets follow industry medians."
              >
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {tiles}
                </div>
              </Section>
            );
          })()}

          {/* ── Spend & suppliers (hide entirely when both empty) ── */}
          {(() => {
            const cats = kpis.spend_by_category ?? [];
            const sups = kpis.top_suppliers ?? [];
            if (cats.length === 0 && sups.length === 0) return null;
            return (
              <Section icon={<ShoppingCart className="h-3.5 w-3.5" />} title="Spend Breakdown">
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                  {cats.length > 0 && (
                    <DataTable
                      icon={<ShoppingCart className="h-3.5 w-3.5" />}
                      title="By Category"
                      empty=""
                      rows={cats.map((c) => ({
                        name: c.category,
                        meta: `${c.orders} order${c.orders === 1 ? "" : "s"}`,
                        value: formatCurrency(c.spend),
                      }))}
                    />
                  )}
                  {sups.length > 0 && (
                    <DataTable
                      icon={<Package className="h-3.5 w-3.5" />}
                      title="Top Suppliers"
                      empty=""
                      rows={sups.map((s) => ({
                        name: s.supplier,
                        meta: `${s.orders} order${s.orders === 1 ? "" : "s"}`,
                        value: formatCurrency(s.spend),
                      }))}
                    />
                  )}
                </div>
              </Section>
            );
          })()}

          {/* ── AI insights ── */}
          {(ai?.highlights?.length ||
            ai?.trends?.length ||
            ai?.risk_alerts?.length ||
            ai?.recommendations?.length) ? (
            <Section icon={<Sparkles className="h-3.5 w-3.5" />} title="AI Insights">
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                {ai?.highlights && ai.highlights.length > 0 && (
                  <InsightList
                    icon={<Sparkles className="h-3.5 w-3.5" />}
                    title="Highlights"
                    items={ai.highlights}
                    tone="indigo"
                  />
                )}
                {ai?.trends && ai.trends.length > 0 && (
                  <InsightList
                    icon={<TrendingUp className="h-3.5 w-3.5" />}
                    title="Trends"
                    items={ai.trends}
                    tone="cyan"
                  />
                )}
                {ai?.risk_alerts && ai.risk_alerts.length > 0 && (
                  <InsightList
                    icon={<AlertTriangle className="h-3.5 w-3.5" />}
                    title="Risk Alerts"
                    items={ai.risk_alerts}
                    tone="red"
                  />
                )}
                {ai?.recommendations && ai.recommendations.length > 0 && (
                  <InsightList
                    icon={<Lightbulb className="h-3.5 w-3.5" />}
                    title="Recommended Actions"
                    items={ai.recommendations}
                    tone="emerald"
                    numbered
                  />
                )}
              </div>
            </Section>
          ) : (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
              <strong className="font-semibold">AI summary not generated.</strong> Click{" "}
              <span className="font-semibold">Generate Today's Report</span> on the parent page to
              add insights and recommendations.
            </div>
          )}
        </div>

        {/* ── Footer ── */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-white px-5 py-4 sm:px-7">
          <p className="text-xs text-slate-500">
            Benchmarks: OTIF 95%+, forecast accuracy 85%+, stockout ≤ 2%, rollback ≤ 5%.
          </p>
          <div className="flex items-center gap-3">
            {sendMsg && <span className="text-xs text-slate-600">{sendMsg}</span>}
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleSendEmail}
              disabled={sending}
              className={cn(
                "flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-xs font-semibold text-white shadow-md shadow-violet-500/30 hover:bg-violet-700 hover:shadow-lg hover:shadow-violet-500/40 transition",
                sending && "cursor-wait opacity-70"
              )}
            >
              {sending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
              {report.email_sent ? "Resend Email" : "Email Report"}
            </motion.button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

/* ─── Modal sub-components ─────────────────────────────────── */

function Section({
  icon,
  title,
  subtitle,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="mb-2.5 flex flex-wrap items-baseline gap-2">
        <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.18em] text-violet-700">
          {icon}
          {title}
        </div>
        {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

type AccentTone = "indigo" | "emerald" | "amber" | "red" | "cyan" | "slate";

function HeroStat({
  icon,
  label,
  value,
  hint,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint?: string;
  accent: AccentTone;
}) {
  const accentBg: Record<AccentTone, string> = {
    indigo: "from-violet-500 to-purple-500",
    emerald: "from-emerald-500 to-teal-500",
    amber: "from-amber-500 to-orange-500",
    red: "from-red-500 to-rose-500",
    cyan: "from-cyan-500 to-sky-500",
    slate: "from-slate-400 to-slate-500",
  };
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          {label}
        </span>
        <span
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br text-white shadow-sm",
            accentBg[accent]
          )}
        >
          {icon}
        </span>
      </div>
      <p className="mt-3 text-2xl font-bold text-slate-900">{value}</p>
      {hint && <p className="mt-1 text-[11px] text-slate-500">{hint}</p>}
    </div>
  );
}

function KpiTile({
  label,
  value,
  hint,
  tone,
  trend,
}: {
  label: string;
  value: string;
  hint?: string;
  tone: AccentTone;
  trend?: "up" | "down" | "flat";
}) {
  const valueColor: Record<AccentTone, string> = {
    indigo: "text-violet-700",
    emerald: "text-emerald-700",
    amber: "text-amber-700",
    red: "text-red-700",
    cyan: "text-cyan-700",
    slate: "text-slate-900",
  };
  const trendNode =
    trend === "up" ? (
      <ArrowUpRight className="h-3.5 w-3.5 text-emerald-600" />
    ) : trend === "down" ? (
      <ArrowDownRight className="h-3.5 w-3.5 text-red-600" />
    ) : trend === "flat" ? (
      <Minus className="h-3.5 w-3.5 text-slate-400" />
    ) : null;
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        {label}
      </div>
      <div className="mt-1.5 flex items-baseline gap-1.5">
        <span className={cn("text-xl font-bold", valueColor[tone])}>{value}</span>
        {trendNode}
      </div>
      {hint && <p className="mt-1 text-[11px] text-slate-500">{hint}</p>}
    </div>
  );
}

function Pill({
  label,
  value,
  tone,
  icon,
}: {
  label: string;
  value: number;
  tone: "good" | "warn" | "bad";
  icon: React.ReactNode;
}) {
  const toneClass =
    tone === "good"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : tone === "warn"
      ? "border-amber-200 bg-amber-50 text-amber-700"
      : "border-red-200 bg-red-50 text-red-700";
  return (
    <div className={cn("rounded-xl border p-3", toneClass)}>
      <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider opacity-90">
        {icon} {label}
      </div>
      <div className="mt-1 text-xl font-bold">{value}</div>
    </div>
  );
}

function DataTable({
  icon,
  title,
  rows,
  empty,
}: {
  icon: React.ReactNode;
  title: string;
  rows: { name: string; meta: string; value: string }[];
  empty: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-700">
        {icon} {title}
      </div>
      {rows.length === 0 ? (
        <p className="mt-3 text-xs text-slate-500">{empty}</p>
      ) : (
        <ul className="mt-3 divide-y divide-slate-100">
          {rows.map((r, i) => (
            <li key={i} className="flex items-center justify-between py-2.5">
              <div className="min-w-0 pr-3">
                <p className="truncate text-sm font-medium text-slate-900">{r.name}</p>
                <p className="text-[11px] text-slate-500">{r.meta}</p>
              </div>
              <span className="text-sm font-semibold text-slate-900">{r.value}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

type InsightTone = "indigo" | "cyan" | "red" | "emerald";

function InsightList({
  icon,
  title,
  items,
  tone,
  numbered = false,
}: {
  icon: React.ReactNode;
  title: string;
  items: string[];
  tone: InsightTone;
  numbered?: boolean;
}) {
  const card: Record<InsightTone, string> = {
    indigo: "border-violet-200 bg-violet-50",
    cyan: "border-cyan-200 bg-cyan-50",
    red: "border-red-200 bg-red-50",
    emerald: "border-emerald-200 bg-emerald-50",
  };
  const heading: Record<InsightTone, string> = {
    indigo: "text-violet-700",
    cyan: "text-cyan-700",
    red: "text-red-700",
    emerald: "text-emerald-700",
  };
  const text: Record<InsightTone, string> = {
    indigo: "text-violet-900",
    cyan: "text-cyan-900",
    red: "text-red-900",
    emerald: "text-emerald-900",
  };
  return (
    <section className={cn("rounded-xl border p-4", card[tone])}>
      <div
        className={cn(
          "flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.18em]",
          heading[tone]
        )}
      >
        {icon} {title}
      </div>
      {numbered ? (
        <ol className={cn("mt-2 list-decimal space-y-1.5 pl-5 text-sm", text[tone])}>
          {items.map((it, i) => (
            <li key={i}>{it}</li>
          ))}
        </ol>
      ) : (
        <ul className={cn("mt-2 list-disc space-y-1.5 pl-5 text-sm", text[tone])}>
          {items.map((it, i) => (
            <li key={i}>{it}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
