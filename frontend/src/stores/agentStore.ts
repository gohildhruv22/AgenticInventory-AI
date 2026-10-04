import { create } from "zustand";
import type { AgentDecision, PipelineStatus } from "@/types/agent";

interface AgentState {
  decisions: AgentDecision[];
  pipelineStatus: PipelineStatus;
  activeAgent: string | null;

  addDecision: (decision: AgentDecision) => void;
  setDecisions: (decisions: AgentDecision[]) => void;
  setPipelineStatus: (status: PipelineStatus) => void;
  setActiveAgent: (agent: string | null) => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  decisions: [],
  pipelineStatus: {
    active: false,
    current_agent: null,
    progress: 0,
    total_steps: 0,
  },
  activeAgent: null,

  addDecision: (decision) =>
    set((state) => ({
      decisions: [decision, ...state.decisions].slice(0, 100),
    })),

  setDecisions: (decisions) => set({ decisions }),

  setPipelineStatus: (pipelineStatus) =>
    set({
      pipelineStatus,
      activeAgent: pipelineStatus.current_agent,
    }),

  setActiveAgent: (activeAgent) => set({ activeAgent }),
}));
