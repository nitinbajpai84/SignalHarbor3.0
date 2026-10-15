// E2d: Evidence Explorer. Shapes are the real ones served by e2a/e2b/e2c routes through sh_platform/v1/e2_screen.py (detail.real.json); see docs/plan/v2-landings/E2d.md.
import { apiGet, apiSend } from "../../api/client";

export interface DocRow { id: string; title: string; instrument_name: string; valuation_date: string; received_at: string; label: "Current" | "Superseded"; }
export interface DocVersion {
  id: string; label: "Current" | "Superseded"; received_at: string; status_label: string; // status_label as printed: Estimate, Final
  value_text: string; page: number | null; line: number | null; excerpt: string; file_url: string;
}
export interface Field {
  id: string; field: string; original: string | null; amended: string | null; confidence: number;
  state: "waiting" | "confirmed" | "corrected" | "rejected"; page: number | null; line: number | null;
}
export interface Match { identifier_id: string; source_name: string; instrument_name: string | null; status: "approved" | "proposed" | "unknown"; can_approve: boolean }
export interface DocDetail {
  id: string; instrument_name: string; valuation_date: string; versions: DocVersion[]; fields: Field[]; match: Match | null; can_review: boolean;
}

export const listDocuments = () => apiGet<{ documents: DocRow[] }>("/api/v1/evidence/documents");
export const getDocument = (id: string) => apiGet<DocDetail>(`/api/v1/evidence/documents/${encodeURIComponent(id)}`);
const f = (id: string) => `/api/v1/evidence/fields/${encodeURIComponent(id)}`;
export const confirmField = (id: string) => apiSend<Field>("POST", `${f(id)}/confirm`, {});
export const correctField = (id: string, value: string) => apiSend<Field>("POST", `${f(id)}/correct`, { value });
export const approveAlias = (identifierId: string) => apiSend<Match>("POST", `/api/v1/evidence/aliases/${encodeURIComponent(identifierId)}/approve`, {});
