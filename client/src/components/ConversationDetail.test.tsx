import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderToString } from "react-dom/server";
import { fetchConversation, type ConversationDetail as Detail } from "../services/analysisApi";
import { ConversationDetail } from "./ConversationDetail";
import { MarkdownContent } from "./MarkdownContent";

const record: Detail = {
  conversation_id: "abc123",
  source: { tenant_name: "Acme Corp", user_name: "jdoe", created_at: "2026-08-10T00:00:00Z", last_message_at: "2026-08-10T01:00:00Z" },
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
  deep: null,
  metrics: { ttft_ms: 11440, input_tokens: 35293, output_tokens: 6186, prompt_tokens: 35293 },
  messages: [
    { id: "m1", role: "user", content: "How do I reset my password?", sequence_num: 1, model: null, created_at: "" },
    { id: "m2", role: "assistant", content: "Go to **Settings**:\n\n1. Open Security.\n2. Choose Password.\n\n| Requisition Number | Status |\n| ---: | --- |\n| 3917582 | Pending |", sequence_num: 2, model: "gemini", created_at: "" },
  ],
  feedback: { rating: null, comment: null, message_id: null },
};

const overrideMock = jest.fn(async (_id: string, _category: string, _actor: string) => undefined);
jest.mock("../services/analysisApi", () => ({
  ...jest.requireActual("../services/analysisApi"),
  fetchConversation: jest.fn(async () => record),
  overrideCategory: (...args: [string, string, string]) => overrideMock(...args),
}));

const fetchConversationMock = fetchConversation as jest.MockedFunction<typeof fetchConversation>;

describe("ConversationDetail", () => {
  beforeEach(() => fetchConversationMock.mockReset().mockResolvedValue(record));
  it("shows transcript, review evidence, confidence and formatted metrics", async () => {
    render(<ConversationDetail id="abc123" initial={record} />);
    // Recommended action panel (mirrors the feedback view) holds the step + rationale.
    expect(screen.getByLabelText("Recommended action")).toBeInTheDocument();
    // Conversation context panel (tier-1) shows source metadata.
    expect(screen.getByLabelText("Conversation context")).toHaveTextContent("Acme Corp");
    expect(screen.getByText("Improve the password-reset answer.")).toBeInTheDocument();
    expect(screen.getByText("High confidence")).toBeInTheDocument();
    expect(screen.getByText("How do I reset my password?")).toBeInTheDocument();
    expect(screen.getByLabelText("Time to first token")).toHaveTextContent("11.4 s");
    expect(screen.getByLabelText("Input tokens")).toHaveTextContent("35,293");
    // Total tokens = input + output (replaces the redundant "Prompt tokens" card).
    expect(screen.getByLabelText("Total tokens")).toHaveTextContent("41,479");
    expect(screen.queryByLabelText("Prompt tokens")).not.toBeInTheDocument();
    expect(screen.getByText("The user repeated the same question.")).toBeInTheDocument();
    expect(screen.getByText("Settings").tagName).toBe("STRONG");
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Requisition Number" })).toBeInTheDocument();
    expect(screen.queryByText(/\*\*Settings\*\*/)).not.toBeInTheDocument();
  });

  it("shows Total tokens as unavailable when one half is missing (never substitutes 0)", () => {
    const partial = { ...record, metrics: { ...record.metrics, output_tokens: null } };
    render(<ConversationDetail id="abc123" initial={partial} />);
    expect(screen.getByLabelText("Total tokens")).toHaveTextContent("unavailable");
  });

  it("shows per-message generation telemetry under assistant messages (FR-4 full record)", () => {
    const withTelemetry: Detail = {
      ...record,
      messages: [
        ...record.messages,
        {
          id: "m3",
          role: "assistant",
          content: "Second answer",
          sequence_num: 3,
          model: "gemini",
          created_at: "",
          input_tokens: 130,
          output_tokens: 48,
          prompt_tokens: 120,
          ttft_ms: 340,
        },
      ],
    };
    render(<ConversationDetail id="abc123" initial={withTelemetry} />);
    // captured values render under the generated message…
    expect(screen.getByText("TTFT 340 ms · in 130 tk · out 48 tk · prompt 120 tk")).toBeInTheDocument();
    // …and a generated message WITHOUT telemetry reads "unavailable", never 0 (AC-7)
    expect(screen.getByText("Telemetry unavailable")).toBeInTheDocument();
  });

  it("shows the full override audit trail, oldest first, with old-to-new transitions", () => {
    const withHistory: Detail = {
      ...record,
      analysis: {
        ...record.analysis,
        override: { category: "out_of_scope", actor: "reviewer-b", at: "2026-08-11T02:00:00Z", previous_category: "negative_feedback" },
        override_history: [
          // first transition starts from the model label; later ones from the prior override
          { category: "negative_feedback", actor: "reviewer-a", at: "2026-08-11T01:00:00Z", previous_category: "failed_to_resolve" },
          { category: "out_of_scope", actor: "reviewer-b", at: "2026-08-11T02:00:00Z", previous_category: "negative_feedback" },
        ],
      },
    };
    render(<ConversationDetail id="abc123" initial={withHistory} />);
    expect(screen.getByText("Override audit trail")).toBeInTheDocument();
    expect(screen.getByText(/1\. Failed to resolve → Negative feedback by reviewer-a on/)).toBeInTheDocument();
    expect(screen.getByText(/2\. Negative feedback → Out of scope by reviewer-b on/)).toBeInTheDocument();
    // the current-override alert states the transition too
    expect(screen.getByText(/Overridden by reviewer-b on .*\(Negative feedback → Out of scope\)/)).toBeInTheDocument();
  });

  it("renders Markdown safely during server-side rendering", () => {
    const consoleError = jest.spyOn(console, "error").mockImplementation(() => undefined);
    try {
      renderToString(<MarkdownContent># Heading\n\nParagraph</MarkdownContent>);
      expect(consoleError.mock.calls.flat().join(" ")).not.toContain(":first-child");
    } finally {
      consoleError.mockRestore();
    }
  });

  it("retries a failed detail request", async () => {
    fetchConversationMock.mockRejectedValueOnce(new Error("offline"));
    render(<ConversationDetail id="abc123" />);
    expect(await screen.findByText("Conversation unavailable")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("How do I reset my password?")).toBeInTheDocument();
  });

  it("submits a human override", async () => {
    render(<ConversationDetail id="abc123" initial={record} />);
    await userEvent.click(screen.getByLabelText("New category"));
    await userEvent.click(await screen.findByRole("option", { name: "Out of scope" }));
    await userEvent.click(screen.getByRole("button", { name: "Save override" }));
    await waitFor(() => expect(overrideMock).toHaveBeenCalledWith("abc123", "out_of_scope", "reviewer"));
  });
});
