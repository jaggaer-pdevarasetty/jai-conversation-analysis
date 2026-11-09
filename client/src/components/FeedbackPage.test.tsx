import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import FeedbackPage from "../../app/feedback/page";
import type { FeedbackListResponse } from "../services/analysisApi";

const mockFetchFeedback = jest.fn();

jest.mock("../services/analysisApi", () => ({
  ...jest.requireActual("../services/analysisApi"),
  fetchFeedback: (...args: unknown[]) => mockFetchFeedback(...args),
}));

jest.mock("./RegionContext", () => ({
  useRegion: () => ({ region: "us", loading: false }),
}));

jest.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

const response: FeedbackListResponse = {
  items: [{
    feedback_id: "4512ec35-9164-4225-a7eb-06c1a26cf652:m1",
    feedback_message_id: "m1",
    conversation_id: "4512ec35-9164-4225-a7eb-06c1a26cf652",
    region: "us",
    category: "negative_feedback",
    model_category: "negative_feedback",
    confidence: "high",
    rating: false,
    comment: "**Broken answer**",
    recommended_next_step: "Fix it",
    why_it_happened: "Missed **context**",
    input_tokens: 10,
    output_tokens: 5,
    analyzed_at: "2026-08-14T05:43:39Z",
    last_message_at: "2026-08-13T18:52:59Z",
    deep: null,
  }],
  total: 1,
  scope_total: 1,
  positive: 0,
  negative: 1,
  negative_outcomes: 1,
  deep_analysed: 0,
  limit: 10,
  offset: 0,
};

describe("FeedbackPage", () => {
  beforeEach(() => {
    mockFetchFeedback.mockReset();
    mockFetchFeedback.mockResolvedValue(response);
  });

  it("loads newest conversation activity first and labels both dates", async () => {
    render(<FeedbackPage />);
    await waitFor(() => expect(mockFetchFeedback).toHaveBeenCalledWith(expect.objectContaining({ sort: "newest" })));
    expect(screen.getByRole("combobox", { name: "Activity period" })).toHaveTextContent("All time");
    expect(screen.getByText(/Last message/)).toBeInTheDocument();
    expect(screen.getByText(/Analysed/)).toBeInTheDocument();
  });

  it("sends filters to the server and renders Markdown fields", async () => {
    render(<FeedbackPage />);
    expect((await screen.findByText("Broken answer")).tagName).toBe("STRONG");
    expect(screen.getByText("US")).toBeInTheDocument();
    expect(screen.getByText("context").tagName).toBe("STRONG");
    await userEvent.click(screen.getByLabelText("Sentiment"));
    await userEvent.click(await screen.findByRole("option", { name: "Negative" }));
    await waitFor(() => expect(mockFetchFeedback).toHaveBeenLastCalledWith(expect.objectContaining({ rating: "negative" })));
  });

  it("filters by tenant and the last seven days", async () => {
    render(<FeedbackPage />);
    await userEvent.type(await screen.findByLabelText("Tenant name"), "Acme");
    await userEvent.click(screen.getByLabelText("Activity period"));
    await userEvent.click(await screen.findByRole("option", { name: "Last 7 days" }));
    await waitFor(() => expect(mockFetchFeedback).toHaveBeenLastCalledWith(expect.objectContaining({ tenant: "Acme", date_range: "last_7_days" })));
  });

  it("requests oldest conversation activity when selected", async () => {
    render(<FeedbackPage />);
    await userEvent.click(await screen.findByLabelText("Sort"));
    await userEvent.click(await screen.findByRole("option", { name: "Oldest feedback" }));
    await waitFor(() => expect(mockFetchFeedback).toHaveBeenLastCalledWith(expect.objectContaining({ sort: "oldest" })));
  });

  it("renders every rated message with platform and interaction mode", async () => {
    const first = {
      ...response.items[0],
      feedback_id: "conversation-1:m1",
      feedback_message_id: "m1",
      comment: "First wrong answer",
      title: "Repeated feedback",
      platform: "JI",
      interaction_mode: "Ask",
      agent_used: "rag",
    };
    const second = {
      ...first,
      feedback_id: "conversation-1:m2",
      feedback_message_id: "m2",
      comment: "Second wrong answer",
    };
    mockFetchFeedback.mockResolvedValueOnce({
      ...response,
      items: [first, second],
      total: 2,
      scope_total: 2,
      negative: 2,
    });

    render(<FeedbackPage />);

    expect(await screen.findByText(/First wrong answer/)).toBeInTheDocument();
    expect(screen.getByText(/Second wrong answer/)).toBeInTheDocument();
    expect(screen.getAllByText("Repeated feedback")).toHaveLength(2);
    expect(screen.getAllByText("JI")).toHaveLength(2);
    expect(screen.getAllByText(/Ask · rag/)).toHaveLength(2);
    expect(screen.getByText(/2 matching feedback messages/i)).toBeInTheDocument();
  });
});
