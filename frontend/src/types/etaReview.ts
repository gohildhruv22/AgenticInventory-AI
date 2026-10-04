/**
 * Types mirroring the OpenAPI contract at
 * `specs/004-supplier-delivery-eta-agent/contracts/eta-reviews.openapi.yaml`.
 */

export type EtaIntent =
  | "confirm"
  | "delay"
  | "cancel"
  | "acknowledge"
  | "unclear";

export type CorrectIntent = "confirm" | "delay" | "cancel" | "acknowledge";

export type RaisedReason =
  | "low_confidence"
  | "unmatched_order"
  | "ambiguous_match"
  | "negative_intent"
  | "past_date"
  | "non_english";

export type ResolutionState =
  | "pending"
  | "approved"
  | "corrected"
  | "dismissed";

export type ReviewStateFilter = ResolutionState | "all";

export interface SupplierReplyEmbedded {
  id: string;
  subject: string;
  from_address: string;
  received_at: string;
  body_excerpt: string;
}

export interface EtaReviewResolutionPayload {
  delivery_id: string;
  parsed_date: string;
  intent: CorrectIntent;
}

export interface EtaReviewSummary {
  id: string;
  raised_at: string;
  raised_reason: RaisedReason;
  agent_intent: EtaIntent;
  agent_parsed_date: string | null;
  agent_confidence: number;
  resolution_state: ResolutionState;
  candidate_delivery_id: string | null;
  supplier_from: string;
  supplier_reply_excerpt: string;
}

export interface EtaReviewDetailResponse extends EtaReviewSummary {
  agent_reasoning: string;
  candidate_order_ids: string[];
  supplier_reply: SupplierReplyEmbedded;
  resolved_by: string | null;
  resolved_at: string | null;
  resolution_payload: EtaReviewResolutionPayload | null;
}

export interface EtaReviewListResponse {
  items: EtaReviewSummary[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface EtaReviewCorrectRequest {
  delivery_id: string;
  parsed_date: string;
  intent: CorrectIntent;
  note?: string;
}

export interface EtaReviewDismissRequest {
  note?: string;
}
