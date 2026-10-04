import { create } from "zustand";
import type { User } from "@/types/settings";
import { api, ApiError } from "@/services/api";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;

  /** Fetch the current user from /auth/me (cookie-based). */
  fetchUser: () => Promise<void>;

  login: (email: string, password: string) => Promise<User>;
  register: (name: string, email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;

  /** Clear local state without calling the server. */
  clear: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: true,
  isAuthenticated: false,

  fetchUser: async () => {
    set({ isLoading: true });
    try {
      const user = await api.get<User>("/auth/me");
      set({ user, isAuthenticated: true, isLoading: false });
    } catch (err) {
      // 401 means no valid session — that's fine
      if (err instanceof ApiError && err.status === 401) {
        set({ user: null, isAuthenticated: false, isLoading: false });
      } else {
        set({ isLoading: false });
      }
    }
  },

  login: async (email, password) => {
    const user = await api.post<User>("/auth/login", { email, password });
    set({ user, isAuthenticated: true });
    return user;
  },

  register: async (name, email, password) => {
    const user = await api.post<User>("/auth/register", { name, email, password });
    set({ user, isAuthenticated: true });
    return user;
  },

  logout: async () => {
    await api.post("/auth/logout");
    set({ user: null, isAuthenticated: false });
  },

  clear: () => set({ user: null, isAuthenticated: false, isLoading: false }),
}));
