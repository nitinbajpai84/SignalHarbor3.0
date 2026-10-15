// I4: the intent of work record (V1-BUILD.md "Records") plus what this person may do, through the shared client.
import { apiGet, apiSend, downloadFile } from "../../api/client";

export interface SowField { name: string; type: string; example?: string; meaning: string; source_field?: string }
export interface Sow {
  id: string; intent_id: string; title: string; state: "draft" | "signed"; version: number;
  goal: { line: string; why: string; readers: string[]; decisions: string[]; needed_by: string } | null;
  process: { steps: { n: number; name: string; who: string; does: string; inputs: string[]; outputs: string[]; system: string }[];
    handovers: { from_step: number; to_step: number; what: string }[] } | null;
  kpis: { code: string; name: string; definition: string; formula: string; unit: string; period: string; owner: string; source_ids: string[];
    status: "defined" | "unclear"; pack_suggested: boolean }[];
  sources: { id: string; name: string; kind: "file" | "system" | "document"; holds: string; sample_path: string | null; owner: string; fields: SowField[] }[];
  catalogue: { table: string; layer: "landing" | "silver" | "gold"; meaning: string; source_id: string | null; fields: SowField[]; feeds_kpis: string[] }[];
  governance: { rule: string; kind: "access" | "retention" | "approval"; applies_to: string[]; stated_by: string }[];
  unclear: { id: string; question: string; about: string; who_can_settle: string; settled: boolean; answer: string | null }[];
  signature: { name: string; role: string; at: string; note?: string } | null;
  signatures?: { name: string; role: string; at: string; version: number }[];
}
export interface SowView extends Sow {
  may: { edit: boolean; sign: boolean; send_back: boolean };
  sign_block: string | null;
  /** V6 (design B3): who finished the intent with North, when, and after how many minutes; null when the thread has no turns. */
  before?: { by: string | null; at: string; minutes: number } | null;
  docx: boolean;
  written?: { glossary: Record<string, number>; catalogue: { sources?: number; tables?: number; fields?: number; error?: string } };
}
export type Section = "title" | "goal" | "process" | "kpis" | "sources" | "catalogue" | "governance" | "unclear";
export interface LineEdit { section: Section; index?: number; field?: string; value: string }

const base = (iid: string) => `/api/v1/intents/${encodeURIComponent(iid)}/sow`;

export const getSow = (iid: string) => apiGet<SowView>(base(iid));
export const editLine = (iid: string, version: number, e: LineEdit) => apiSend<SowView>("PUT", base(iid), { ...e, version });
export const signSow = (iid: string, version: number, note?: string) => apiSend<SowView>("POST", `${base(iid)}/sign`, { confirm: true, version, ...(note?.trim() ? { note: note.trim() } : {}) });
export const sendBack = (iid: string, reason: string) => apiSend<SowView>("POST", `${base(iid)}/send-back`, { reason });
export const download = (iid: string, format: "md" | "docx") =>
  downloadFile(`${base(iid)}/download?format=${format}`, `statement-of-work.${format}`);
