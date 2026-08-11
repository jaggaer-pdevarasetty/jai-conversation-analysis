import { render, screen } from "@testing-library/react";
import { AnalysisQueuePanel } from "./AnalysisQueuePanel";

jest.mock("../services/analysisApi", () => ({
  fetchQueue: jest.fn(async () => ({
    queued: 1,
    in_flight: 1,
    in_flight_or_queued: 2,
    dead_letter: 0,
    capacity: 5000,
    workers: 2,
    started: true,
    limit: 10,
    offset: 0,
    items: [
      { conversation_id: "analysing-id", status: "analysing", attempt: 1, queued_at: "2026-08-11T00:00:00Z" },
      { conversation_id: "queued-id", status: "queued", attempt: 1, queued_at: "2026-08-11T00:00:01Z" },
    ],
  })),
}));

describe("AnalysisQueuePanel", () => {
  it("shows real queued and analysing conversation IDs", async () => {
    render(<AnalysisQueuePanel />);
    expect(await screen.findByText("analysing-id")).toBeInTheDocument();
    expect(screen.getByText("queued-id")).toBeInTheDocument();
    expect(screen.getAllByText("Analysing").length).toBeGreaterThan(0);
    expect(screen.getByText("1 queued")).toBeInTheDocument();
  });
});
