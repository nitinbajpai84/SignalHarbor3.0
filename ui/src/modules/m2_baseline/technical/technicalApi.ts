import { apiGet, apiSend } from "../../../api/client";
import { BASE, type Prov } from "../api";

// M2-E1: the technical definition of a measure and the open questions (ambiguities). The server decides what each person may see:
// a part or a question that names something they may not see is left out or withheld.
export type TechPart = "sources" | "tables" | "fields" | "calculation" | "filters" | "grain" | "period" | "currency_basis" | "notes";
export type AmbKind = "definition" | "period" | "currency" | "owner" | "source" | "calculation" | "threshold" | "governance" | "conflict" | "other";
export type AmbStatus = "open" | "settled" | "accepted";
export const AMB_KINDS: AmbKind[] = ["definition", "period", "currency", "owner", "source", "calculation", "threshold", "governance", "conflict", "other"];
export const LINK_PARTS: TechPart[] = ["sources", "tables", "fields"];

export interface TechLink {
  id: string;
  name: string;
}
export interface TechPartView {
  /** What this part said before a person's answer replaced it (oldest first). */
  history?: Prov<string | string[]>[];
  part: TechPart;
  label: string;
  /** Text, or the ids of catalogue rows for sources, tables and fields. Unknown has no value and `from` says what is missing. */
  cell: Prov<string | string[]>;
  links: TechLink[];
  proposal: Prov<string | string[]> | null;
  withheld: boolean;
}
export interface TechKpi {
  kpi_id: string;
  name: string;
  parts: TechPartView[];
  confirmed: { by: string; at: string } | null;
  /** The business definition as text, for the wording a person edits when an answer changes it. */
  definition?: string;
  /** Parts whose confirmation still holds, and the parts that changed since (a change clears only that part's confirmation). */
  confirmed_parts?: string[];
  to_confirm?: string[];
  complete: boolean;
  missing: string[];
  open: number;
  ready: { ready: boolean; reasons: string[]; label: string };
}
export interface Ambiguity {
  id: string;
  kind: AmbKind;
  text: string;
  question: string;
  where: string;
  raised_by: string;
  status: AmbStatus;
  resolution: string | null;
  by: string | null;
  at: string | null;
  /** Lens's proposed answer: a suggestion until a person decides. */
  suggestion?: { value: string; mark: "guessed"; by: string };
  asked?: { owner: string; at: string };
  /** "Re-opened: <why>": the facts behind a settled item changed; what it was before stays in `history`. */
  reopened?: string;
  history?: { status: string; resolution: string | null; by: string | null; at: string | null }[];
  /** The part an answer to this kind of question usually changes; the screen preselects it. */
  suggested_part?: string;
  /** Closed by the code because its cause is gone ("Closed: the catalogue now has it"). */
  auto?: boolean;
  kpi_id: string;
  kpi_name: string;
  owner: string;
  /** Worked out from the catalogue (governance): decided in the governance view, not here. */
  derived: boolean;
}
export interface TechnicalScreen {
  baseline_id: string;
  signed: boolean;
  lens_available: boolean;
  kpis: TechKpi[];
  ambiguities: Ambiguity[];
  counts: { all: number; open: number; settled: number; accepted: number };
  summary: { measures: number; drafted: number; ready: number; open: number };
  lens_note?: string;
  outcome?: string;
  changed?: string | null;
  asked?: { owner: string; email: { subject: string; body: string }; link_path: string | null };
}

const B = (id: string) => `${BASE}/baselines/${encodeURIComponent(id)}`;
const K = (id: string, kpi: string) => `${B(id)}/kpis/${encodeURIComponent(kpi)}`;
export const getTechnical = (id: string) => apiGet<TechnicalScreen>(`${B(id)}/technical`);
export const putPart = (id: string, kpi: string, part: TechPart, value: string | string[], mark: "stated" | "guessed" | "unknown" = "stated") =>
  apiSend<TechnicalScreen>("PUT", `${K(id, kpi)}/technical`, { part, value, mark });
export const usePart = (id: string, kpi: string, part: TechPart) => apiSend<TechnicalScreen>("POST", `${K(id, kpi)}/technical/use`, { part });
/** The technical definitions of the measures the signed-in person is the named data owner of, whatever their role (nothing else of the baseline). */
export const getMyTechnical = (id: string) => apiGet<{ baseline_id: string; signed: boolean; kpis: TechKpi[] }>(`${B(id)}/my-technical`);
export const confirmTechnical = (id: string, kpi: string) => apiSend<TechnicalScreen>("POST", `${K(id, kpi)}/technical/confirm`);
export const lensTechnical = (id: string, kpiIds?: string[], retry = false) =>
  apiSend<TechnicalScreen>("POST", `${B(id)}/lens/technical`, { kpi_ids: kpiIds, ...(retry ? { retry: true } : {}) });
export const redraftTechnical = (id: string, kpi: string, instruction: string) =>
  apiSend<TechnicalScreen>("POST", `${B(id)}/lens/technical/redraft`, { kpi_id: kpi, instruction });
/** The answer is recorded on the question. Only with a `part` (and the person's own `wording` for it) does a definition change. */
export const answerAmbiguity = (id: string, kpi: string, amb: string, resolution: string, part?: string, wording?: string) =>
  apiSend<TechnicalScreen>("POST", `${K(id, kpi)}/ambiguities/${encodeURIComponent(amb)}/answer`, part ? { resolution, part, wording } : { resolution });
export const askOwner = (id: string, kpi: string, amb: string) => apiSend<TechnicalScreen>("POST", `${K(id, kpi)}/ambiguities/${encodeURIComponent(amb)}/ask`, {});
export const acceptAmbiguity = (id: string, kpi: string, amb: string, reason: string) =>
  apiSend<TechnicalScreen>("POST", `${K(id, kpi)}/ambiguities/${encodeURIComponent(amb)}/accept`, { reason });
