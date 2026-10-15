// STUDIO2 F2: calls behind the inspector, Lumen's options and the checks (contracts in docs/plan/v6-landings/STUDIO2-CARDS.md).
import { apiGet, apiSend } from "../../api/client";

export interface TilePatch { kind?: string; measure?: string; split?: string; when?: string; only?: { column: string; values: string[] }; title?: string }
export interface Option { label: string; why: string; patch: TilePatch; pick: boolean ; book?: { line: string; used: string } }
export interface Check { id: string; widget: string; kind: "counted_twice" | "flattened_trend" | "space" | "house_style" | "too_many"; message: string; fix?: { label: string; patch: TilePatch } }

const d = (pid: string, did: string) => `/api/v1/build/p/${encodeURIComponent(pid)}/studio/${encodeURIComponent(did)}`;
export const patchTile = (pid: string, did: string, tid: string, patch: TilePatch) =>
  apiSend<{ ok: boolean; step: number }>("PATCH", `${d(pid, did)}/tiles/${encodeURIComponent(tid)}`, patch);
export const duplicateWidget = (pid: string, did: string, wid: string) => apiSend<unknown>("POST", `${d(pid, did)}/widgets/${encodeURIComponent(wid)}/duplicate`, {});
export const removeWidget = (pid: string, did: string, wid: string) => apiSend<unknown>("DELETE", `${d(pid, did)}/widgets/${encodeURIComponent(wid)}`);
export const tileOptions = (pid: string, did: string, tid: string) => apiSend<{ options: Option[] }>("POST", `${d(pid, did)}/tiles/${encodeURIComponent(tid)}/options`, {});
export const getChecks = (pid: string, did: string) => apiGet<{ checks: Check[] }>(`${d(pid, did)}/checks`);
