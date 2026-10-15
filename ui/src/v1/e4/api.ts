// E4c: the Action Desk. Routes under /api/v1/cases are served by E4a (and /explain by E4b); the shapes are the real ones (case.real.json, cases.real.json).
import { apiGet, apiSend } from "../../api/client";
import type { Used } from "../teach/api";

export type Materiality = "high" | "medium" | "low";
export type Action = "take" | "explain" | "submit" | "approve" | "send_back" | "dismiss" | "ask_finance";
export interface CaseRow { id: string; number: string; title: string; materiality: Materiality; due: string | null; state: string; amount?: number | null; currency?: string | null;
  /** Closed on the company's day (demo_today when set), decided by the server. */
  closed_today?: boolean }
export interface HistoryEntry { at: string; by: string | null; text: string }
export interface Case extends CaseRow {
  exception_type?: string; description?: string;
  maker_name: string | null; checker_name: string | null; state_label?: string;
  proposal: { text: string; sources: string[] } | null; affects: string[]; history: HistoryEntry[];
  /** What the signed-in person may press, decided by the server (a maker never checks). */
  can: Partial<Record<Action, boolean>>;
  /** True only when the signed-in person is the case owner (an administrator who is not the owner gets false). */
  is_owner?: boolean;
}

/** N1: Tally's account of a case. `chips` are the sources behind a finding: a statement, or a stored fact whose trail can be opened. */
export interface Chip { label: string; kind: string; id: string }
export interface Finding { key: string; text: string; figure: string | null; chips: Chip[] }
export interface Proposal { kind: "explanation" | "next_step"; text: string; note?: string; cause?: string; item_ref?: string; sources?: string[]; who?: string }
export interface Tally {
  proposals?: Proposal[];
  case_id: string; kind: string; summary: string; findings: Finding[]; next_steps: { who: string; text: string }[]; missing: string[];
  worded_by: "model" | "rules"; question: string | null; answer: string | null; used?: Used[];
}

export const MATERIALITY_NAMES: Record<Materiality, string> = { high: "High", medium: "Medium", low: "Low" };
const WEIGHT: Record<Materiality, number> = { high: 0, medium: 1, low: 2 };
/** Materiality first, then the earlier due time; no due time last. */
export const byMaterialityThenDue = (a: CaseRow, b: CaseRow) =>
  WEIGHT[a.materiality] - WEIGHT[b.materiality] || (a.due ?? "9999").localeCompare(b.due ?? "9999");

const c = (id: string) => `/api/v1/cases/${encodeURIComponent(id)}`;
const PATH: Record<Action, string> = { take: "take", explain: "explain", submit: "submit", approve: "approve", send_back: "send_back", dismiss: "dismiss", ask_finance: "ask_finance" };
/** The word the person types goes in the field the server reads for that action. */
const FIELD: Partial<Record<Action, string>> = { send_back: "reason", dismiss: "reason", submit: "explanation", ask_finance: "to", approve: "rationale" };
export const listCases = () => apiGet<{ cases: CaseRow[] }>("/api/v1/cases");
export const getCase = (id: string) => apiGet<Case>(c(id));
export const act = (id: string, action: Action, text = "", code = "") => apiSend<Case>("POST", `${c(id)}/${PATH[action]}`,
  { ...(text && FIELD[action] ? { [FIELD[action]!]: text } : {}), ...(code && action === "submit" ? { code } : {}) });
/** The reason a case closes under once its check is approved (kept on the case; blank means "explained"). */
export const CLOSE_CODES: [string, string][] = [["", "Explained"], ["stale_data", "Stale data, not a real breach"], ["action_agreed", "Real, action agreed"], ["cured", "Cured"]];
export const getTally = (id: string, quick = false) => apiGet<Tally>(`${c(id)}/tally${quick ? "?quick=1" : ""}`);
export const askTally = (id: string, question: string) => apiSend<Tally>("POST", `${c(id)}/ask`, { question });
