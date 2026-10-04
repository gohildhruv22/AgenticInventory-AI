export type DeliveryTimelineEventType =
  | "eta_confirmed"
  | "eta_revised"
  | "acknowledged"
  | "at_risk"
  | "delivered"
  | "manual_override"
  | "note";

export type DeliveryTimelineActorType = "agent" | "admin" | "simulator";

export interface DeliveryTimelineEntry {
  id: string;
  delivery_id: string;
  event_type: DeliveryTimelineEventType;
  occurred_at: string;
  actor_type: DeliveryTimelineActorType;
  actor_id: string | null;
  parsed_date: string | null;
  confidence: number | null;
  supplier_excerpt: string | null;
  source_reply_id: string | null;
  source_review_id: string | null;
  note: string | null;
  created_at: string;
}

export interface DeliveryTimelineResponse {
  delivery_id: string;
  entries: DeliveryTimelineEntry[];
}

export interface Delivery {
  id: string;
  order_id: string;
  current_stage: string;
  stage_history: { stage: string; timestamp: string; notes?: string }[];
  expected_delivery_at: string | null;
  actual_delivery_at: string | null;
  items_received: Record<string, unknown> | null;
  // Feature 004 additions (deliveries-timeline.openapi.yaml).
  has_pending_review: boolean;
  latest_timeline_entry: DeliveryTimelineEntry | null;
  created_at: string;
  updated_at: string;
}

export interface DeliveryListResponse {
  deliveries: Delivery[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}
