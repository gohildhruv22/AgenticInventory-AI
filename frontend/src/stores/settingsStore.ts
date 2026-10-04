import { create } from "zustand";
import type { EmailConfig, EmailDefaults } from "@/types/settings";
import { api } from "@/services/api";

interface SettingsState {
  emailConfig: EmailConfig | null;
  emailDefaults: EmailDefaults | null;
  isLoading: boolean;
  error: string | null;

  fetchEmailConfig: () => Promise<void>;
  fetchEmailDefaults: () => Promise<void>;
  saveEmailConfig: (data: Partial<EmailConfig> & { smtp_password?: string }) => Promise<void>;
  testEmail: (toEmail: string) => Promise<{ success: boolean; message: string }>;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  emailConfig: null,
  emailDefaults: null,
  isLoading: false,
  error: null,

  fetchEmailConfig: async () => {
    set({ isLoading: true, error: null });
    try {
      const config = await api.get<EmailConfig>("/settings/email");
      set({ emailConfig: config, isLoading: false });
    } catch {
      // 404 means not configured yet — that's OK
      set({ emailConfig: null, isLoading: false });
    }
  },

  fetchEmailDefaults: async () => {
    try {
      const defaults = await api.get<EmailDefaults>("/settings/email/defaults");
      set({ emailDefaults: defaults });
    } catch {
      set({ emailDefaults: null });
    }
  },

  saveEmailConfig: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const config = await api.put<EmailConfig>("/settings/email", data);
      set({ emailConfig: config, isLoading: false });
    } catch (err) {
      set({ isLoading: false, error: (err as Error).message });
      throw err;
    }
  },

  testEmail: async (toEmail: string) => {
    const result = await api.post<{ success: boolean; message: string }>(
      "/settings/email/test",
      { to_email: toEmail }
    );
    return result;
  },
}));
