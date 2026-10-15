import { apiGet, apiSend } from "../../api/client";

// B17 (specs 30, 31): the catalogue and the governed state of an Initiative. The views come from /api/intents/{id}/...; every edit goes through
// the existing module 2 routes (baseline id from the view), so there is one place for each record.
const M2 = "/api/modules/m2_baseline/baselines";
const I = (id: string) => `/api/intents/${encodeURIComponent(id)}`;

export type EntryState = "confirmed" | "draft" | "not_drafted" | "unknown_accepted" | "changed";
export const STATES: EntryState[] = ["confirmed", "draft", "not_drafted", "unknown_accepted", "changed"];

export interface ListRow {
  restricted?: boolean;
  code?: string;
  label: string;
  aliases?: string[];
  owner?: string | null;
  state?: EntryState;
  state_label?: string;
  guessed?: number;
  priority?: string | null;
}
export interface CatalogueList {
  baseline_id: string;
  measures: ListRow[];
  counts: Record<EntryState, number> | null;
  guessed_parts: number | null;
  empty: string | null;
  lens_line: string;
  not_drafted: number;
  waiting: { person: string; codes: string[]; text?: string }[];
  blockers: string[];
  signed: boolean;
}
export interface Owners {
  business: string | null;
  data: string | null;
  source: string | null;
  confirmed: boolean;
}
export interface Entry {
  code: string;
  label: string;
  aliases: string[];
  node: string;
  state: EntryState;
  state_label: string;
  version: number;
  business_definition: string | null;
  owners: Owners;
  sources: { id: string; name: string; owner: string | null }[];
  fields: { id: string; name: string; class: string | null }[];
  personal_class: string | null;
  may_see: string[] | null;
  accepted: { by: string; at: string } | null;
  trail: { v: number; at: string; text: string }[];
  sent_back: { label: string } | null;
  complete: boolean;
  missing: string[];
  can_confirm: boolean;
  priority: string | null;
}

export type Field = "owners" | "classification" | "may_see" | "resolving" | "affects" | "review_date";
export const FIELDS: Field[] = ["owners", "classification", "may_see", "resolving", "affects", "review_date"];
export interface Cell {
  value: unknown;
  mark: "stated" | "guessed" | "unknown";
  by: string;
  from: string;
  at: string;
}
export interface Proposal {
  value: unknown;
  reason: string;
  by: string;
  at: string;
  declined?: { by: string; reason: string };
}
export interface GovernedRow {
  id: string;
  name: string;
  priority: string | null;
  state: Record<Field, Cell> & { history?: Record<string, unknown[]> };
  complete: boolean;
  n: number;
  needs: string[];
  can_confirm: Record<Field, boolean>;
  slots: Record<"business" | "data" | "source", boolean>;
  proposals: Partial<Record<Field, Proposal>>;
  owners: Owners;
}
export interface Governed {
  baseline_id: string;
  measures: GovernedRow[];
  strip: Record<"owned" | "classified" | "may_see_confirmed" | "team_assigned", { n: number; of: number; pct: number }> | null;
  empty: string | null;
  must: { n: number; of: number };
  should: { n: number; of: number };
  not_governed: { id: string; name: string; needs: string[] }[];
  waiting_on: string[];
  refusal: string;
  redrafted?: { id: string; n: number } | null;
}

export const getCatalogue = (intent: string, owner?: string) => apiGet<CatalogueList>(`${I(intent)}/catalogue${owner ? `?owner=${owner}` : ""}`);
export const getEntry = (intent: string, code: string) => apiGet<Entry>(`${I(intent)}/catalogue/entry/${encodeURIComponent(code)}`);
export const getGoverned = (intent: string) => apiGet<Governed>(`${I(intent)}/governed`);
export const redraftGoverned = (intent: string, measure: string) => apiGet<Governed>(`${I(intent)}/governed?redraft=${encodeURIComponent(measure)}`);
export const renameMeasure = (intent: string, code: string, label: string) => apiSend<unknown>("POST", `${I(intent)}/catalogue/measures/${encodeURIComponent(code)}/alias`, { label });
export const confirmField = (baseline: string, measure: string, field: Field, value: unknown) =>
  apiSend<unknown>("POST", `${M2}/${baseline}/governed/${encodeURIComponent(measure)}/confirm`, { field, value });
export const propose = (intent: string, measure: string, field: Field, value: unknown, reason: string) =>
  apiSend<unknown>("POST", `${I(intent)}/governed/${encodeURIComponent(measure)}/propose`, { field, value, reason });
export const withdraw = (intent: string, measure: string, field: Field) => apiSend<unknown>("POST", `${I(intent)}/governed/${encodeURIComponent(measure)}/withdraw`, { field });
export const decide = (intent: string, measure: string, field: Field, decision: "apply" | "decline", reason?: string) =>
  apiSend<unknown>("POST", `${I(intent)}/governed/${encodeURIComponent(measure)}/proposal/${field}/decide`, { decision, reason });
export const sendBack = (baseline: string, measure: string, note: string) => apiSend<unknown>("POST", `${M2}/${baseline}/measures/${encodeURIComponent(measure)}/send-back`, { note });
export const acceptUnknown = (baseline: string, measure: string) => apiSend<unknown>("POST", `${M2}/${baseline}/review/${encodeURIComponent(measure)}/accept`);
export const lensDraft = (baseline: string) => apiSend<unknown>("POST", `${M2}/${baseline}/lens/technical`, {});
export const exportPath = (baseline: string) => `${M2}/${baseline}/catalogue/export`;
