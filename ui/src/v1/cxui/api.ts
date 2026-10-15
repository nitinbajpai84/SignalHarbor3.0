// C2: the Consume centre against card C1's routes (sh_platform/v1/cx_routes.py), through the shared client.
import { apiGet, apiSend } from "../../api/client";
import type { Used } from "../teach/api";

export interface Tile {
  id: string; title: string; kpi: string; sql: string; spec: Record<string, unknown>; note: string; state: "proposed" | "accepted"; replaces?: string | null;
}
/** DS1: where a widget sits on the 12-column grid. `size` is Small (3 columns), Medium (6), Wide (9) or Full (12). */
export type Size = "small" | "medium" | "wide" | "full";
export interface LayoutItem { id: string; kind: string; tile: string | null; title: string; text: string; row: number; col: number; size: Size; h?: number; reads?: string[] }
export interface Layout { rows: number; items: LayoutItem[] }
export interface Dashboard {
  id: string; title: string; project_id: string; tiles: Tile[]; audience: string[]; refresh: "same" | "daily" | "weekly";
  created_by?: string; updated_at?: string; audience_people?: Member[];
  /** Set for a dashboard made in the Build studio; older dashboards have none and show as a plain list of tiles. */
  layout?: Layout | null;
  /** OP1: no longer set (dashboards are made in the Build studio); kept so an older response still types. */
  personal?: boolean;
}
export interface Member { id: string; name: string; kind: "user" | "group" }
/** One row of GET .../dashboards: tiles is a count. */
export interface DashSummary { id: string; title: string; project_id: string; refresh: string; tiles: number; accepted: number }
export interface GoldTable { name: string; columns: { name: string; type: string }[]; rows: number; refreshed: string | null }
export interface TileData { columns?: string[]; spec: Record<string, unknown>; rows?: Record<string, unknown>[]; capped?: boolean; data_used: { tables: string[]; last_refresh: string | null } }
export interface Picture { name: string; data: string; no_client_figures: boolean }
/** OP1: in Consume the answer never carries proposals; a request to build comes back with the studio link (for people who may build there). */
export interface Ask { used?: Used[]; reply: string; proposals: Tile[]; dashboard_id?: string; link?: string | null }
export interface Person { id: string; name: string; role: string }
export interface Why { answer: string; evidence: ({ period: string; value: string } | { split: string; change: string })[]; caveats: string[] }

export interface Shared { id: string; title: string; project_title: string; shared_by: string; shared_at: string; tiles: number; link: string }
export interface Company { id: string; title: string; project_title: string; published_at: string; tiles: number; link: string }
export interface SharedList { dashboards: Shared[]; brief: { report_version_id: string; title: string; link: string } | null; company?: Company[] }
export const getShared = () => apiGet<SharedList>("/api/v1/consume/shared");
const p = (pid: string) => `/api/v1/consume/p/${encodeURIComponent(pid)}`;
const d = (pid: string, id: string) => `${p(pid)}/dashboards/${encodeURIComponent(id)}`;
export const getTables = (pid: string) => apiGet<{ tables: GoldTable[] }>(`${p(pid)}/tables`).then((r) => r.tables);
export const listDashboards = (pid: string) => apiGet<{ dashboards: DashSummary[] }>(`${p(pid)}/dashboards`).then((r) => r.dashboards);
export const getDashboard = (pid: string, id: string) => apiGet<Dashboard>(d(pid, id));
/** The read-only view knows only the dashboard id. */
export const getDashboardById = (id: string) => apiGet<Dashboard>(`/api/v1/consume/dashboards/${encodeURIComponent(id)}/view`);
export const getPeople = (pid: string) => apiGet<{ people: Person[] }>(`${p(pid)}/people`).then((r) => r.people);
/** Lumen in Consume answers questions about the dashboard; building and changing it is done in the Build studio (OP1). */
export const ask = (pid: string, id: string, text: string) => apiSend<Ask>("POST", `${d(pid, id)}/ask`, { text });
/** With no published dashboard to talk about, the project-level talk answers (and points to the studio for a build request). */
export const askProject = (pid: string, text: string) => apiSend<{ reply: string; link?: string | null; used?: Used[] }>("POST", "/api/v1/consume/chat", { text, project_id: pid });
export const tileData = (pid: string, id: string, tid: string) => apiGet<TileData>(`${d(pid, id)}/tiles/${encodeURIComponent(tid)}/data`);
export const why = (pid: string, id: string, tid: string) => apiGet<Why>(`${d(pid, id)}/tiles/${encodeURIComponent(tid)}/why`);
export const share = (pid: string, id: string, audience: string[], refresh: string) =>
  apiSend<{ audience: Member[]; refresh: string }>("PUT", `${d(pid, id)}/audience`, { audience, refresh });
