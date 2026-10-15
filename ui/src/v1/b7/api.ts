// DS1: the dashboard studio against sh_platform/v1/b7_routes.py, and the refresh line (also read by Consume).
import { apiGet, apiSend } from "../../api/client";
import type { Layout, LayoutItem, Picture, Size, TileData } from "../cxui/api";

export interface Refresh {
  schedule: string | null; words: string; last_refreshed: string | null; next: string | null;
  warning: string | null; link: string | null; late_sources: string[]; last_run_failed: boolean;
}
export type Status = "draft" | "submitted" | "published";
export const STATUS_WORDS: Record<Status, string> = { draft: "Draft", submitted: "Waiting for approval", published: "Published" };
export interface LumenTile { dashboard_id: string; tile_id: string; title: string; state: string; reads: string[] }
export interface LibraryTable { name: string; label: string; columns: { name: string; type: string }[] }
export interface Studio {
  id: string; project_id: string; title: string; /** Save counter: sent back with a layout change so a stale copy is refused (409). */ rev: number; status: Status; version: number; published_version: number | null;
  sent_back: { reason: string; by: string; at: string } | null; submitted_by: string | null; submitted_at: string | null;
  approved_by: string | null; approved_at: string | null; company_wide: boolean; layout: Layout;
  /** Every tile of the working copy; `proposed` ones are Lumen's proposals waiting for Accept or Not this. */
  tiles: { id: string; title: string; state: string; spec: Record<string, unknown>; kpi?: string; note?: string; replaces?: string | null; starter?: boolean }[];
  /** The person's own thread with Lumen on this dashboard. */
  talk?: { by: "lumen" | "person"; text: string }[];
  can: { edit: boolean; submit: boolean; approve: boolean };
  /** V6 (design D3): for the approver only: who built and sent it, and "What Lumen checked" (ok is null when no record says). */
  review?: { built_by: string | null; submitted_by: string | null; submitted_at: string | null; checks: { title: string; detail: string; ok: boolean | null }[] } | null;
  /** H10: Lumen's starter dashboard; `proposed` until someone accepts it as it is. */
  starter?: { status: "proposed" | "accepted"; pack_version: number | null; why: string[]; from_intent: boolean; at: string } | null;
  library: { kinds: string[]; tables: LibraryTable[]; lumen: LumenTile[] }; refresh: Refresh;
}
export interface StudioRow { id: string; title: string; status: Status; version: number; tiles: number; created_by: string; made_by?: string | null; approved_by?: string | null; updated_at: string; waiting_for_you: boolean; archived?: boolean }
export interface LumenProposal { id: string; title: string; replaces?: string | null }
export interface NewWidget { kind: string; table?: string; text?: string; dashboard_id?: string; tile_id?: string; row: number; col: number; size?: Size }
export type LayoutSend = { id: string; row: number; col: number; size: Size; text?: string }[];

const s = (pid: string) => `/api/v1/build/p/${encodeURIComponent(pid)}/studio`;
const d = (pid: string, id: string) => `${s(pid)}/${encodeURIComponent(id)}`;
export const listStudio = (pid: string) => apiGet<{ dashboards: StudioRow[]; can_make: boolean }>(s(pid));
export const createStudio = (pid: string, title: string) => apiSend<Studio>("POST", s(pid), { title });
export const deleteStudio = (pid: string, id: string) => apiSend<{ deleted: string }>("DELETE", d(pid, id));
export const getStudio = (pid: string, id: string) => apiGet<Studio>(d(pid, id));
export const saveLayout = (pid: string, id: string, items: LayoutSend, rows: number, extra: { title?: string; company_wide?: boolean; rev?: number } = {}) =>
  apiSend<Studio>("PUT", `${d(pid, id)}/layout`, { items, rows, ...extra });
export const addWidget = (pid: string, id: string, w: NewWidget) => apiSend<{ placed: LayoutItem; dashboard: Studio }>("POST", `${d(pid, id)}/widgets`, w);
export const askSlot = (pid: string, id: string, body: { text?: string; widget?: string; new_talk?: boolean; picture?: Picture }) =>
  apiSend<{ reply: string; proposals: LumenProposal[]; dashboard: Studio; worded_by?: string; note?: string }>("POST", `${d(pid, id)}/ask`, body);
export const acceptTile = (pid: string, id: string, tid: string, slot: { row?: number; col?: number; size?: Size }) =>
  apiSend<{ placed: LayoutItem; dashboard: Studio }>("POST", `${d(pid, id)}/tiles/${encodeURIComponent(tid)}/accept`, slot);
export const rejectTile = (pid: string, id: string, tid: string) => apiSend<Studio>("POST", `${d(pid, id)}/tiles/${encodeURIComponent(tid)}/reject`, {});
export const submitStudio = (pid: string, id: string) => apiSend<Studio>("POST", `${d(pid, id)}/submit`, {});
export const approveStudio = (pid: string, id: string) => apiSend<Studio>("POST", `${d(pid, id)}/approve`, {});
export const sendBack = (pid: string, id: string, reason: string) => apiSend<{ id: string; status: Status }>("POST", `${d(pid, id)}/send-back`, { reason });
export const studioTileData = (pid: string, id: string, tid: string) => apiGet<TileData>(`${d(pid, id)}/tiles/${encodeURIComponent(tid)}/data`);
/** The same facts for a published dashboard, for anyone who may read it. */
export const getRefresh = (did: string) => apiGet<Refresh>(`/api/v1/consume/dashboards/${encodeURIComponent(did)}/refresh`);
/** H10: Lumen's starter dashboard (made when the pipeline went live; made now when it was not). */
export const startStarter = (pid: string) => apiSend<Studio>("POST", `${s(pid)}/starter`, {});
export const acceptStarter = (pid: string, id: string) => apiSend<Studio>("POST", `${d(pid, id)}/starter/accept`, {});
