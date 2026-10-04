import { useEffect, useState } from "react";
import { wsClient } from "@/services/socket";
import { useInventoryStore } from "@/stores/inventoryStore";
import { useAgentStore } from "@/stores/agentStore";

export function useWebSocket() {
  const [status, setStatus] = useState<"connecting" | "connected" | "disconnected">(wsClient.status);
  const updateItem = useInventoryStore((s) => s.updateItem);
  const addDecision = useAgentStore((s) => s.addDecision);
  const setPipelineStatus = useAgentStore((s) => s.setPipelineStatus);

  useEffect(() => {
    wsClient.connect();

    const unsubStatus = wsClient.onStatusChange((s) =>
      setStatus(s as "connecting" | "connected" | "disconnected")
    );

    const unsubMessages = wsClient.subscribe((event, data) => {
      switch (event) {
        case "inventory:update":
          updateItem(data as Parameters<typeof updateItem>[0]);
          break;
        case "agent:decision":
          addDecision(data as Parameters<typeof addDecision>[0]);
          break;
        case "pipeline:progress":
          setPipelineStatus(data as Parameters<typeof setPipelineStatus>[0]);
          break;
      }
    });

    return () => {
      unsubStatus();
      unsubMessages();
    };
  }, [updateItem, addDecision, setPipelineStatus]);

  return { status, isConnected: status === "connected" };
}
