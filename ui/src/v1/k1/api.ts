// K1: sensitivity, topic and access to library items (sh_platform/v1/k1_routes.py), through the shared client.
import { apiGet, apiSend } from "../../api/client";

export type Sensitivity = "open" | "internal" | "restricted";
export interface Pii { found: boolean; kinds: string[]; where: string[] }
export interface Proposal { sensitivity: Sensitivity; topics: string[]; pii: Pii; by: "rules" | "model" | "person"; message: string; topic_list: string[];
  folder?: string; folder_by?: "rules" | "Jev"; folders?: string[] }  // L3: where it goes
export interface Choice { sensitivity: Sensitivity; topic: string[]; reviewed: boolean; folder?: string; folder_by?: "rules" | "Jev" | "owner" }
export interface AccessRequest {
  id: string; item_id: string; item_name: string; requester: string; to: string; owner_left: boolean; reason: string; at: string;
  state: "requested" | "granted" | "denied" | "revoked"; decided_by: string | null; decision_note: string; expires: string | null;
}
export interface Person { account_id: string; name: string }

export const getProposal = (name: string, data: string, note?: string) => apiSend<Proposal>("POST", "/api/v1/library/proposal", { name, data, note });
export const requestAccess = (id: string, reason: string, iid?: string) =>
  apiSend<AccessRequest>("POST", `/api/v1/library/${encodeURIComponent(id)}/access`, { reason, iid });
export const getAccess = () => apiGet<{ incoming: AccessRequest[]; mine: AccessRequest[] }>("/api/v1/library/access");
export const decide = (id: string, approve: boolean, days: number, note = "") =>
  apiSend<AccessRequest>("POST", `/api/v1/library/access/${encodeURIComponent(id)}`, { approve, days, note });
export const getPeople = () => apiGet<Person[]>("/api/v1/library/people");
export const addGrant = (id: string, account_id: string, days?: number) =>
  apiSend<unknown>("POST", `/api/v1/library/${encodeURIComponent(id)}/grants`, { account_id, days });
export const revokeGrant = (id: string, account_id: string) =>
  apiSend<unknown>("DELETE", `/api/v1/library/${encodeURIComponent(id)}/grants/${encodeURIComponent(account_id)}`);
