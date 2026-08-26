import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Enrichment } from "../services/analysisApi";
import { EnrichmentPanel } from "./EnrichmentPanel";

const base: Enrichment = {
  intent: "knowledge_search",
  secondary_intent: null,
  agent_used: "rag",
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
  it("renders nothing when there is no matched LangSmith trace", () => {
    const { container } = render(<EnrichmentPanel enrichment={{ ...base, langsmith_found: false }} />);
    expect(container).toBeEmptyDOMElement();
    const { container: c2 } = render(<EnrichmentPanel enrichment={null} />);
    expect(c2).toBeEmptyDOMElement();
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
