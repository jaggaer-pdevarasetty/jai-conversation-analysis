import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { fetchPending, triggerSweep, type PendingResponse } from "../services/analysisApi";
import { AnalyzeNowButton } from "./AnalyzeNowButton";

jest.mock("../services/analysisApi", () => ({
  fetchPending: jest.fn(),
  triggerSweep: jest.fn(),
}));
let mockEnv = "uit";
jest.mock("./EnvContext", () => ({
  useEnv: () => ({ env: mockEnv, setEnv: () => {}, environments: ["uit", "prod"], loading: false }),
}));
const mockFetch = fetchPending as jest.MockedFunction<typeof fetchPending>;
const mockTrigger = triggerSweep as jest.MockedFunction<typeof triggerSweep>;

describe("AnalyzeNowButton", () => {
  beforeEach(() => {
    mockEnv = "uit";
    mockFetch.mockReset();
    mockTrigger.mockReset();
  });

  it("UIT: fetches, shows the total/feedback/normal breakdown + a Start button, then analyses on Start", async () => {
    const feedbackPending: PendingResponse = {
      count: 1,
      ids: ["a"],
      by_region: { us: 1 },
      items: [],
      negative_feedback_messages: 2,
      negative_by_region: { us: 2 },
      negative_by_mode: { "Deep Research": 2 },
      negative_by_platform: { JI: 2 },
      deep_research_negative: 2,
      average_frustration: 0.84,
      frustration_scored_messages: 2,
      details_complete: true,
      negative_items: [{
        feedback_id: "a:m1",
        conversation_id: "a",
        feedback_message_id: "m1",
        comment: "Factually incorrect",
        feedback_at: "2026-10-01T10:00:00+00:00",
        region: "us",
        tenant_name: "ShopBlue",
        title: "Deep research issue",
        platform: "JI",
        interaction_mode: "Deep Research",
        agent_used: "deep-research",
        frustration_score: 0.84,
      }],
    };
    const allPending: PendingResponse = {
      count: 3,
      ids: ["a", "b", "c"],
      by_region: { us: 2, eu: 1 },
      items: [
        { conversation_id: "a", region: "us", tenant_name: "ShopBlue", title: "Approvals", last_message_at: null },
        { conversation_id: "b", region: "us", tenant_name: "ShopBlue", title: "Invoices", last_message_at: null },
        { conversation_id: "c", region: "eu", tenant_name: "Hitachi", title: "Suppliers", last_message_at: null },
      ],
    };
    mockFetch.mockImplementation((_region, scope) =>
      Promise.resolve(scope === "feedback" ? feedbackPending : allPending),
    );
    mockTrigger.mockResolvedValue("started");
    render(<AnalyzeNowButton />);

    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
    expect(mockFetch).toHaveBeenCalledWith("", "all");
    expect(mockFetch).toHaveBeenCalledWith("", "feedback");
    // "waiting for analysis", NOT "new" — the count is unanalysed conversations of ANY age,
    // not conversations created recently (wording fix: it read like a created-date count).
    expect(await screen.findByText(/waiting for analysis in all regions/i)).toBeInTheDocument();
    expect(screen.getByText(/\(not yet analysed, of any age\)/i)).toBeInTheDocument();
    expect(screen.getByText(/recent chats appear after 5 minutes without a new message/i)).toBeInTheDocument();
    // breakdown: total 3, one feedback conversation, two negative messages, two without feedback
    expect(screen.getByText("Total conversations 3")).toBeInTheDocument();
    expect(screen.getByText("Feedback conversations 1")).toBeInTheDocument();
    expect(screen.getAllByText("Negative messages 2").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Positive messages 0").length).toBeGreaterThan(0);
    expect(screen.getByText("Without feedback 2")).toBeInTheDocument();
    expect(screen.getAllByText("US: 2").length).toBeGreaterThan(0);
    expect(screen.getByText("Deep Research: 2")).toBeInTheDocument();
    expect(screen.getByText("Avg frustration 0.84")).toBeInTheDocument();
    expect(screen.getByText(/Deep research issue/)).toBeInTheDocument();
    expect(screen.getByText(/Deep Research negative feedback/i)).toBeInTheDocument();
    expect(screen.getByText(/2 negative feedback messages came from Deep Research/i)).toBeInTheDocument();
    expect(screen.getByText("Approvals")).toBeInTheDocument();
    const start = await screen.findByRole("button", { name: /start analysis/i });

    await userEvent.click(start);
    expect(mockTrigger).toHaveBeenCalledWith("", "all");
    expect(await screen.findByText(/analysis started/i)).toBeInTheDocument();
  });

  it("makes a bounded preview explicit", async () => {
    const feedbackPending: PendingResponse = { count: 0, ids: [], by_region: {}, items: [] };
    const allPending: PendingResponse = {
      count: 60,
      ids: [],
      by_region: { us: 60 },
      items: [{ conversation_id: "a", region: "us", tenant_name: "ShopBlue", title: "Approvals", last_message_at: null }],
    };
    mockFetch.mockImplementation((_region, scope) =>
      Promise.resolve(scope === "feedback" ? feedbackPending : allPending),
    );
    render(<AnalyzeNowButton />);
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
    expect(await screen.findByText("Showing newest 1 of 60 conversations.")).toBeInTheDocument();
  });

  it("UIT: offers no Start button when there is nothing waiting for analysis", async () => {
    mockFetch.mockResolvedValue({ count: 0, ids: [], by_region: {}, items: [] });
    render(<AnalyzeNowButton />);
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
    expect(await screen.findByText(/everything currently eligible is already analysed/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start analysis/i })).not.toBeInTheDocument();
    expect(mockTrigger).not.toHaveBeenCalled();
  });

  it("shows an error when the fetch fails", async () => {
    mockFetch.mockRejectedValue(new Error("network"));
    render(<AnalyzeNowButton />);
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
    expect(await screen.findByText(/couldn't fetch conversations/i)).toBeInTheDocument();
  });

  it("PROD: shows feedback + all sections with separate buttons; feedback button sweeps feedback only", async () => {
    mockEnv = "prod";
    mockFetch.mockImplementation((_region, scope) =>
      Promise.resolve(
        scope === "feedback"
          ? {
              count: 5,
              ids: [],
              by_region: { us: 5 },
              items: [],
              feedback_messages: 8,
              positive_feedback_messages: 5,
              negative_feedback_messages: 3,
              positive_feedback_conversations: 2,
              negative_feedback_conversations: 3,
              negative_by_region: { us: 3 },
              negative_by_mode: { "Deep Research": 2, Ask: 1 },
              negative_by_platform: { JI: 3 },
              deep_research_negative: 2,
              average_frustration: 0.72,
              frustration_scored_messages: 3,
              negative_items: [],
              details_complete: true,
            }
          : { count: 20, ids: [], by_region: { us: 20 }, items: [], analysis_window_days: 15 },
      ),
    );
    mockTrigger.mockResolvedValue("started");
    render(<AnalyzeNowButton />);

    await userEvent.click(screen.getByRole("button", { name: /^analyze$/i }));
    // both scopes fetched
    expect(mockFetch).toHaveBeenCalledWith("", "feedback");
    expect(mockFetch).toHaveBeenCalledWith("", "all");
    // two sections + warning on "all"
    expect(await screen.findByText(/with user feedback are not analyzed/i)).toBeInTheDocument();
    expect(screen.getByText(/analyzes/i)).toBeInTheDocument(); // warning text
    expect(
      screen.getByText(
        (_content, node) =>
          node?.textContent === "3 negative rated messages waiting for analysis (5 positive messages across 5 feedback conversations).",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Feedback convos 5")).toBeInTheDocument();
    expect(screen.getByText("Negative convos 3")).toBeInTheDocument();
    expect(screen.getByText("Positive-only convos 2")).toBeInTheDocument();
    expect(screen.getAllByText("Positive messages 5").length).toBeGreaterThan(0);
    expect(screen.getByText("Total conversations 20")).toBeInTheDocument();
    expect(screen.getByText("Without feedback 15")).toBeInTheDocument();
    expect(screen.getByText("US: 3")).toBeInTheDocument();
    expect(screen.getByText("Deep Research: 2")).toBeInTheDocument();
    expect(screen.getByText("Ask: 1")).toBeInTheDocument();
    expect(screen.getByText("Avg frustration 0.72")).toBeInTheDocument();
    expect(screen.getByText(/2 negative feedback messages came from Deep Research/i)).toBeInTheDocument();
    expect(screen.getByText(/only conversations active in the last 15 days/i)).toBeInTheDocument();
    expect(screen.getByText(/older history is excluded/i)).toBeInTheDocument();
    const feedbackBtn = screen.getByRole("button", { name: /analyze feedback/i });
    expect(screen.getByRole("button", { name: /analyze all/i })).toBeInTheDocument();

    await userEvent.click(feedbackBtn);
    expect(mockTrigger).toHaveBeenCalledWith("", "feedback");
    expect(await screen.findByText(/analysis started/i)).toBeInTheDocument();
  });
});
