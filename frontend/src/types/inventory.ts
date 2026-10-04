export interface InventoryItem {
  id: string;
  name: string;
  sku: string;
  category: string;
  current_stock: number;
  reorder_threshold: number;
  safety_stock: number;
  lead_time_days: number;
  unit_cost: number;
  supplier_email: string | null;
  status: "normal" | "low_stock" | "out_of_stock" | "reorder_pending";
  is_active: boolean;
  last_checked_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface InventoryListResponse {
  items: InventoryItem[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface InventoryItemCreate {
  name: string;
  sku: string;
  category: string;
  current_stock?: number;
  reorder_threshold: number;
  safety_stock?: number;
  lead_time_days?: number;
  unit_cost: number;
  supplier_email?: string;
}

export interface InventoryItemUpdate {
  name?: string;
  category?: string;
  current_stock?: number;
  reorder_threshold?: number;
  safety_stock?: number;
  lead_time_days?: number;
  unit_cost?: number;
  supplier_email?: string;
  is_active?: boolean;
}
