// Typed calls for Span's panels (sh_platform/build/agents/routes.py and sh_platform/build/proposals.py). Plain wrappers over apiGet/apiSend.
import { apiGet, apiSend } from "../../api/client";

export type DraftState = "none" | "drafting" | "ready" | "failed" | "fallback" | "filed";
export interface ModelDraft {
  state: DraftState; id?: string; message?: string | null; fallback?: boolean; rounds?: number; errors?: string[]; open_questions?: string[];
  counts?: { label: string; value?: number; text?: string }[]; filed?: { by: string; at: string; version: number; skipped: string[] };
}
export interface Proposal {
  id: string; kind: string; by_agent: string; to: string | null; to_role: string; title: string; what: string; why: string; technique?: string | null;
  evidence?: { counts?: { label: string; value: number }[]; fields?: string[] }; impact?: { contracts?: string[]; marts?: string[]; dashboards?: string[] };
  alternatives?: { option: string; why_not: string }[]; effort?: string | null; state: "proposed" | "accepted" | "declined" | "asked" | "superseded";
  thread?: { by: string; text: string }[]; can_decide: boolean; outside_note?: string | null;
}
export interface ProposalList { proposals?: Proposal[]; empty?: string | null }
export interface Review { proposals: Proposal[]; fallback: boolean; message: string | null }
export interface DesignLine { text: string; mark: "guessed" | "stated"; by?: string }
export interface DesignDoc {
  doc: { version: number; state: "draft" | "signed"; sections: Record<string, DesignLine[]>; signed_by?: { name: string; at: string }[] } | null;
  diagrams?: Record<string, string>; diagram_errors?: string[]; fallback?: boolean; message?: string | null; empty?: string | null; can_edit?: boolean;
}
export type SpecKind = "current" | "target" | "delta";

const B = "/api/company/build";
export const modelDraftPath = `${B}/span/model-draft`;
export const proposalsPath = `${B}/proposals`;
export const designPath = `${B}/design`;
export const designDownload = `${B}/design/download`;
export const specDownload = (kind: SpecKind) => `${B}/design/spec?kind=${kind}`;

export const getModelDraft = () => apiGet<ModelDraft>(modelDraftPath);
export const askModel = (changes: string) => apiSend<ModelDraft>("POST", modelDraftPath, { changes });
export const fileModel = (id: string) => apiSend<ModelDraft>("POST", `${modelDraftPath}/${encodeURIComponent(id)}/file`);
export const review = () => apiSend<Review>("POST", `${B}/span/review`, {});
export const accept = (id: string) => apiSend<Proposal>("POST", `${proposalsPath}/${id}/accept`);
export const decline = (id: string, reason: string) => apiSend<Proposal>("POST", `${proposalsPath}/${id}/decline`, { reason });
export const askQuestion = (id: string, text: string) => apiSend<Proposal>("POST", `${proposalsPath}/${id}/ask`, { text });
export const redraft = () => apiSend<{ state: string; message: string }>("POST", `${designPath}/redraft`);
export const uploadSpec = (kind: SpecKind, spec: unknown) => apiSend<{ kind: SpecKind }>("PUT", `${designPath}/spec`, { kind, spec });
export const getDesign = () => apiGet<DesignDoc>(designPath);
