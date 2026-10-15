// Typed calls for the plan screen (M3-P04). Everything goes through the shared client; nothing here calls fetch.
import { apiGet, apiSend } from "../../../api/client";
import { BASE } from "../api";

export type Band = "now" | "next" | "later";
export type Effort = "small" | "medium" | "large";
export type RiskState = "open" | "accepted" | "sent_back" | "rechecked";

export interface RiskRow {
  id: string;
  kind: "risk" | "ambiguity" | "unknown";
  text: string;
  /** True when the viewer may not see the measure it is about: the text is only "A restricted measure". */
  restricted: boolean;
  measures: { id: string; name: string }[];
  pain_points: { id: string; title: string }[];
  state: RiskState;
  decision: { decision: "accepted" | "sent_back" | null; note: string | null; reason: string | null; by: string | null; at: string | null } | null;
}
export interface RisksView {
  risks: RiskRow[];
  counts: Record<RiskState, number>;
  signed: boolean;
  locked: boolean;
  ready: boolean;
  /** After "accept all remaining": how many were accepted and how many stayed because the viewer may not see them. */
  accepted?: number;
  left_hidden?: number;
}

export interface EditRecord {
  value: unknown;
  reason: string;
  by: string;
  at: string;
}
export interface PlanItem {
  key: string;
  band: Band;
  restricted: boolean;
  summary: string;
  measures: { id: string; name: string }[];
  pain_points: { id: string; title: string }[];
  effort?: Effort;
  effort_label?: string;
  team: string[];
  blocked_by: string[];
  who_unblocks: string[];
  date?: string | null;
  date_text?: string;
  why_descoped?: string | null;
  covered_by?: string | null;
  covered_text?: string;
  edits?: Record<string, EditRecord>;
  proposals?: Record<string, unknown>;
  stale?: boolean;
}
export interface Signature {
  slot: string;
  label: string;
  name: string;
  at: string;
  restricted_covered: number;
  note: string | null;
}
export interface PlanView {
  drafted: boolean;
  /** Plain words about what the plan is waiting for, or null. */
  waiting: string | null;
  bands_info: Record<Band, { label: string; weeks: string }>;
  bands: Record<Band, PlanItem[]>;
  drafted_at: string | null;
  signed_at: string | null;
  outcome_id: string | null;
  signatures: Signature[];
  waiting_for: string[];
  risks_undecided: number;
  can_sign: boolean;
  restricted_hidden: number;
  effort: Record<Effort, string>;
  viewer: { name: string; slot: "sponsor" | "head_of_data" | null; can_edit: boolean };
}
export interface NextSentence {
  step: string | null;
  done: boolean;
  sentence: string;
}
export interface ItemChange {
  key: string;
  reason: string;
  band?: Band;
  effort?: Effort;
  team?: string;
  date?: string;
  covered_by?: string;
}

const A = (id: string) => `${BASE}/assessments/${id}`;
export const getPlan = (id: string) => apiGet<PlanView>(`${A(id)}/plan`);
export const draftAgain = (id: string) => apiSend<PlanView>("POST", `${A(id)}/plan/draft`);
export const editItem = (id: string, change: ItemChange) => apiSend<PlanView>("PUT", `${A(id)}/plan/item`, change);
export const getRisks = (id: string) => apiGet<RisksView>(`${A(id)}/risks`);
export const decideRisk = (id: string, risk: string, body: { decision: "accepted" | "sent_back"; note?: string; reason?: string }) =>
  apiSend<RisksView>("POST", `${A(id)}/risks/${risk}/decision`, body);
export const acceptAll = (id: string, note?: string) => apiSend<RisksView>("POST", `${A(id)}/risks/accept-all`, { note });
export const signPlan = (id: string) => apiSend<PlanView>("POST", `${A(id)}/plan/sign`);
export const getNext = (id: string) => apiGet<NextSentence>(`${A(id)}/next`);
