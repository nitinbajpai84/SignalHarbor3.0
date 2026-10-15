// Typed calls for the trial and findings screen (M3-P03). Everything goes through the shared client.
import { apiGet, apiSend } from "../../../api/client";
import { BASE } from "../api";

export type Result = "matches" | "gap" | "cannot";
export type RuleState = "draft" | "checked" | "could_not_compile";
export interface RuleView {
  state: RuleState;
  origin: string | null;
  words: string | null;
  reason: string | null;
  checked_by: string | null;
  auto_checked?: boolean;
}
/** A measure the viewer may not see is only its id, the words "A restricted measure" and the flag. */
export interface TrialRow {
  measure: string;
  name: string;
  restricted: boolean;
  our_figure?: number | null;
  their_figure?: number | null;
  unit?: string | null;
  difference?: number | null;
  relative?: number | null;
  result?: Result;
  likely_reason?: string;
  likely_reason_lens?: string | null;
  missing?: string | null;
  group_note?: string;
  skipped?: Record<string, number>;
  source_note?: string | null;
  rule?: RuleView | null;
}
export interface TrialView {
  measures: TrialRow[];
  compiled: boolean;
  run: boolean;
}
export type Group = "ready" | "unclear" | "unknown";
export interface Finding {
  measure: string;
  name: string;
  group: Group;
  reasons: string[];
  pain_points: { id: string; title: string }[];
  levers: { id: string; title: string }[];
  restricted?: boolean;
}
export interface Risk {
  id: string;
  kind: "risk" | "ambiguity" | "unknown";
  text: string;
  measures: string[];
}
export interface FindingsView {
  built: boolean;
  measures: Record<string, Finding>;
  risks: Risk[];
}

const at = (id: string, tail: string) => `${BASE}/assessments/${id}/${tail}`;
export const getTrial = (id: string) => apiGet<TrialView>(at(id, "trial"));
export const getFindings = (id: string) => apiGet<FindingsView>(at(id, "findings"));
export const compileRules = (id: string) => apiSend<TrialView>("POST", at(id, "trial/compile"));
export const runTrial = (id: string) => apiSend<TrialView>("POST", at(id, "trial/run"));
export const checkRule = (id: string, measure: string) => apiSend<TrialView>("POST", at(id, `trial/rules/${measure}/check`));
