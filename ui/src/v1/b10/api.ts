// V6 b10: the Architecture step's calls (read before asking, the few questions, samples, the design pack, approval, the plan from the pack).
import { apiGet, apiSend } from "../../api/client";

export type Channel = "upload" | "mailbox" | "sftp" | "sharepoint" | "database";
export const CHANNELS: Channel[] = ["upload", "mailbox", "sftp", "sharepoint", "database"];
export const CHANNEL_WORDS: Record<Channel, string> = { upload: "Upload each file", mailbox: "A mailbox", sftp: "An SFTP folder", sharepoint: "A SharePoint folder", database: "A database" };

export interface Sample { kind: "table" | "pdf"; name: string; rows?: number; columns?: { name: string; type: string; goes_to: string }[]; fields?: { name: string; format: string; where_usually: string; example: string; line: number }[] }
export interface System {
  id: string; code: string; name: string; holds: string; owner: string; format: string; channel: string; frequency: string;
  status: "connected" | "landed" | "sample" | "never_seen"; connector: string | null; from_intent: boolean; confirmed: boolean; corrected: string[];
  intent: { holds: string; owner: string; format: string; channel: string; frequency: string };
  found?: { files: number; documents: number; columns?: number; rows?: number; names?: string[] }; sample?: Sample | null;
}
export interface Summary {
  project_id: string; title: string; people?: Record<string, string | null>; readers: string[]; needed_by: string; steps: number; line: string; asked: string[]; not_asked: string[];
  kpis: { code: string; name: string; definition: string; signed: boolean; owner: string }[]; systems: System[];
}
export interface Check { id: string; kind: string; text: string; tolerance: string; source: string }
export interface Question { id: string; topic: string; title: string; why: string; proposal: unknown; options: string[]; answer: unknown; state: "open" | "answered"; evidence: string }
export interface Questions { open: Question[]; all: Question[]; known: string[] }

export interface Column { name: string; type: string; expr: string; definition: string; sensitivity: string; history: boolean }
export interface Gold { name: string; purpose: string; grain: string; keys: string[]; history: string[]; owner: string; columns: Column[] }
export interface Silver {
  name: string; status: "reused" | "used" | "extended" | "proposed"; note: string; history: string[]; columns?: string[];
  /** FIXC: other projects that already read a reused table. */
  other_projects?: string[]; feeds_other?: string[];
  /** FIXC: for a proposed change, what was looked for, which tables were considered and why they do not fit, and who is affected. */
  looked_for?: string; considered?: { table: string; why_not: string }[]; affects?: string[]; extends?: boolean; model_change?: number | null;
}
export interface ModelChange { version: number; state: string; proposed_by?: string; approved_by?: string | null; summary: string; tables: { name: string }[] }
export interface MapRow { id: string; kind: string; system: string; source_field: string; bronze: string; silver: string; gold: string; words: string; needs_person: string; resolved: boolean }
export interface CatalogueRow { table: string; layer: string; column: string; meaning: string; source: string; sensitivity: string }
export interface Definition { name: string; definition: string; source: string; signed: boolean; columns: string[] }
export interface BenchmarkBlock {
  portfolio: string; portfolio_name?: string; code: string; version?: number | null; benchmark_name?: string; month: string; table?: string; weights_table?: string | null;
  names?: Record<string, string>; figures: { key: string; label: string; unit: string }[];
}
export interface Pack {
  project_id: string; version: number; state: "draft" | "proposed" | "approved" | "superseded"; base_version: number | null; created_by: string; created_at: string;
  approved_by: string | null; approved_at: string | null; approval_note?: string; send_back?: string; open_rows: number; locked: boolean; notes: string[];
  target: { silver: Silver[]; gold: Gold[] }; catalogue: CatalogueRow[]; mapping: MapRow[]; edits: { at: string; by: string; section: string; key: string; field: string; before: unknown; after: unknown }[];
  rules: { checks: Check[]; history: string[]; refresh: { freq: string; at: string; day: string | null; label?: string }; late_data: string; benchmark: string };
  sources: { id: string; code: string; name: string; format: string; channel: string; frequency: string; owner: string; sample: string | null; marked_fields: string[] }[];
  counts: { sources: number; gold: number; silver: number; mapping: number; checks: number };
  /** V6B: one definition per figure, the benchmark check the builder runs, and the money figures it compares. */
  model_change?: number | null; plan_state?: "approved" | "not_approved"; plan_error?: string | null;
  definitions?: Definition[]; benchmark?: BenchmarkBlock | null; key_figures?: { label: string; table: string; column: string; by?: string }[];
}
export interface VersionRow { version: number; state: string; by: string; at: string; approved_by: string | null; edits: number; base_version: number | null; plan_version: number | null }
export interface PackView {
  project_id: string; pack: Pack | null; versions: VersionRow[]; plan_version?: number | null; log?: { at: string; by: string; what: string; note: string }[];
  can: { answer: boolean; generate: boolean; edit: boolean; submit: boolean; approve: boolean; reject: boolean; plan: boolean; approve_plan?: boolean };
  model_change?: ModelChange | null;
}
export interface Diff { from: number; to: number; changes: { line: string; change: "added" | "removed" | "changed"; before: string | null; after: string | null }[] }

const p = (pid: string) => `/api/v1/build/p/${encodeURIComponent(pid)}/architecture`;
export const getSummary = (pid: string) => apiGet<Summary>(`${p(pid)}/summary`);
export const getQuestions = (pid: string) => apiGet<Questions>(`${p(pid)}/questions`);
export const answer = (pid: string, qid: string, value: unknown) => apiSend<Questions>("POST", `${p(pid)}/questions/${encodeURIComponent(qid)}`, { value });
export const acceptAll = (pid: string) => apiSend<Questions>("POST", `${p(pid)}/questions/accept-all`, {});
export const confirmSystems = (pid: string, ids: string[]) => apiSend<Summary>("POST", `${p(pid)}/systems/confirm`, { ids });
export const correctSystem = (pid: string, sid: string, changes: Record<string, string>) => apiSend<Summary>("PUT", `${p(pid)}/systems/${encodeURIComponent(sid)}`, changes);
export const sampleTable = (pid: string, sid: string, name: string, data: string) => apiSend<Sample>("POST", `${p(pid)}/samples/${encodeURIComponent(sid)}/table`, { name, data });
export const samplePdf = (pid: string, sid: string, name: string, data: string) => apiSend<Sample>("POST", `${p(pid)}/samples/${encodeURIComponent(sid)}/pdf`, { name, data });
export const sampleLines = (pid: string, sid: string) => apiGet<{ lines: { n: number; text: string }[] }>(`${p(pid)}/samples/${encodeURIComponent(sid)}/lines`);
export const markField = (pid: string, sid: string, line: number, name: string, format: string) => apiSend<Sample>("POST", `${p(pid)}/samples/${encodeURIComponent(sid)}/mark`, { line, name, format });
export const getPack = (pid: string, version?: number) => apiGet<PackView>(`${p(pid)}/pack${version ? `?version=${version}` : ""}`);
export const generate = (pid: string) => apiSend<PackView>("POST", `${p(pid)}/pack/generate`, {});
export const edit = (pid: string, section: string, key: string, changes: Record<string, unknown>, note = "") => apiSend<PackView>("PUT", `${p(pid)}/pack/edit`, { section, key, changes, note });
export const submit = (pid: string) => apiSend<PackView>("POST", `${p(pid)}/pack/submit`, {});
export const approve = (pid: string, note = "") => apiSend<PackView>("POST", `${p(pid)}/pack/approve`, { note });
export const reject = (pid: string, reason: string) => apiSend<PackView>("POST", `${p(pid)}/pack/reject`, { reason });
export const getDiff = (pid: string, a: number, b: number) => apiGet<Diff>(`${p(pid)}/pack/diff?a=${a}&b=${b}`);
export const planFromPack = (pid: string) => apiSend<PackView>("POST", `${p(pid)}/pack/plan`, {});
export const approvePlan = (pid: string) => apiSend<PackView>("POST", `${p(pid)}/pack/plan/approve`, {});
