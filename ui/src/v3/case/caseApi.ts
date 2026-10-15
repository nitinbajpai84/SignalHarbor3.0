// What the case page adds to getCase (api.ts): the fields v3_case_routes.py sends beyond the spec shape, the act call and the talk box.
import { apiSend } from "../../api/client";
import type { Case, CaseEvidence } from "../api";

export type CaseAnswer = "ask" | "note" | "timing" | "resolved" | "dismiss";
export interface Draft { to: string; subject: string; body: string; sent: false }
export interface EvidenceSide extends CaseEvidence { side?: "have" | "missing" }
export interface CaseView extends Omit<Case, "evidence"> {
  evidence: EvidenceSide[]; number?: string | null; kind?: string | null; amount?: number | null; currency?: string | null;
  closed?: boolean; draft?: Draft | null;
}

const base = (id: string) => `/api/v3/cases/${encodeURIComponent(id)}`;
export const actOnCase = (id: string, answer: CaseAnswer, reason?: string) =>
  apiSend<CaseView>("POST", `${base(id)}/act`, reason ? { answer, reason } : { answer });
/** The 2.0 Tally talk route: anyone who can see the case may ask; it changes nothing. */
export const askAboutCase = (id: string, question: string) =>
  apiSend<{ answer: string | null; summary: string }>("POST", `/api/v1/cases/${encodeURIComponent(id)}/ask`, { question });
