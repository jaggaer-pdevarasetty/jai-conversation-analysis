import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ListResponse } from "../services/analysisApi";
import { ReviewerTable } from "./ReviewerTable";

function response(category?: string): ListResponse {
  const all = [
    {
      conversation_id: "11111111-1111-4111-8111-111111111111",
      category: "resolved",
      recommended_next_step: "No action.",
      confidence: "medium",
      status: "analysed",
      overridden: false,
      has_feedback: false,
      metrics: { ttft_ms: 340, input_tokens: 130, output_tokens: 48, prompt_tokens: 120 },
    },
    {
      conversation_id: "66666666-6666-4666-8666-666666666666",
      category: "resolved",
      recommended_next_step: "No action.",
      confidence: "medium",
      status: "analysed",
      overridden: false,
      has_feedback: false,
      // AC-7: missing telemetry
      metrics: { ttft_ms: null, input_tokens: null, output_tokens: null, prompt_tokens: null },
    },
  ];
  const items = category ? all.filter((i) => i.category === category) : all;
  return { items, counts: {}, total: items.length, unanalysed: 2, limit: 50, offset: 0 };
}

jest.mock("../services/analysisApi", () => ({
  fetchAnalysis: jest.fn(async (category?: string) => response(category)),
}));

import { fetchAnalysis } from "../services/analysisApi";

describe("ReviewerTable", () => {
  it("renders analysed conversations by conversation ID (no tenant column)", async () => {
    render(<ReviewerTable />);
    expect(await screen.findByRole("table", { name: "Analysed conversations" })).toBeInTheDocument();
    expect(await screen.findByText("11111111-1111-4111-8111-111111111111")).toBeInTheDocument();
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

  it("filters by category via the labelled control", async () => {
    render(<ReviewerTable />);
    await screen.findByText("11111111-1111-4111-8111-111111111111");
    await userEvent.selectOptions(screen.getByLabelText("Filter by category"), "resolved");
    await waitFor(() => expect(fetchAnalysis).toHaveBeenLastCalledWith("resolved"));
  });
});
