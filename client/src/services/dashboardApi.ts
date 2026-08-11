import { API_BASE } from "../config";

export interface Overview {
  tenants: number;
  users: number;
  conversations: number;
  analysed: number;
  unanalysed: number;
  counts: Record<string, number>;
}
export interface Tenant {
  tenant_id: string;
  name: string;
  conversations: number;
  users: number;
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
  category: string | null;
  confidence: string | null;
  recommended_next_step: string | null;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return (await res.json()) as T;
}

export const fetchOverview = () => getJson<Overview>("/api/analysis/dashboard/overview");
export const fetchTenants = () =>
  getJson<{ items: Tenant[] }>("/api/analysis/dashboard/tenants").then((d) => d.items);
export const fetchTenantUsers = (tenantId: string) =>
  getJson<{ items: TenantUser[] }>(`/api/analysis/dashboard/tenants/${tenantId}/users`).then(
    (d) => d.items,
  );
export const fetchUserConversations = (tenantId: string, userId: string) =>
  getJson<{ items: UserConversation[] }>(
    `/api/analysis/dashboard/tenants/${tenantId}/users/${userId}/conversations`,
  ).then((d) => d.items);
