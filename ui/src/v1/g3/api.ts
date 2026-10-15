// G3 the benchmark sheet and G4 deviations (sh_platform/v1/g3_routes.py, g4_routes.py), through the shared client.
import { apiGet, apiSend, downloadFile } from "../../api/client";

export interface SheetRow {
  id: string; code: string; kpi: string | null; dims: Record<string, string>; reported: number | null; expected: number | null; tolerance: number | null;
  source: string | null; source_doc: string | null; line: number | null; stated_by: string | null; proposed: boolean; dropped: boolean;
  status: "ready" | "needs figure" | "proposed";
}
export interface SheetView { sheet: { version: number; state: "draft" | "signed"; rows: SheetRow[] }; columns: string[]; sign_block: string | null; required: string[]; missing: string[] }
export interface Check { code: string; period: string; expected: number | null; got: number | null; tolerance: number; met: boolean | null; row_id?: string; why?: string }
export interface Deviation {
  id: string; summary: string; about: string; before: string; after: string; why: string; effect: string[]; effect_labels: string[];
  status: string; by?: string; implement_error?: string | null; asks: { name: string; cid: string }[]; decisions: Record<string, { decision: string; reason?: string }>;
}
export interface Deviations { intent_id: string; deviations: Deviation[]; pending: string | null }

const b = (iid: string) => `/api/v1/build/${encodeURIComponent(iid)}`;
export const getSheet = (iid: string) => apiGet<SheetView>(`${b(iid)}/benchmarks/sheet`);
export const getChecks = (iid: string) => apiGet<{ verify: Check[] }>(`${b(iid)}/benchmarks`).then((r) => r.verify ?? []);
export const setFigure = (iid: string, rid: string, reported: string) => apiSend<SheetView>("POST", `${b(iid)}/benchmarks/sheet/rows/${encodeURIComponent(rid)}`, { reported });
export const signSheet = (iid: string) => apiSend<SheetView>("POST", `${b(iid)}/benchmarks/sheet/sign`);
export const exportSheet = (pid: string) => downloadFile(`/api/v1/projects/${encodeURIComponent(pid)}/artefacts/benchmarks/export?format=xlsx`, `${pid}-benchmarks.xlsx`);
export const readReport = (iid: string, body: { item_id?: string; file?: string }) => apiSend<SheetView & { read: number }>("POST", `${b(iid)}/benchmarks/sheet/read`, body);
export interface DocView { name: string; line: number; lines: { n: number; text: string }[] }
export const getDoc = (iid: string, file: string, line: number) =>
  apiGet<DocView>(`${b(iid)}/benchmarks/sheet/doc?file=${encodeURIComponent(file)}&line=${line}`);
export const getDeviations = (iid: string) => apiGet<Deviations>(`${b(iid)}/deviations`);
export const decide = (iid: string, did: string, decision: "approved" | "not approved", reason = "") =>
  apiSend<Deviations>("POST", `${b(iid)}/deviations/${encodeURIComponent(did)}/decide`, { decision, ...(reason ? { reason } : {}) });
export const makeNow = (iid: string, did: string) => apiSend<Deviations>("POST", `${b(iid)}/deviations/${encodeURIComponent(did)}/make`);
