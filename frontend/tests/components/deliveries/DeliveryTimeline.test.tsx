/**
 * T034 — Component test for `DeliveryTimeline`.
 *
 * Asserts:
 *   - One row is rendered per supported `event_type`
 *     (`eta_confirmed`, `eta_revised`, `acknowledged`, `at_risk`,
 *      `delivered`, `manual_override`, `note`).
 *   - Supplier excerpt and parsed date are visible for confirmed/revised
 *     entries.
 *   - Entries render in reverse-chronological order (most-recent first).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";

import { DeliveryTimeline } from "@/components/deliveries/DeliveryTimeline";
import type {
  DeliveryTimelineEntry,
  DeliveryTimelineResponse,
} from "@/types/delivery";

// Mock the data hook so we test rendering in isolation.
vi.mock("@/hooks/useDeliveryTimeline", () => ({
  useDeliveryTimeline: vi.fn(),
}));
import { useDeliveryTimeline } from "@/hooks/useDeliveryTimeline";

const EVENT_TYPES = [
  "eta_confirmed",
  "eta_revised",
  "acknowledged",
  "at_risk",
  "delivered",
  "manual_override",
  "note",
] as const;

function makeEntry(
  i: number,
  event_type: DeliveryTimelineEntry["event_type"],
  extra: Partial<DeliveryTimelineEntry> = {},
): DeliveryTimelineEntry {
  // ascending occurred_at by index (later index = newer)
  const occurred = new Date(2024, 0, 1, 0, i).toISOString();
  return {
    id: `entry-${i}`,
    delivery_id: "d-1",
    event_type,
    occurred_at: occurred,
    actor_type: "agent",
    actor_id: "ingestor",
    parsed_date: null,
    confidence: null,
    supplier_excerpt: null,
    source_reply_id: null,
    source_review_id: null,
    note: null,
    created_at: occurred,
    ...extra,
  };
}

function buildResponse(): DeliveryTimelineResponse {
  // Build all 7 variants. Confirmed/revised get excerpts + parsed_date.
  const entries: DeliveryTimelineEntry[] = EVENT_TYPES.map((ev, i) => {
    if (ev === "eta_confirmed") {
      return makeEntry(i, ev, {
        supplier_excerpt: "Confirming shipment will arrive Tuesday.",
        parsed_date: new Date(2024, 1, 6, 10, 0).toISOString(),
        confidence: 92,
      });
    }
    if (ev === "eta_revised") {
      return makeEntry(i, ev, {
        supplier_excerpt: "Revised ETA — delay until Friday due to weather.",
        parsed_date: new Date(2024, 1, 9, 10, 0).toISOString(),
        confidence: 78,
      });
    }
    return makeEntry(i, ev);
  });

  // Backend returns reverse-chronological — mirror that contract here.
  const reversed = [...entries].reverse();
  return { delivery_id: "d-1", entries: reversed };
}

describe("DeliveryTimeline", () => {
  beforeEach(() => {
    vi.mocked(useDeliveryTimeline).mockReturnValue({
      data: buildResponse(),
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useDeliveryTimeline>);
  });

  it("renders one row per event_type variant", () => {
    render(<DeliveryTimeline deliveryId="d-1" />);
    for (const ev of EVENT_TYPES) {
      expect(
        screen.getByTestId(`timeline-row-${ev}`),
      ).toBeInTheDocument();
    }
  });

  it("shows supplier excerpt and parsed date for confirmed/revised entries", () => {
    render(<DeliveryTimeline deliveryId="d-1" />);
    for (const ev of ["eta_confirmed", "eta_revised"] as const) {
      const row = screen.getByTestId(`timeline-row-${ev}`);
      expect(
        within(row).getByTestId("timeline-supplier-excerpt"),
      ).toBeInTheDocument();
      expect(
        within(row).getByTestId("timeline-parsed-date"),
      ).toBeInTheDocument();
    }
  });

  it("renders entries in reverse-chronological order", () => {
    render(<DeliveryTimeline deliveryId="d-1" />);
    const list = screen.getByTestId("delivery-timeline");
    const rows = within(list).getAllByRole("listitem");
    const rendered = rows.map((r) =>
      (r.getAttribute("data-testid") ?? "").replace("timeline-row-", ""),
    );
    const expected = [...EVENT_TYPES].reverse();
    expect(rendered).toEqual(expected);
  });
});
