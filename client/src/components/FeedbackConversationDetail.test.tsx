import { render, screen } from "@testing-library/react";
import type { ConversationDetail, FeedbackItem } from "../services/analysisApi";
import { FeedbackConversationDetail } from "./FeedbackConversationDetail";

const deep = {
  what_happened: "The response missed the requested comparison.",
  why_it_happened: "The answer focused on setup instead of the task.",
  how_to_avoid: "Confirm the user's intended action.",
  suggestions: "Improve the comparison guidance.",
  user_remark: "Not useful",
};

const detail: ConversationDetail = {
  conversation_id: "feedback-1",
  source: {
    tenant_id: "t1",
    tenant_name: "Example tenant",
    user_id: "u1",
    user_name: "Reviewer user",
    title: "Compare supplier responses",
    status: "active",
    created_at: "2026-08-11T00:00:00Z",
    last_message_at: "2026-08-11T00:01:00Z",
    message_count: 2,
  },
  analysis: {
    category: "negative_feedback",
    model_category: "negative_feedback",
    recommended_next_step: "Improve the **comparison** answer.",
    confidence: "high",
    rationale: "The user gave negative feedback.",
    status: "analysed",
    override: null,
    run_id: "run-1",
    analyzed_at: "2026-08-11T00:02:00Z",
    analyzer_version: "vertex:test",
  },
  deep,
  metrics: { ttft_ms: 400, input_tokens: 100, output_tokens: 50, prompt_tokens: 90 },
  messages: [
    { id: "m1", role: "user", content: "How do I compare responses?", sequence_num: 1, model: null, created_at: "2026-08-11T00:00:00Z" },
    { id: "m2", role: "assistant", content: "Use **Bid Collector**.", sequence_num: 2, model: "gemini", created_at: "2026-08-11T00:01:00Z" },
  ],
  feedback: { rating: false, comment: "Not useful", message_id: "m2" },
};

const feedback: FeedbackItem = {
  ...detail.source!,
  conversation_id: "feedback-1",
  category: "negative_feedback",
  model_category: "negative_feedback",
  confidence: "high",
  rating: false,
  comment: "Not useful",
  feedback_message_id: "m2",
  recommended_next_step: detail.analysis.recommended_next_step,
  rationale: detail.analysis.rationale,
  why_it_happened: deep.why_it_happened,
  input_tokens: 100,
  output_tokens: 50,
  analyzed_at: detail.analysis.analyzed_at,
  analyzer_version: "vertex:test",
  deep,
};

describe("FeedbackConversationDetail", () => {
  it("shows the full conversation and highlights the exact rated response", () => {
    render(<FeedbackConversationDetail id="feedback-1" initialDetail={detail} initialFeedback={feedback} />);
    expect(screen.getByRole("heading", { name: "Compare supplier responses" })).toBeInTheDocument();
    expect(screen.getByText("How do I compare responses?")).toBeInTheDocument();
    expect(screen.getByText("Rated response")).toBeInTheDocument();
    expect(screen.getAllByText("Not useful").length).toBeGreaterThan(0);
    expect(screen.getByText("Bid Collector").tagName).toBe("STRONG");
    expect(screen.getByText("The answer focused on setup instead of the task.")).toBeInTheDocument();
  });
});
