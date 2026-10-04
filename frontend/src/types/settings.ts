export interface EmailConfig {
  id: string;
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_use_tls: boolean;
  from_email: string;
  from_name: string;
  supplier_mappings: Record<string, { email: string; name: string }>;
  confidence_threshold: number;
  daily_report_enabled: boolean;
  daily_report_time: string;
  daily_report_recipients: string[];
  admin_notification_email: string | null;
  // Feature 004 — Supplier ETA Agent (T055).
  imap_host?: string | null;
  imap_port?: number | null;
  eta_auto_apply_threshold?: number;
  created_at: string;
  updated_at: string;
}

export interface EmailDefaults {
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_use_tls: boolean;
  from_email: string;
  from_name: string;
  admin_notification_email: string | null;
  supplier_override_email: string | null;
  password_configured: boolean;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: "admin" | "viewer";
  is_active: boolean;
  created_at: string;
}
