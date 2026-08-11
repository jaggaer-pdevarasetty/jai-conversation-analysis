import { API_BASE } from "../config";

export interface Metrics {
  ttft_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  prompt_tokens: number | null;
}

export interface Signals {
  feedback: "positive" | "negative" | null;
  repeated_prompts: boolean;
  abandoned: boolean;
  error: boolean;
  out_of_scope_intent: boolean;
  frustrated: boolean;
}

export interface ListItem {
  conversation_id: string;
  category: string;
  model_category?: string;
  recommended_next_step: string;
  confidence: string;
  status: string;
  overridden: boolean;
  has_feedback: boolean;
  metrics: Metrics;
  analyzed_at?: string;
}

export interface ListResponse {
  items: ListItem[];
  counts: Record<string, number>;
  total: number;
  unanalysed: number;
  limit: number;
  offset: number;
}

export interface RunSummary {
  run_id: string;
  started_at: string;
  completed_at: string;
  analysed: number;
  failed: number;
  skipped: number;
  unanalysed: number;
}

export interface Message {
  id: string;
  role: string;
  content: string;
  sequence_num: number;
  model: string | null;
  created_at: string;
}

export interface ConversationDetail {
  conversation_id: string;
  analysis: {
    category: string;
    model_category: string;
    recommended_next_step: string;
    confidence: string;
    rationale: string;
    signals?: Signals;
    status: string;
    override: { category: string; actor: string; at: string } | null;
    run_id?: string;
    analyzed_at: string;
    analyzer_version?: string;
  };
  metrics: Metrics;
  messages: Message[];
  feedback: { rating: boolean | null; comment: string | null };
}

export const CATEGORIES = [
  "resolved",
  "failed_to_resolve",
  "positive_feedback",
  "negative_feedback",
  "out_of_scope",
] as const;

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Analysis API responded ${res.status}`);
  }
  return (await res.json()) as T;
}

/** Fetch analysed conversations from the FastAPI server (optionally filtered). */
export async function fetchAnalysis(category?: string): Promise<ListResponse> {
  const url = new URL(`${API_BASE}/api/analysis/conversations`);
  url.searchParams.set("limit", "200");
  if (category) url.searchParams.set("category", category);
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`Analysis API responded ${res.status}`);
  return (await res.json()) as ListResponse;
}

export const fetchLatestRun = () => getJson<RunSummary>("/api/analysis/runs/latest");

/** Fetch the full de-identified record for one conversation (FR-4). */
export async function fetchConversation(id: string): Promise<ConversationDetail> {
  return getJson<ConversationDetail>(`/api/analysis/conversations/${encodeURIComponent(id)}`);
}

/** On-demand (re)analyse one conversation now (capped server-side per day). */
export async function analyzeConversation(id: string): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/analysis/conversations/${encodeURIComponent(id)}/analyze`,
    { method: "POST" },
  );
  if (!res.ok) throw new Error(`Analyse failed: ${res.status}`);
}

/** Human override of the category (audited). */
export async function overrideCategory(id: string, category: string, actor: string): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/analysis/conversations/${encodeURIComponent(id)}/override`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category, actor }),
    },
  );
  if (!res.ok) throw new Error(`Override failed: ${res.status}`);
}
