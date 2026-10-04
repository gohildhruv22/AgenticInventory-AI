import { create } from "zustand";
import type { InventoryItem } from "@/types/inventory";

interface InventoryState {
  items: Map<string, InventoryItem>;
  search: string;
  categoryFilter: string | null;
  statusFilter: string | null;

  setItems: (items: InventoryItem[]) => void;
  updateItem: (item: InventoryItem) => void;
  removeItem: (id: string) => void;
  setSearch: (q: string) => void;
  setCategoryFilter: (cat: string | null) => void;
  setStatusFilter: (status: string | null) => void;
  filteredItems: () => InventoryItem[];
}

export const useInventoryStore = create<InventoryState>((set, get) => ({
  items: new Map(),
  search: "",
  categoryFilter: null,
  statusFilter: null,

  setItems: (items) =>
    set({
      items: new Map(items.map((i) => [i.id, i])),
    }),

  updateItem: (item) =>
    set((state) => {
      const next = new Map(state.items);
      next.set(item.id, item);
      return { items: next };
    }),

  removeItem: (id) =>
    set((state) => {
      const next = new Map(state.items);
      next.delete(id);
      return { items: next };
    }),

  setSearch: (search) => set({ search }),
  setCategoryFilter: (categoryFilter) => set({ categoryFilter }),
  setStatusFilter: (statusFilter) => set({ statusFilter }),

  filteredItems: () => {
    const { items, search, categoryFilter, statusFilter } = get();
    let result = Array.from(items.values());

    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (i) =>
          i.name.toLowerCase().includes(q) ||
          i.sku.toLowerCase().includes(q) ||
          i.category.toLowerCase().includes(q)
      );
    }

    if (categoryFilter) {
      result = result.filter((i) => i.category === categoryFilter);
    }

    if (statusFilter) {
      result = result.filter((i) => i.status === statusFilter);
    }

    return result;
  },
}));
