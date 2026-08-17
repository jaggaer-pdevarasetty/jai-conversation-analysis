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
  last_message_at?: string | null;
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

export interface AnalysisQuery {
  category?: string;
  region?: string;
  query?: string;
  confidence?: string;
  review_state?: string;
  sort?: string;
  limit?: number;
  offset?: number;
}

export interface QueueItem {
  conversation_id: string;
  status: "queued" | "analysing" | "retrying";
  attempt: number;
  queued_at: string;
}

export interface QueueStats {
  queued: number;
  in_flight: number;
  in_flight_or_queued: number;
  dead_letter: number;
  capacity: number;
  workers: number;
  started: boolean;
  items: QueueItem[];
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

export interface DeepAnalysis {
  what_happened: string;
  why_it_happened: string;
  how_to_avoid: string;
  suggestions: string;
  user_remark: string;
}

export interface ConversationSource {
  tenant_id?: string | null;
  tenant_name?: string | null;
  user_id?: string | null;
  user_name?: string | null;
  title?: string | null;
  status?: string | null;
  created_at?: string | null;
  last_message_at?: string | null;
  message_count?: number | null;
}

export interface ConversationDetail {
  conversation_id: string;
  source?: ConversationSource | null;
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
  deep: DeepAnalysis | null;
  metrics: Metrics;
  messages: Message[];
  feedback: { rating: boolean | null; comment: string | null; message_id?: string | null };
}

export interface FeedbackItem extends ConversationSource {
  conversation_id: string;
  category: string;
  model_category?: string;
  confidence: string;
  rating: boolean | null;
  comment: string | null;
  feedback_message_id?: string | null;
  recommended_next_step: string;
  rationale?: string;
  why_it_happened?: string;
  input_tokens?: number | null;
  output_tokens?: number | null;
  analyzed_at?: string;
  analyzer_version?: string;
  deep: DeepAnalysis | null;
}

export interface FeedbackQuery {
  rating?: string;
  category?: string;
  region?: string;
  scope?: string;
  query?: string;
  tenant?: string;
  date_range?: string;
  date_from?: string;
  date_to?: string;
  sort?: string;
  limit?: number;
  offset?: number;
}

export interface FeedbackListResponse {
  items: FeedbackItem[];
  total: number;
  scope_total?: number;
  positive: number;
  negative: number;
  negative_outcomes?: number;
  deep_analysed?: number;
  limit?: number;
  offset?: number;
}

/** Conversations with explicit thumbs feedback + their deep analysis (feedback matters most). */
export async function fetchFeedback(params: FeedbackQuery = {}): Promise<FeedbackListResponse> {
  const url = new URL(`${API_BASE}/api/analysis/feedback`);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") url.searchParams.set(key, String(value));
  });
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`Analysis API responded ${res.status}`);
  return (await res.json()) as FeedbackListResponse;
}

export async function fetchFeedbackConversation(id: string): Promise<ConversationDetail> {
  return fetchConversation(id);
}

export async function fetchFeedbackItem(id: string): Promise<FeedbackItem> {
  const response = await fetchFeedback({ query: id, limit: 1 });
  const item = response.items.find((feedback) => feedback.conversation_id === id);
  if (!item) throw new Error(`No explicit feedback for conversation ${id}`);
  return item;
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
export async function fetchAnalysis(params: AnalysisQuery = {}): Promise<ListResponse> {
  const url = new URL(`${API_BASE}/api/analysis/conversations`);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") url.searchParams.set(key, String(value));
  });
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`Analysis API responded ${res.status}`);
  return (await res.json()) as ListResponse;
}

export const fetchLatestRun = () => getJson<RunSummary>("/api/analysis/runs/latest");
export const fetchQueue = (limit = 25, offset = 0) => getJson<QueueStats>(`/api/analysis/queue?limit=${limit}&offset=${offset}`);

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
