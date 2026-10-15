// V6-builder: Span the builder in the Pipelines step (sh_platform/v1/b11_routes.py).
import { apiGet, apiSend } from "../../api/client";

export interface Mismatch { field: "file" | "columns" | "host"; pack: string | string[] | null; intent: string | string[] | null; seen: string | null }
export interface Connection {
  code: string; name: string; kind: string | null; how: string; how_words: string; status: "connected" | "failed" | "needs_sample" | "mismatch" | "not_needed"; detail: string;
  owner: string | null; seen: { file?: string | null; host?: string | null }; mismatches: Mismatch[]; from_intent: boolean;
}
export interface RunStep { label: string; layer: string | null; rows: number | null; status: string }
export interface RunSummary {
  status: string; pack_version: number; run_id?: string; started?: string; finished?: string; error: string | null;
  tables?: { bronze: number; silver: number; gold: number }; steps?: RunStep[]; gold_rows?: number; checks?: { passed: number; total: number } | null;
}
export interface Evidence { text: string; trail?: { kind: string; id: string } }
export interface VarianceLine { figure: string; run: string | null; report: string; unit: "money" | "pct"; diff: string | null; status: "matches" | "explained" | "unexplained"; evidence: Evidence[] }
export interface Variance {
  benchmark: string; lines: VarianceLine[]; legs: VarianceLine[]; unmatched: { label: string; value: string; unit: string }[];
  summary: { matches: number; explained: number; unexplained: number }; headline: string; at: string;
}
export interface Round {
  pack_version: number; started_at: string; connections: Connection[]; run: RunSummary | null; variance: Variance | null;
  state: "connecting" | "blocked" | "failed" | "ran" | "checked" | "sent_back" | "live"; outcome: { kind: string; by: string; at: string; anyway?: boolean } | null;
}
export interface Message { who: string; at: string; text: string; evidence: Evidence[] }
export interface Need { id: string; kind: "connection_failed" | "missing_sample"; source: string; name: string; to: string[]; text: string; at: string }
export interface BuilderView {
  project_id: string; waiting: string | null; newer: { version: number; state: string } | null;
  pack: { version: number; state: string; approved_by: string | null; approved_at: string | null; sources: number; tables: { bronze: number; silver: number; gold: number };
          schedule: { freq: string; at: string; day: string | number | null } | null; change_from: { version: number; changes: { table: string; before: string; after: string; why: string }[] } | null;
          sql: { table: string; label: string; sql: string }[] } | null;
  round: Round | null; rounds: { pack_version: number; state: string; headline: string | null }[];
  benchmark: { kind: "upload" | "signed"; name: string; by: string; at: string; figures: number } | null;
  signed_reports: { id: string; name: string; issued_at: string }[]; thread: Message[]; needs: Need[]; not_needed?: { code: string; name: string; by: string; at: string; reason: string }[];
  can: { start: boolean; recheck: boolean; benchmark: boolean; go_live: boolean; send_back: boolean; settle: boolean; issue: boolean; not_needed?: boolean };
}

const p = (pid: string) => `/api/v1/build/p/${encodeURIComponent(pid)}/builder`;
export const getBuilder = (pid: string) => apiGet<BuilderView>(p(pid));
export const startBuilder = (pid: string) => apiSend<BuilderView>("POST", `${p(pid)}/start`, {});
export const recheck = (pid: string) => apiSend<BuilderView>("POST", `${p(pid)}/recheck`, {});
export const settle = (pid: string, b: { source: string; field: string; value: string }) => apiSend<BuilderView>("POST", `${p(pid)}/settle`, b);
export const notNeeded = (pid: string, b: { source: string; reason?: string; needed?: boolean }) => apiSend<BuilderView>("POST", `${p(pid)}/not-needed`, b);
export const giveBenchmark = (pid: string, b: { name: string; text?: string; b64?: string } | { report_version_id: string }) => apiSend<BuilderView>("POST", `${p(pid)}/benchmark`, b);
export const goLive = (pid: string, b: { accept_variance?: boolean; no_benchmark?: boolean }) => apiSend<BuilderView>("POST", `${p(pid)}/go-live`, b);
export const sendBack = (pid: string, note: string) => apiSend<BuilderView>("POST", `${p(pid)}/send-back`, { note });
export const issuePack = (pid: string, b: { changes: { table: string; sql: string; why: string }[]; note?: string }) => apiSend<BuilderView>("POST", `${p(pid)}/pack`, b);
