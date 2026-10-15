import { apiGet, apiSend } from "../../../api/client";
import { BASE, type Prov } from "../api";

// M2-E2: the business glossary. Typed calls for the glossary screen; the server decides what each person may see.
export type GlossaryChange = "unchanged" | "changed" | "new";
export type Choice = "ours" | "provided" | "edited" | "not_same";

/** The same words the Excel file and the printed page use. */
export interface GlossaryText {
  term: string;
  aliases: string;
  definition: string;
  how_sure: string;
  previous: string;
  owner: string;
  frequency: string;
  who: string;
  personal: string;
  change: string;
  assumption: string;
  source: string;
  reviewed: string;
  decided_by: string;
  proposal: string;
}
export interface GlossaryEntry {
  kpi_id: string;
  change: GlossaryChange;
  business_definition: Prov;
  previous: Prov;
  assumption: string;
  source_document: string;
  reviewed: { by: string; at: string } | null;
  decided?: { choice: Choice; by: string; at: string };
  proposal?: Prov;
  match?: "name" | "meaning";
  matched_term?: string;
  text: GlossaryText;
}
export interface GlossaryView {
  baseline_id: string;
  signed: boolean;
  lens_available: boolean;
  /** Set for the company admin: the kept glossary mentions personal data and waits for a decision (restrict it, or say it is not personal). */
  personal_documents?: { doc_id: string; personal_words: string[]; restrict_path: string }[];
  built: boolean;
  entries: GlossaryEntry[];
  counts: { all: number; changed: number; new: number; unchanged: number; reviewed: number };
  unmatched_terms: { term: string; definition: string }[];
  provided: { title: string; filename: string; by: string; at: string; truncated: boolean } | null;
  waiting: number;
  restricted_kept?: number;
  lens_note?: string;
  note?: string;
}

const G = (id: string) => `${BASE}/baselines/${encodeURIComponent(id)}/glossary`;
export const getGlossary = (id: string) => apiGet<GlossaryView>(G(id));
export const buildGlossary = (id: string) => apiSend<GlossaryView>("POST", `${G(id)}/build`);
export const uploadGlossary = (id: string, filename: string, data: string) => apiSend<GlossaryView>("POST", `${G(id)}/upload`, { filename, data });
export const decideEntry = (id: string, kpi: string, choice: Choice, text?: string) => apiSend<GlossaryView>("PUT", `${G(id)}/entries/${encodeURIComponent(kpi)}`, { choice, text });
export const reviewEntry = (id: string, kpi: string) => apiSend<GlossaryView>("POST", `${G(id)}/entries/${encodeURIComponent(kpi)}/review`);
export const reviewUnchanged = (id: string) => apiSend<GlossaryView>("POST", `${G(id)}/review-unchanged`);
/** Plain links: the browser downloads with the signed-in session. */
export const glossaryExcelUrl = (id: string) => `${G(id)}/export`;
export const glossaryPrintUrl = (id: string) => `${G(id)}/print`;
