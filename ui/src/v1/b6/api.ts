// B1: the Build centre's calls. Routes are B2 (plan, chat), B4 (runs, schedule, airflow) and B3 (diagram). Shapes follow fact 5 and 7 of V3-CENTRES-CARDS.
import { apiGet, apiSend } from "../../api/client";
import type { Used } from "../teach/api";

export type PlanState = "draft" | "proposed" | "approved" | "rejected" | "built" | "live";
export const STATE_NAMES: Record<PlanState, string> = {
  draft: "Draft", proposed: "Waiting for the head of data", approved: "Approved", rejected: "Sent back", built: "Built in the sandbox", live: "Live",
};
export interface ProjectRow { id: string; intent_id?: string | null; title: string; owner: string | null; builder?: string | null; stage: "intent" | "build" | "live"; plan_state: PlanState | null; updated_at?: string }
export interface SourceFile { name: string; state: string }
export interface Source { code: string; kind: "structured" | "unstructured"; files: (string | SourceFile)[]; owner: string }
export interface Column { name: string; type: string; from?: string }
export interface Table { name: string; layer: "bronze" | "silver" | "gold"; purpose: string; columns: Column[]; sql: string; depends_on: string[]; is_new?: boolean }
export interface Schedule { freq: "daily" | "weekly" | "monthly" | "on_arrival"; at: string; day: string | null }
export const MODEL_STATES: Record<string, string> = { proposed: "Proposed", approved: "Approved", rejected: "Sent back" };
export interface ModelDiff { tables_added: { table: string; columns: string[] }[]; columns_added: { table: string; column: string; type?: string }[]; state?: string }
export interface Pending { id: string; summary: string; status: string }
export interface Plan {
  project_id: string; intent_id?: string | null; version: number; sources: Source[]; model_changes: number | string | null; model_diff?: ModelDiff; tables: Table[];
  lineage: { from: string; to: string }[]; schedule: Schedule; state: PlanState; proposed_by: string | null; approved_by: string | null; approved_at: string | null; reason: string | null;
  can?: { propose?: boolean; approve?: boolean; reject?: boolean; run_sandbox?: boolean; go_live?: boolean; schedule?: boolean };
}
export interface RunStep { table: string; rows: number; ms: number; status: string; error?: string }
export interface Run { run_id: string; plan_version: number; started: string; finished: string | null; status: string; mode?: string; steps: RunStep[] }
export interface Turn { id: string; by: "span" | "person"; name: string; text: string; at: string }
export interface Chat { turns: Turn[]; pending?: Pending[]; used?: Used[] }
// A project Span has not planned yet: the server answers with plan null and no sources or tables.
export interface NoPlan { project_id: string; intent_id?: string | null; plan: null; state: null; title?: string; intent_signed?: boolean; can?: Plan["can"] }

const p = (pid: string) => `/api/v1/build/p/${encodeURIComponent(pid)}`;
export const listProjects = () => apiGet<{ projects: ProjectRow[] }>("/api/v1/build/projects");
export const getPlan = (pid: string) => apiGet<Plan | NoPlan>(`${p(pid)}/plan`);
export const propose = (pid: string) => apiSend<Plan>("POST", `${p(pid)}/plan/propose`, {});
export const approve = (pid: string, note?: string) => apiSend<Plan>("POST", `${p(pid)}/plan/approve`, note?.trim() ? { note: note.trim() } : {});
export const reject = (pid: string, reason: string) => apiSend<Plan>("POST", `${p(pid)}/plan/reject`, { reason });
export const getRuns = (pid: string) => apiGet<{ runs: Run[] }>(`${p(pid)}/runs`);
export const startRun = (pid: string, mode: "sandbox" | "live") => apiSend<Plan>("POST", `${p(pid)}/run?mode=${mode}`, {});
export const setSchedule = (pid: string, s: Schedule) => apiSend<Plan>("PUT", `${p(pid)}/schedule`, s);
export const airflowHref = (pid: string) => `${p(pid)}/airflow`;
export const getChat = (pid: string) => apiGet<Chat>(`${p(pid)}/chat`);
export const sendChat = (pid: string, text: string, files: string[] = []) => apiSend<Chat>("POST", `${p(pid)}/chat`, files.length ? { text, files } : { text });
/** A file for Span to read, kept for this project; the server answers {name, path, kind}. */
export const sendChatFile = (pid: string, name: string, data: string) => apiSend<{ name: string; path: string; kind: string }>("POST", `${p(pid)}/chat/files`, { name, data });
export const acceptChange = (pid: string, cid: string) => apiSend<Plan>("POST", `${p(pid)}/plan/changes/${encodeURIComponent(cid)}/accept`, {});
export const rejectChange = (pid: string, cid: string) => apiSend<Plan>("POST", `${p(pid)}/plan/changes/${encodeURIComponent(cid)}/reject`, {});
