import { API_BASE } from "../config";
import { withEnv } from "./env";

export interface Overview {
  region?: string | null;
  tenants: number;
  users: number;
  conversations: number;
  analysed: number;
  unanalysed: number;
  counts: Record<string, number>;
  telemetry_complete: number;
  telemetry_total: number;
}
export interface RegionInfo {
  label: string;
  reachable: boolean | null;
  counts: Record<string, number>;
  error: string | null;
}
export interface EAInfo {
  key: string;
  label: string;
  product: string; // JI / JA
  status: string; // active / blocked
  privacy: string; // non-empty => privacy/compliance-sensitive (e.g. ENEL RoPA/ISO 42001)
  privacy_sensitive: boolean;
}
export interface Tenant {
  tenant_id: string;
  name: string;
  conversations: number;
  users: number;
  ea?: EAInfo | null; // Early Access customer badge (mirrors Confluence roster)
}
export interface TenantUser {
  user_id: string;
  user_name: string;
  role: string | null;
  conversations: number;
}
export interface UserConversation {
  conversation_id: string;
  title: string | null;
  message_count: number | null;
  last_message_at: string | null;
  analysed: boolean;
  status: "analysed" | "analysing" | "pending";
  category: string | null;
  confidence: string | null;
  recommended_next_step: string | null;
}
export interface UserConversationPage {
  items: UserConversation[];
  total: number;
  limit: number;
  offset: number;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(withEnv(new URL(`${API_BASE}${path}`)).toString());
  if (!res.ok) throw new Error(`API ${res.status}`);
  return (await res.json()) as T;
}

/** `?region=us` when a region is selected, else empty (all regions). */
const rq = (region?: string) => (region ? `?region=${encodeURIComponent(region)}` : "");

export interface EnvInfo {
  env: string;
  regions: { label: string; reachable: boolean | null; counts: Record<string, number>; error: string | null }[];
}
export const fetchEnvironments = () =>
  getJson<{ items: EnvInfo[]; default: string }>("/api/analysis/environments");

export const fetchRegions = () =>
  getJson<{ items: RegionInfo[] }>("/api/analysis/regions").then((d) => d.items);
export const fetchOverview = (region?: string) =>
  getJson<Overview>(`/api/analysis/dashboard/overview${rq(region)}`);
export const fetchTenants = (region?: string) =>
  getJson<{ items: Tenant[] }>(`/api/analysis/dashboard/tenants${rq(region)}`).then((d) => d.items);
export const fetchTenantUsers = (tenantId: string, region?: string) =>
  getJson<{ items: TenantUser[] }>(
    `/api/analysis/dashboard/tenants/${tenantId}/users${rq(region)}`,
  ).then((d) => d.items);
export const fetchUserConversations = (
  tenantId: string,
  userId: string,
  limit = 25,
  offset = 0,
  region?: string,
) =>
  getJson<UserConversationPage>(
    `/api/analysis/dashboard/tenants/${tenantId}/users/${userId}/conversations?limit=${limit}&offset=${offset}${
      region ? `&region=${encodeURIComponent(region)}` : ""
    }`,
  );
