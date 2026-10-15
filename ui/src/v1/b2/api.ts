// B2: the scan report as V1-BUILD.md names it, through the shared client.
import { apiGet, apiSend } from "../../api/client";

export type ScanStatus = "available" | "partly" | "not";
export interface ScanKpi { code: string; status: ScanStatus; sources_used: string[]; missing: { what: string; where_expected: string }[] }
export interface Scan { intent_id: string; at: string; kpis: ScanKpi[]; agreed: { by: string; at: string; scope: string[] } | null }
export interface ScanView { scan: Scan | null; names: Record<string, string>; files: { path: string; columns: string[]; rows: number }[] }

const base = (iid: string) => `/api/v1/build/${encodeURIComponent(iid)}/scan`;
export const getScan = (iid: string) => apiGet<ScanView>(base(iid));
export const runScan = (iid: string) => apiSend<ScanView>("POST", base(iid));
export const agreeScope = (iid: string, scope: string[]) => apiSend<ScanView>("POST", `${base(iid)}/agree`, { scope });
export const sendBack = (iid: string, reason: string) => apiSend<ScanView>("POST", `${base(iid)}/send-back`, { reason });
