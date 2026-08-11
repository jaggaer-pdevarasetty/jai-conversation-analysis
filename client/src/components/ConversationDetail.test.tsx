import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ConversationDetail as Detail } from "../services/analysisApi";
import { ConversationDetail } from "./ConversationDetail";

const record: Detail = {
  conversation_id: "abc123",
  analysis: {
    category: "failed_to_resolve",
    model_category: "failed_to_resolve",
    recommended_next_step: "Improve the password-reset answer.",
    confidence: "high",
    rationale: "The user repeated the same question.",
    status: "analysed",
    override: null,
    analyzed_at: "2026-08-11T00:00:00Z",
    analyzer_version: "vertex:gemini-2.5-flash",
  },
  metrics: { ttft_ms: 11440, input_tokens: 35293, output_tokens: 6186, prompt_tokens: 35293 },
  messages: [
    { id: "m1", role: "user", content: "How do I reset my password?", sequence_num: 1, model: null, created_at: "" },
    { id: "m2", role: "assistant", content: "Go to Settings → Security.", sequence_num: 2, model: "gemini", created_at: "" },
  ],
  feedback: { rating: null, comment: null },
};

const overrideMock = jest.fn(async (_id: string, _category: string, _actor: string) => undefined);
jest.mock("../services/analysisApi", () => ({
  ...jest.requireActual("../services/analysisApi"),
  fetchConversation: jest.fn(async () => record),
  overrideCategory: (...args: [string, string, string]) => overrideMock(...args),
}));

describe("ConversationDetail", () => {
  it("shows transcript, review evidence, confidence and formatted metrics", async () => {
    render(<ConversationDetail id="abc123" initial={record} />);
    expect(screen.getByText("Improve the password-reset answer.")).toBeInTheDocument();
    expect(screen.getByText("High confidence")).toBeInTheDocument();
    expect(screen.getByText("How do I reset my password?")).toBeInTheDocument();
    expect(screen.getByLabelText("Time to first token")).toHaveTextContent("11.4 s");
    expect(screen.getByLabelText("Input tokens")).toHaveTextContent("35,293");
    expect(screen.getByText("The user repeated the same question.")).toBeInTheDocument();
  });

  it("submits a human override", async () => {
    render(<ConversationDetail id="abc123" initial={record} />);
    await userEvent.click(screen.getByLabelText("New category"));
    await userEvent.click(await screen.findByRole("option", { name: "Out of scope" }));
    await userEvent.click(screen.getByRole("button", { name: "Save override" }));
    await waitFor(() => expect(overrideMock).toHaveBeenCalledWith("abc123", "out_of_scope", "reviewer"));
  });
});
