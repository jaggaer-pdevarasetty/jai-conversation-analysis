import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Enrichment } from "../services/analysisApi";
import { EnrichmentPanel } from "./EnrichmentPanel";

const base: Enrichment = {
  intent: "knowledge_search",
  secondary_intent: null,
  agent_used: "rag",
  platform: "JI",
  interaction_mode: "Ask",
  response_type: "answer",
  source_confidence: "MEDIUM",
  retrieval_hit: true,
  retrieved_count: 2,
  retrieved_docs: ["cb guide 20260819.docx", "UC Terms.pdf"],
  retrieved_snippets: ["services are procured via the Services form"],
  invocation_prompt: "system: Answer only from context.",
  reasoning_summary: "user asked how to pay for a service",
  frustration_score: 0.1,
  guardrail: null,
  had_error: false,
  turns: 4,
  langsmith_found: true,
};

describe("EnrichmentPanel", () => {
  it("explains when LangSmith details were not captured or no trace matched", () => {
    const { rerender } = render(<EnrichmentPanel enrichment={null} />);
    expect(screen.getByRole("heading", { name: /what the assistant did/i })).toBeInTheDocument();
    expect(screen.getByText(/trace details were not captured when this analysis ran/i)).toBeInTheDocument();
    expect(screen.getByText(/exact lookup failure was not retained/i)).toBeInTheDocument();

    rerender(<EnrichmentPanel enrichment={{ ...base, langsmith_found: false }} />);
    expect(screen.getByText(/no matching LangSmith trace was found/i)).toBeInTheDocument();
    expect(screen.getByText(/configured project and environment returned no root runs/i)).toBeInTheDocument();
  });

  it("shows the agent signals, its reasoning, and the documents used", () => {
    render(<EnrichmentPanel enrichment={base} />);
    expect(screen.getByText(/intent: knowledge_search/)).toBeInTheDocument();
    expect(screen.getByText(/agent: rag/)).toBeInTheDocument();
    expect(screen.getByText(/knowledge base: 2 doc/)).toBeInTheDocument();
    expect(screen.getByText(/What the assistant was thinking/)).toBeInTheDocument();
    expect(screen.getByText(/how to pay for a service/)).toBeInTheDocument();
    expect(screen.getByText(/cb guide 20260819.docx/)).toBeInTheDocument();
  });

  it("reveals the scrubbed invocation prompt on demand (Tier-2)", async () => {
    render(<EnrichmentPanel enrichment={base} />);
    await userEvent.click(screen.getByRole("button", { name: /invocation prompt/i }));
    expect(screen.getByText(/Answer only from context/)).toBeInTheDocument();
  });
});
