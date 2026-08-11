import { API_BASE } from "../config";

export interface Metrics {
  ttft_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  prompt_tokens: number | null;
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

/** Fetch analysed conversations from the FastAPI server (optionally filtered). */
export async function fetchAnalysis(category?: string): Promise<ListResponse> {
  const url = new URL(`${API_BASE}/api/analysis/conversations`);
  if (category) url.searchParams.set("category", category);
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`Analysis API responded ${res.status}`);
  return (await res.json()) as ListResponse;
}
