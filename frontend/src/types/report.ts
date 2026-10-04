export interface AISummary {
  summary: string;
  highlights: string[];
  trends: string[];
  recommendations: string[];
  risk_alerts: string[];
  score: number;
}

export interface IndustryKPIs {
  otif_rate: number | null;
  automation_rate: number | null;
  rollback_rate: number | null;
  stockout_rate: number | null;
  active_skus: number | null;
  stockout_count: number | null;
  at_risk_count: number | null;
  avg_order_value: number | null;
  perfect_order_rate: number | null;
  spend_by_category: { category: string; spend: number; orders: number }[];
  top_suppliers: { supplier: string; orders: number; spend: number }[];
  total_decisions: number | null;
  total_deliveries: number | null;
}

export interface ReportData {
  generated_at?: string;
  ai_summary?: AISummary;
  industry_kpis?: Partial<IndustryKPIs>;
}

export interface KPIReport {
  id: string;
  report_date: string;
  order_volume: number;
  total_spend: number;
  forecast_accuracy: number | null;
  avg_confidence_score: number | null;
  decisions_approved: number;
  decisions_flagged: number;
  decisions_rolled_back: number;
  deliveries_completed: number;
  deliveries_failed: number;
  supplier_performance: Record<string, unknown>;
  agent_activity: Record<string, unknown>;
  email_delivery_rate: number | null;
  cost_savings_estimate: number | null;
  email_sent: boolean;
  email_sent_at?: string | null;
  email_recipients?: string[] | Record<string, unknown>;
  report_data?: ReportData;
  created_at: string;
}

export interface DashboardMetrics {
  order_volume: number;
  total_spend: number;
  forecast_accuracy: number | null;
  avg_confidence: number | null;
  decisions_approved: number;
  decisions_flagged: number;
  active_deliveries: number;
  low_stock_count: number;
}
