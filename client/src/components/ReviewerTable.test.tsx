import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AnalysisQuery, ListItem, ListResponse } from "../services/analysisApi";
import { ReviewerTable } from "./ReviewerTable";

let mockRegionLoading = false;

jest.mock("./RegionContext", () => ({
  useRegion: () => ({ region: "us", loading: mockRegionLoading }),
}));

function response(params: AnalysisQuery = {}): ListResponse {
  const all: ListItem[] = Array.from({ length: 30 }, (_, index) => ({
    conversation_id: index === 0
      ? "11111111-1111-4111-8111-111111111111"
      : index === 1
        ? "66666666-6666-4666-8666-666666666666"
        : `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
    category: "resolved",
    recommended_next_step: "No action.",
    confidence: "medium",
    status: "analysed",
    overridden: false,
    has_feedback: false,
    metrics: index === 1
      ? { ttft_ms: null, input_tokens: null, output_tokens: null, prompt_tokens: null }
      : { ttft_ms: 340, input_tokens: 130, output_tokens: 48, prompt_tokens: 120 },
    last_message_at: "2026-08-13T18:52:59Z",
    analyzed_at: "2026-08-14T05:43:39Z",
  }));
  let items = params.category ? all.filter((item) => item.category === params.category) : all;
  if (params.query) items = items.filter((item) => item.conversation_id.includes(params.query!) || item.recommended_next_step.includes(params.query!));
  if (params.review_state === "missing_telemetry") items = items.filter((item) => item.metrics.ttft_ms === null);
  const total = items.length;
  const offset = params.offset ?? 0;
  const limit = params.limit ?? 25;
  return {
    items: items.slice(offset, offset + limit),
    counts: { resolved: all.length },
    total,
    unanalysed: 2,
    limit,
    offset,
  };
}

jest.mock("../services/analysisApi", () => ({
  fetchAnalysis: jest.fn(async (params?: AnalysisQuery) => response(params)),
}));

import { fetchAnalysis } from "../services/analysisApi";

const fetchAnalysisMock = fetchAnalysis as jest.MockedFunction<typeof fetchAnalysis>;

describe("ReviewerTable", () => {
  beforeEach(() => {
    mockRegionLoading = false;
    fetchAnalysisMock.mockClear();
  });

  it("loads the latest conversation activity first by default", async () => {
    render(<ReviewerTable />);
    await waitFor(() => expect(fetchAnalysisMock).toHaveBeenCalledWith(expect.objectContaining({ sort: "newest" })));
  });

  it("waits for the saved region before loading data", async () => {
    mockRegionLoading = true;
    const { rerender } = render(<ReviewerTable />);
    expect(fetchAnalysisMock).not.toHaveBeenCalled();
    mockRegionLoading = false;
    rerender(<ReviewerTable />);
    await waitFor(() => expect(fetchAnalysisMock).toHaveBeenCalledWith(expect.objectContaining({ region: "us" })));
  });

  it("renders a searchable review queue by conversation ID (no tenant column)", async () => {
    render(<ReviewerTable />);
    expect(await screen.findByRole("table", { name: "Analysed conversations" })).toBeInTheDocument();
    expect(await screen.findByText("11111111-1111-4111-8111-111111111111")).toBeInTheDocument();
    expect(screen.getByLabelText("Search conversations")).toBeInTheDocument();
    expect(screen.queryByText(/tenant/i)).not.toBeInTheDocument();
  });

  it("shows missing telemetry as 'unavailable', not zero (AC-7)", async () => {
    render(<ReviewerTable />);
    await screen.findByText("66666666-6666-4666-8666-666666666666");
    expect(screen.getAllByText(/unavailable/).length).toBeGreaterThan(0);
  });

  it("surfaces the unanalysed count (AC-9)", async () => {
    render(<ReviewerTable />);
    expect(await screen.findByText(/not yet analysed/)).toBeInTheDocument();
  });

  it("filters by category through the server query", async () => {
    render(<ReviewerTable />);
    await screen.findByText("11111111-1111-4111-8111-111111111111");
    await userEvent.click(screen.getByLabelText("Filter by category"));
    await userEvent.click(await screen.findByRole("option", { name: "JAI resolved user query" }));
    await waitFor(() => expect(fetchAnalysisMock).toHaveBeenLastCalledWith(expect.objectContaining({ category: "resolved", offset: 0 })));
  });

  it("searches the server by conversation ID or recommended action", async () => {
    render(<ReviewerTable />);
    await screen.findByText("11111111-1111-4111-8111-111111111111");
    await userEvent.type(screen.getByLabelText("Search conversations"), "no matching conversation");
    expect(await screen.findByText("No conversations match")).toBeInTheDocument();
    expect(fetchAnalysisMock).toHaveBeenLastCalledWith(expect.objectContaining({ query: "no matching conversation" }));
  });

  it("filters conversations that have missing telemetry", async () => {
    render(<ReviewerTable />);
    await screen.findByText("11111111-1111-4111-8111-111111111111");
    await userEvent.click(screen.getByLabelText("Review state"));
    await userEvent.click(await screen.findByRole("option", { name: "Missing telemetry" }));
    await waitFor(() => expect(fetchAnalysisMock).toHaveBeenLastCalledWith(expect.objectContaining({ review_state: "missing_telemetry" })));
    expect(screen.queryByText("11111111-1111-4111-8111-111111111111")).not.toBeInTheDocument();
    expect(screen.getByText("66666666-6666-4666-8666-666666666666")).toBeInTheDocument();
  });

  it("requests the next page from the server", async () => {
    render(<ReviewerTable />);
    await screen.findByText("Showing 1–25 of 30");
    await userEvent.click(screen.getByRole("button", { name: "Go to next page" }));
    await waitFor(() => expect(fetchAnalysisMock).toHaveBeenLastCalledWith(expect.objectContaining({ limit: 25, offset: 25 })));
    expect(await screen.findByText("Showing 26–30 of 30")).toBeInTheDocument();
  });
});
