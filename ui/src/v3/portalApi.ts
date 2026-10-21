// The family portal client (docs/v3/PROGRAM-GAPS.md W5; routes in sh_platform/v1/v3_portal_routes.py).
import { apiGet, apiSend } from "../api/client";

export interface ShareLine {
  entity: string; code: string; level: "full" | "summary"; value: string | null; your_pct: string | null; your_value: string | null; via: string[];
  portfolios?: { name: string; value: string | null }[];
}
export interface Share { member: string; currency: string; as_of: string; basis: "lookthrough" | "entity"; total: string | null; lines: ShareLine[]; note: string }
export interface PortalNote { headline: string; lines: string[]; as_of: string; text: string }
export interface PortalDoc { id: string; title: string; kind: string; date: string }
export interface Approval { id: string; title: string; detail: string; amount: string | null; currency: string; status: "pending" | "approved" | "declined"; raised_by: string; raised: string; note?: string }
export interface Portal { member: string; share: Share; note: PortalNote; documents: PortalDoc[]; approvals: Approval[] }

export const getPortal = (member?: string) => apiGet<Portal>(`/api/v3/portal${member ? `?member=${encodeURIComponent(member)}` : ""}`);
export const askPortal = (text: string, member?: string) => apiSend<{ answer: string; used: string[] }>("POST", "/api/v3/portal/ask", { text, ...(member ? { member } : {}) });
export const decideApproval = (id: string, approve: boolean, note = "") => apiSend<Approval>("POST", `/api/v3/portal/approvals/${encodeURIComponent(id)}/decide`, { approve, note });
