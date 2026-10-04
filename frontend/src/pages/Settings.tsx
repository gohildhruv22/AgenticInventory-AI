import { useState, useEffect, type FormEvent } from "react";
import { motion } from "framer-motion";
import {
  Settings as SettingsIcon,
  Mail,
  Server,
  Shield,
  Users,
  Plus,
  Trash2,
  Send,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Sliders,
  Clock,
  Bell,
} from "lucide-react";
import { GlassCard } from "@/components/ui/GlassCard";
import { fadeInUp, staggerChildren, pageTransition } from "@/lib/animations";
import { useSettingsStore } from "@/stores/settingsStore";
import { cn } from "@/lib/utils";

interface SupplierMapping {
  category: string;
  email: string;
  name: string;
}

export default function SettingsPage() {
  const {
    emailConfig,
    emailDefaults,
    isLoading,
    fetchEmailConfig,
    fetchEmailDefaults,
    saveEmailConfig,
    testEmail,
  } = useSettingsStore();

  // SMTP form state
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState(587);
  const [smtpUsername, setSmtpUsername] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [smtpUseTls, setSmtpUseTls] = useState(true);
  const [fromEmail, setFromEmail] = useState("");
  const [fromName, setFromName] = useState("AgenticInventory AI");

  // Supplier mappings
  const [mappings, setMappings] = useState<SupplierMapping[]>([]);
  const [newCategory, setNewCategory] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newName, setNewName] = useState("");

  // Threshold & reports
  const [confidenceThreshold, setConfidenceThreshold] = useState(75);
  const [dailyReportEnabled, setDailyReportEnabled] = useState(true);
  const [dailyReportTime, setDailyReportTime] = useState("08:00");
  const [adminNotificationEmail, setAdminNotificationEmail] = useState("");

  // Feature 004 — Supplier ETA Agent (T055).
  const [imapHost, setImapHost] = useState("");
  const [imapPort, setImapPort] = useState<number | "">("");
  const [etaAutoApplyThreshold, setEtaAutoApplyThreshold] = useState(80);

  // UI state
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [testTo, setTestTo] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  // Load existing config + server-side defaults in parallel
  useEffect(() => {
    fetchEmailConfig();
    fetchEmailDefaults();
  }, [fetchEmailConfig, fetchEmailDefaults]);

  // Populate form when config loads
  useEffect(() => {
    if (emailConfig) {
      setSmtpHost(emailConfig.smtp_host);
      setSmtpPort(emailConfig.smtp_port);
      setSmtpUsername(emailConfig.smtp_username);
      setSmtpUseTls(emailConfig.smtp_use_tls);
      setFromEmail(emailConfig.from_email);
      setFromName(emailConfig.from_name);
      setConfidenceThreshold(Number(emailConfig.confidence_threshold));
      setDailyReportEnabled(emailConfig.daily_report_enabled);
      setDailyReportTime(emailConfig.daily_report_time);
      setAdminNotificationEmail(emailConfig.admin_notification_email ?? "");
      setImapHost(emailConfig.imap_host ?? "");
      setImapPort(emailConfig.imap_port ?? "");
      setEtaAutoApplyThreshold(
        Number(emailConfig.eta_auto_apply_threshold ?? 80),
      );

      const mapped = Object.entries(emailConfig.supplier_mappings).map(
        ([category, val]) => ({
          category,
          email: val.email,
          name: val.name,
        })
      );
      setMappings(mapped);
    }
  }, [emailConfig]);

  // Pre-fill from server-side .env defaults when no DB config exists yet so
  // first-time save doesn't fail with empty required fields.
  useEffect(() => {
    if (!emailConfig && emailDefaults) {
      setSmtpHost((prev) => prev || emailDefaults.smtp_host);
      setSmtpPort((prev) => prev || emailDefaults.smtp_port);
      setSmtpUsername((prev) => prev || emailDefaults.smtp_username);
      setSmtpUseTls(emailDefaults.smtp_use_tls);
      setFromEmail((prev) => prev || emailDefaults.from_email);
      setFromName((prev) => prev || emailDefaults.from_name);
      setAdminNotificationEmail(
        (prev) => prev || emailDefaults.admin_notification_email || ""
      );
    }
  }, [emailConfig, emailDefaults]);

  const addMapping = () => {
    if (!newCategory || !newEmail) return;
    setMappings((prev) => [
      ...prev,
      { category: newCategory, email: newEmail, name: newName || newCategory },
    ]);
    setNewCategory("");
    setNewEmail("");
    setNewName("");
  };

  const removeMapping = (idx: number) => {
    setMappings((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSave = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    const supplierMappings: Record<string, { email: string; name: string }> = {};
    for (const m of mappings) {
      supplierMappings[m.category] = { email: m.email, name: m.name };
    }

    try {
      await saveEmailConfig({
        smtp_host: smtpHost,
        smtp_port: smtpPort,
        smtp_username: smtpUsername,
        smtp_password: smtpPassword || undefined,
        smtp_use_tls: smtpUseTls,
        from_email: fromEmail,
        from_name: fromName,
        supplier_mappings: supplierMappings,
        confidence_threshold: confidenceThreshold,
        daily_report_enabled: dailyReportEnabled,
        daily_report_time: dailyReportTime,
        admin_notification_email: adminNotificationEmail || undefined,
        imap_host: imapHost || undefined,
        imap_port: imapPort === "" ? undefined : imapPort,
        eta_auto_apply_threshold: etaAutoApplyThreshold,
      } as never);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      setSaveError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleTestEmail = async () => {
    if (!testTo) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await testEmail(testTo);
      setTestResult(result);
    } catch {
      setTestResult({ success: false, message: "Failed to send test email" });
    } finally {
      setTesting(false);
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
      {/* Header */}
      <motion.div variants={fadeInUp} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Settings</h1>
          <p className="mt-1 text-sm text-white/40">
            Email configuration, thresholds, and supplier mappings
          </p>
        </div>
      </motion.div>

      <form onSubmit={handleSave}>
        <motion.div
          variants={staggerChildren}
          initial="initial"
          animate="animate"
          className="grid grid-cols-1 gap-6 lg:grid-cols-2"
        >
          {/* ─── SMTP Configuration ─────────────────────────── */}
          <motion.div variants={fadeInUp}>
            <GlassCard className="p-6">
              <div className="mb-5 flex items-center gap-2">
                <Server className="h-4 w-4 text-cyan-400" />
                <h2 className="text-sm font-semibold text-white/80">SMTP Configuration</h2>
              </div>

              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-3">
                  <div className="col-span-2">
                    <label className="mb-1 block text-[11px] font-medium text-white/40">
                      SMTP Host
                    </label>
                    <input
                      type="text"
                      value={smtpHost}
                      onChange={(e) => setSmtpHost(e.target.value)}
                      placeholder="smtp.gmail.com"
                      className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white placeholder:text-white/20 outline-none focus:border-purple-500/40 transition-colors"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] font-medium text-white/40">Port</label>
                    <input
                      type="number"
                      value={smtpPort}
                      onChange={(e) => setSmtpPort(parseInt(e.target.value) || 587)}
                      className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white outline-none focus:border-purple-500/40 transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="mb-1 block text-[11px] font-medium text-white/40">
                    Username
                  </label>
                  <input
                    type="text"
                    value={smtpUsername}
                    onChange={(e) => setSmtpUsername(e.target.value)}
                    placeholder="your@email.com"
                    className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white placeholder:text-white/20 outline-none focus:border-purple-500/40 transition-colors"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-[11px] font-medium text-white/40">
                    Password
                  </label>
                  <input
                    type="password"
                    value={smtpPassword}
                    onChange={(e) => setSmtpPassword(e.target.value)}
                    placeholder={emailConfig ? "••••••••" : "App-specific password"}
                    className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white placeholder:text-white/20 outline-none focus:border-purple-500/40 transition-colors"
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <label className="mb-1 block text-[11px] font-medium text-white/40">
                      From Email
                    </label>
                    <input
                      type="email"
                      value={fromEmail}
                      onChange={(e) => setFromEmail(e.target.value)}
                      placeholder="noreply@company.com"
                      className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white placeholder:text-white/20 outline-none focus:border-purple-500/40 transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="mb-1 block text-[11px] font-medium text-white/40">
                    From Name
                  </label>
                  <input
                    type="text"
                    value={fromName}
                    onChange={(e) => setFromName(e.target.value)}
                    className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white placeholder:text-white/20 outline-none focus:border-purple-500/40 transition-colors"
                  />
                </div>

                {/* TLS toggle */}
                <label className="flex items-center gap-3 cursor-pointer">
                  <div
                    className={cn(
                      "relative h-5 w-9 rounded-full transition-colors",
                      smtpUseTls ? "bg-purple-500" : "bg-white/10"
                    )}
                    onClick={() => setSmtpUseTls(!smtpUseTls)}
                  >
                    <div
                      className={cn(
                        "absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform",
                        smtpUseTls ? "translate-x-4" : "translate-x-0.5"
                      )}
                    />
                  </div>
                  <span className="text-xs text-white/50">Use TLS Encryption</span>
                  <Shield className="h-3.5 w-3.5 text-emerald-400/60" />
                </label>
              </div>
            </GlassCard>
          </motion.div>

          {/* ─── Test Email ──────────────────────────────────── */}
          <motion.div variants={fadeInUp}>
            <GlassCard className="p-6">
              <div className="mb-5 flex items-center gap-2">
                <Mail className="h-4 w-4 text-amber-400" />
                <h2 className="text-sm font-semibold text-white/80">Test Email</h2>
              </div>

              <p className="mb-4 text-xs text-white/30">
                Send a test email to verify your SMTP configuration is working correctly.
              </p>

              <div className="flex gap-2">
                <input
                  type="email"
                  value={testTo}
                  onChange={(e) => setTestTo(e.target.value)}
                  placeholder="test@example.com"
                  className="flex-1 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white placeholder:text-white/20 outline-none focus:border-purple-500/40 transition-colors"
                />
                <motion.button
                  type="button"
                  onClick={handleTestEmail}
                  disabled={testing || !testTo}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-amber-500 to-orange-500 px-4 py-2 text-sm font-medium text-white shadow-lg shadow-amber-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {testing ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                  Send
                </motion.button>
              </div>

              {testResult && (
                <motion.div
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={cn(
                    "mt-3 flex items-center gap-2 rounded-lg border px-3 py-2 text-xs",
                    testResult.success
                      ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
                      : "border-red-500/20 bg-red-500/10 text-red-300"
                  )}
                >
                  {testResult.success ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : (
                    <AlertCircle className="h-3.5 w-3.5" />
                  )}
                  {testResult.message}
                </motion.div>
              )}

              {/* ─── Confidence Threshold ─────────────────────── */}
              <div className="mt-8">
                <div className="mb-4 flex items-center gap-2">
                  <Sliders className="h-4 w-4 text-purple-400" />
                  <h3 className="text-sm font-semibold text-white/80">Decision Threshold</h3>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-white/40">Auto-approval confidence</span>
                    <span className="text-sm font-bold text-purple-400">{confidenceThreshold}%</span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={confidenceThreshold}
                    onChange={(e) => setConfidenceThreshold(parseInt(e.target.value))}
                    className="w-full accent-purple-500"
                  />
                  <p className="text-[10px] text-white/20">
                    Forecasts below this threshold require manual approval
                  </p>
                </div>
              </div>

              {/* ─── Daily Reports ────────────────────────────── */}
              <div className="mt-6">
                <div className="mb-3 flex items-center gap-2">
                  <Bell className="h-4 w-4 text-cyan-400" />
                  <h3 className="text-sm font-semibold text-white/80">Notifications</h3>
                </div>

                <label className="flex items-center gap-3 cursor-pointer mb-3">
                  <div
                    className={cn(
                      "relative h-5 w-9 rounded-full transition-colors",
                      dailyReportEnabled ? "bg-purple-500" : "bg-white/10"
                    )}
                    onClick={() => setDailyReportEnabled(!dailyReportEnabled)}
                  >
                    <div
                      className={cn(
                        "absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform",
                        dailyReportEnabled ? "translate-x-4" : "translate-x-0.5"
                      )}
                    />
                  </div>
                  <span className="text-xs text-white/50">Daily KPI report</span>
                </label>

                {dailyReportEnabled && (
                  <div className="flex items-center gap-2 ml-12">
                    <Clock className="h-3.5 w-3.5 text-white/30" />
                    <input
                      type="time"
                      value={dailyReportTime}
                      onChange={(e) => setDailyReportTime(e.target.value)}
                      className="rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-xs text-white outline-none focus:border-purple-500/40 transition-colors"
                    />
                  </div>
                )}

                <div className="mt-3">
                  <label className="mb-1 block text-[11px] font-medium text-white/40">
                    Admin notification email
                  </label>
                  <input
                    type="email"
                    value={adminNotificationEmail}
                    onChange={(e) => setAdminNotificationEmail(e.target.value)}
                    placeholder="admin@company.com"
                    className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white placeholder:text-white/20 outline-none focus:border-purple-500/40 transition-colors"
                  />
                </div>
              </div>

            </GlassCard>
          </motion.div>

          {/* ─── Supplier Mappings ────────────────────────────── */}
          <motion.div variants={fadeInUp} className="lg:col-span-2">
            <GlassCard className="p-6">
              <div className="mb-5 flex items-center gap-2">
                <Users className="h-4 w-4 text-emerald-400" />
                <h2 className="text-sm font-semibold text-white/80">Supplier Email Mappings</h2>
              </div>

              <p className="mb-4 text-xs text-white/30">
                Map inventory categories to supplier email addresses for automated purchase orders.
              </p>

              {/* Existing mappings */}
              {mappings.length > 0 && (
                <div className="mb-4 space-y-2">
                  {mappings.map((m, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-3 rounded-lg border border-white/[0.04] bg-white/[0.015] p-3"
                    >
                      <span className="rounded-lg bg-emerald-500/10 px-2 py-1 text-xs font-semibold text-emerald-400">
                        {m.category}
                      </span>
                      <span className="flex-1 text-xs text-white/50">{m.email}</span>
                      <span className="text-xs text-white/30">{m.name}</span>
                      <button
                        type="button"
                        onClick={() => removeMapping(idx)}
                        className="rounded-lg p-1.5 text-white/20 hover:bg-red-500/10 hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* Add new mapping */}
              <div className="flex flex-wrap items-end gap-3">
                <div>
                  <label className="mb-1 block text-[11px] font-medium text-white/40">
                    Category
                  </label>
                  <input
                    type="text"
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                    placeholder="Electronics"
                    className="w-36 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white placeholder:text-white/20 outline-none focus:border-purple-500/40 transition-colors"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-[11px] font-medium text-white/40">
                    Supplier Email
                  </label>
                  <input
                    type="email"
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value)}
                    placeholder="supplier@example.com"
                    className="w-52 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white placeholder:text-white/20 outline-none focus:border-purple-500/40 transition-colors"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-[11px] font-medium text-white/40">
                    Supplier Name
                  </label>
                  <input
                    type="text"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="Acme Inc"
                    className="w-40 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white placeholder:text-white/20 outline-none focus:border-purple-500/40 transition-colors"
                  />
                </div>
                <motion.button
                  type="button"
                  onClick={addMapping}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-xs font-medium text-white/60 hover:bg-white/[0.06] transition-colors"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Add
                </motion.button>
              </div>
            </GlassCard>
          </motion.div>
        </motion.div>

        {/* ─── Save Button ────────────────────────────────── */}
        <motion.div variants={fadeInUp} className="mt-6 flex items-center gap-4">
          <motion.button
            type="submit"
            disabled={saving || isLoading}
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-purple-500 to-pink-500 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-purple-500/20 hover:shadow-purple-500/30 transition-shadow disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <SettingsIcon className="h-4 w-4" />
            )}
            {saving ? "Saving…" : "Save Settings"}
          </motion.button>

          {saveSuccess && (
            <motion.span
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center gap-1.5 text-sm text-emerald-400"
            >
              <CheckCircle2 className="h-4 w-4" />
              Settings saved
            </motion.span>
          )}

          {saveError && (
            <motion.span
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center gap-1.5 text-sm text-red-400"
            >
              <AlertCircle className="h-4 w-4" />
              {saveError}
            </motion.span>
          )}
        </motion.div>
      </form>
    </motion.div>
  );
}
