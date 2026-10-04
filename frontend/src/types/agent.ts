export interface ReasoningTrace {
  decision?: string;
  reasoning?: string;
  risk_factors?: string[];
  forecast_confidence?: number;
  predicted_demand?: number;
  suggested_order_qty?: number;
  approved_order_qty?: number;
  estimated_cost?: number;
  item_context?: {
    name?: string;
    sku?: string;
    current_stock?: number;
    unit_cost?: number;
  };
  // Legacy/generic fields
  input_context?: string;
  rationale?: string;
  confidence?: number;
  alternatives?: { action: string; reason: string; rejected_because?: string }[];
  data_sources?: string[];
}

export interface AgentDecision {
  id: string;
  agent_type: string;
  action_type: string;
  inventory_item_id: string | null;
  forecast_id: string | null;
  reasoning_trace: ReasoningTrace;
  confidence_level: number | null;
  alternatives_considered: Record<string, unknown>[];
  status: "executed" | "approved" | "flagged" | "rejected" | "pending_review" | "rolled_back";
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DecisionListResponse {
  decisions: AgentDecision[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface PipelineStatus {
  active: boolean;
  current_agent: string | null;
  progress: number;
  total_steps: number;
}
