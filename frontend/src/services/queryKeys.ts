export const queryKeys = {
  auth: {
    me: ["auth", "me"] as const,
  },
  inventory: {
    all: ["inventory"] as const,
    list: (params?: Record<string, unknown>) =>
      ["inventory", "list", params] as const,
    detail: (id: string) => ["inventory", id] as const,
  },
  decisions: {
    all: ["decisions"] as const,
    list: (params?: Record<string, unknown>) =>
      ["decisions", "list", params] as const,
    detail: (id: string) => ["decisions", id] as const,
  },
  deliveries: {
    all: ["deliveries"] as const,
    list: (params?: Record<string, unknown>) =>
      ["deliveries", "list", params] as const,
    detail: (id: string) => ["deliveries", id] as const,
    timeline: (id: string) => ["deliveries", id, "timeline"] as const,
  },
  reports: {
    all: ["reports"] as const,
    list: (params?: Record<string, unknown>) =>
      ["reports", "list", params] as const,
    detail: (id: string) => ["reports", id] as const,
    dashboard: ["reports", "dashboard"] as const,
  },
  settings: {
    email: ["settings", "email"] as const,
  },
  pipeline: {
    all: ["pipeline"] as const,
    history: ["pipeline", "history"] as const,
    status: (id: string) => ["pipeline", id, "status"] as const,
  },
} as const;
