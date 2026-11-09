import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ImmediateActionPage from "../../app/immediate-action/page";
import type { ListResponse } from "../services/analysisApi";

const mockFetchAnalysis = jest.fn();

jest.mock("../services/analysisApi", () => ({
  ...jest.requireActual("../services/analysisApi"),
  fetchAnalysis: (...args: unknown[]) => mockFetchAnalysis(...args),
}));

jest.mock("./RegionContext", () => ({
  useRegion: () => ({ region: "us", loading: false }),
}));

const response: ListResponse = {
  items: [{
    conversation_id: "98aa5b54-3453-4f89-b957-07724f0b5180",
    region: "us",
    tenant_id: "1007",
    tenant_name: "UB Suny",
    title: "Excel analysis approaches",
    category: "failed_to_resolve",
    recommended_next_step: "Remove the internal document.",
    confidence: "medium",
    status: "analysed",
    overridden: false,
    has_feedback: false,
    immediate_attention: true,
    attention_reasons: ["high_frustration", "guardrail_bypass"],
    kb_issue: false,
    guardrail_bypass: true,
    source_code: false,
    metrics: { ttft_ms: null, input_tokens: null, output_tokens: null, prompt_tokens: null },
    analyzed_at: "2026-10-14T00:00:00Z",
  }],
  counts: { failed_to_resolve: 1 },
  total: 1,
  unanalysed: 0,
  limit: 150,
  offset: 0,
  analytics: {
    total_matching: 1,
    immediate_attention: 1,
    kb_issues: 2,
    empty_final_response: 3,
    guardrail_bypass: 1,
    high_frustration: 1,
    ticket_failure: 2,
    rate_limit: 4,
    affected_tenants: 1,
    by_reason: { rate_limit: 4, empty_final_response: 3, ticket_failure: 2, guardrail_bypass: 1, high_frustration: 1 },
    top_reasons: [
      { reason: "rate_limit", count: 4 },
      { reason: "empty_final_response", count: 3 },
      { reason: "ticket_failure", count: 2 },
    ],
    by_region: { us: 1 },
    kb_by_day: [{ date: "2026-10-14", count: 2 }],
    kb_by_day_region: [{ date: "2026-10-14", us: 1, eu: 1, uk: 0, total: 2 }],
    kb_by_tenant: [{ tenant_id: "1007", tenant_name: "UB Suny", region: "us", count: 2 }],
    serious_by_day: [{ date: "2026-10-14", empty_final_response: 3, guardrail_bypass: 1, high_frustration: 1, ticket_failure: 2, other_serious: 1, total: 8 }],
    top_tenants: [{
      tenant_id: "1007",
      tenant_name: "UB Suny",
      region: "us",
      immediate_attention: 1,
      kb_issues: 2,
      empty_final_response: 3,
      guardrail_bypass: 1,
      total: 3,
    }],
  },
};

describe("ImmediateActionPage", () => {
  beforeEach(() => mockFetchAnalysis.mockReset().mockResolvedValue(response));

  it("loads urgent conversations with 150 rows/page, tenant name & ID, and trend charts", async () => {
    render(<ImmediateActionPage />);
    await waitFor(() => expect(mockFetchAnalysis).toHaveBeenCalledWith(expect.objectContaining({
      region: "us",
      review_state: "immediate_attention",
      include_analytics: true,
      limit: 150,
    })));
    expect(await screen.findByText("98aa5b54-3453-4f89-b957-07724f0b5180")).toBeInTheDocument();
    expect(screen.getByText("UB Suny")).toBeInTheDocument();
    expect(screen.getByText("ID: 1007")).toBeInTheDocument();
    expect(screen.getByText("Guardrail Bypass")).toBeInTheDocument();
    expect(screen.getByText("High Frustration")).toBeInTheDocument();
    expect(screen.getByText("Serious issues trend (1)")).toBeInTheDocument();
    expect(screen.getByText("Top 3 serious issues (last 15 days · count-wise)")).toBeInTheDocument();
    expect(screen.getByText("Ticket not created: 2")).toBeInTheDocument();
    expect(screen.getByText("#1 Rate Limit: 4")).toBeInTheDocument();
    expect(screen.getByText("#2 Empty Final Response: 3")).toBeInTheDocument();
    expect(screen.getByText("#3 Ticket Not Created: 2")).toBeInTheDocument();
    expect(screen.getByText(/Empty 3 · Bypass 1 · Ticket 2 · Other 2/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Per day · region" }));
    expect(screen.getByText("US 1 · EU 1 · UK 0")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Per tenant" }));
    expect(screen.getByText(/ID: 1007 · US/)).toBeInTheDocument();
  });

  it("filters by attention reason and tenant", async () => {
    render(<ImmediateActionPage />);
    await screen.findByText("98aa5b54-3453-4f89-b957-07724f0b5180");
    await userEvent.type(screen.getByLabelText("Tenant name or ID"), "UB Suny");
    await userEvent.click(screen.getByLabelText("Attention reason"));
    await userEvent.click(await screen.findByRole("option", { name: "Rate Limit" }));
    await waitFor(() => expect(mockFetchAnalysis).toHaveBeenLastCalledWith(expect.objectContaining({
      attention_reason: "rate_limit",
      tenant: "UB Suny",
      limit: 150,
    })));
  });
});
