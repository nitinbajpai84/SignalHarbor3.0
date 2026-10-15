// E0a: the data model catalogue, its versions and change proposals (sh_platform/v1/e0a_routes.py).
import { apiGet, apiSend } from "../../api/client";

export interface ModelColumn { name: string; type: string; null: boolean; pk: boolean; note: string; layer: "core" | "company" }
export interface ModelTable { name: string; layer: "core" | "company"; note: string; columns: ModelColumn[] }
export interface LayerTable { name: string; source: string | null; layout: string | null; project_ids: string[]; columns: number }
export interface Layers { bronze: LayerTable[]; silver: { tables: number }; gold: LayerTable[] }
export interface Catalogue {
  layers?: Layers; version: number; state: string; approved_by: string | null; approved_at: string | null; groups: { name: string; tables: ModelTable[] }[];
}
export interface Diff { words: string[] }
export interface Version {
  version: number; state: "proposed" | "approved" | "rejected" | "superseded"; is_current?: boolean; source: string; summary: string; note?: string;
  proposed_by: string; proposed_at: string; approved_by?: string; approved_at?: string; rejected_by?: string; reason?: string;
  diff?: Diff; breaking?: string[]; sandbox?: { ok: boolean; message: string };
}
export interface NewColumn { name: string; type: string; null?: boolean; note?: string }

export const getCatalogue = () => apiGet<Catalogue>("/api/v1/model/catalogue");
export const listVersions = () => apiGet<Version[]>("/api/v1/model/versions");
export const getProposal = (n: number) => apiGet<Version>(`/api/v1/model/proposals/${n}`);
export const proposeScript = (dbml: string, note: string) => apiSend<Version>("POST", "/api/v1/model/proposals", { dbml, note });
export const proposeTable = (name: string, note: string, columns: NewColumn[]) =>
  apiSend<Version>("POST", "/api/v1/model/proposals", { add_table: { name, note, columns } });
export const proposeColumn = (table: string, col: NewColumn) => apiSend<Version>("POST", "/api/v1/model/proposals", { add_column: { table, ...col } });
export const approveProposal = (n: number) => apiSend<Version>("POST", `/api/v1/model/proposals/${n}/approve`, {});
export const rejectProposal = (n: number, reason: string) => apiSend<Version>("POST", `/api/v1/model/proposals/${n}/reject`, { reason });
