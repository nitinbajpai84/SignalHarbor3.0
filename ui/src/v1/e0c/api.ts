// E0c3: data intake (E0c1 routes /api/v1/intake/..., E0b2 routes /api/v1/model/mappings/...). Paths are assumed from the card; see the landing note.
import { ApiError, apiGet, apiSend } from "../../api/client";
import type { PillTone } from "../../design";

export type FileState = "new" | "profiled" | "waiting_for_mapping" | "loaded" | "nothing_loaded" | "rejected_totals" | "quarantined";
export const STATE_NAMES: Record<FileState, string> = {
  new: "New", profiled: "Read, not yet mapped", waiting_for_mapping: "Waiting for mapping approval", loaded: "Loaded", nothing_loaded: "Nothing loaded",
  rejected_totals: "Rejected: totals differ", quarantined: "Quarantined",
};
export const STATE_TONES: Record<FileState, PillTone> = {
  new: "open", profiled: "draft", waiting_for_mapping: "late", loaded: "signed", nothing_loaded: "late", rejected_totals: "failed", quarantined: "restricted",
};

export interface IntakeFile { id: string; name: string; source_code: string; source_label?: string; state: FileState; owner: string | null; received_at: string; last_load_at: string | null }
export interface ProfileColumn { name: string; unit?: string | null; date_format?: string | null; kind?: string | null }
export interface Profile { sheet: string; header_row: number; columns: ProfileColumn[]; units?: string | null; date_format?: string | null; purpose?: string | null }
export interface MappingColumn { source_column: string; target_table: string; target_field: string; transform: string | null; date_format?: string | null; multiply?: number | null; decimal?: string | null }
export interface Mapping { id: string; version: number; state: "proposed" | "approved" | "retired"; can_decide: boolean; can_edit?: boolean; can_fix?: boolean; fixed?: Record<string, string>; columns: MappingColumn[] }
export interface ControlTotal { measure: string; in_file: string; loaded: string; passed: boolean }
export interface LoadResult { state: string; message: string; held_back?: string[] }
export interface FundWaiting { name: string; identifier_id: string | null; status: string; candidates: string[] }
export interface NeedsApproval { funds: FundWaiting[]; portfolios: string[]; choose_portfolio?: { entity: string; options: string[] }[]; can_approve: boolean }
export interface FileDetail extends IntakeFile { profile: Profile | null; mapping: Mapping | null; control_totals: ControlTotal[]; load_result: LoadResult | null; can_act: boolean; needs_approval?: NeedsApproval; target_options?: string[] }
export interface MappingEdit { source: string; target: string; date_format?: string; multiply?: string; decimal?: string }

const f = (id: string) => `/api/v1/intake/files/${encodeURIComponent(id)}`;
export const listFiles = () => apiGet<{ files: IntakeFile[]; can_upload?: boolean }>("/api/v1/intake/files");
export const getFile = (id: string) => apiGet<FileDetail>(f(id));
export const profileFile = (id: string) => apiSend<FileDetail>("POST", `${f(id)}/profile`);
export const loadFile = (id: string) => apiSend<LoadResult>("POST", `${f(id)}/load`);
/** UC5: every sheet of a workbook in one step, each with its own mapping (sheets already loaded are left as they are). */
export const loadAllSheets = (id: string) => apiSend<LoadResult>("POST", `${f(id)}/load`, { sheet: "*" });
export const acceptMapping = (mid: string) => apiSend<Mapping>("POST", `/api/v1/model/mappings/${encodeURIComponent(mid)}/approve`);
export const editMapping = (mid: string, columns: MappingEdit[], fixed?: Record<string, string>) =>
  apiSend<Mapping>("PUT", `/api/v1/model/mappings/${encodeURIComponent(mid)}`, fixed ? { columns, fixed } : { columns });
export const approveFund = (identifierId: string) => apiSend<unknown>("POST", `/api/v1/evidence/aliases/${encodeURIComponent(identifierId)}/approve`);
export const rejectMapping = (mid: string, reason: string) => apiSend<Mapping>("POST", `/api/v1/model/mappings/${encodeURIComponent(mid)}/reject`, { reason });

export interface MonthResult { files: Record<string, { file_id: string | null; state: string; message: string }>; trade_files: number; other_files: number }
// A month of files in one action: the server sends trade files through the trade loader and every other file the normal way.
export async function loadMonth(picked: File[]): Promise<MonthResult> {
  const csrf = document.cookie.split("; ").find((c) => c.startsWith("sh_csrf="));
  const body = new FormData();
  picked.forEach((f) => body.append("file", f));
  const res = await fetch("/api/v1/intake/month", { method: "POST", credentials: "same-origin", headers: { "X-CSRF-Token": csrf ? decodeURIComponent(csrf.slice(8)) : "" }, body });
  if (!res.ok) {
    let message = "Those files did not go through. Please try again.";
    try { const j = (await res.json()) as { message?: string }; if (j.message) message = j.message; } catch { /* keep the plain sentence */ }
    throw new ApiError(message, res.status);
  }
  return (await res.json()) as MonthResult;
}

// Multipart upload: the shared JSON client cannot send a file, so this one call posts the form itself (same CSRF header).
export async function uploadFile(file: File, receivedOn = ""): Promise<IntakeFile> {  // receivedOn: the day it really arrived (UC5)
  const csrf = document.cookie.split("; ").find((c) => c.startsWith("sh_csrf="));
  const body = new FormData();
  body.append("file", file);
  if (receivedOn) body.append("received_on", receivedOn);
  const res = await fetch("/api/v1/intake/upload", { method: "POST", credentials: "same-origin", headers: { "X-CSRF-Token": csrf ? decodeURIComponent(csrf.slice(8)) : "" }, body });
  if (!res.ok) {
    let message = "That file did not go through. Please try again.";
    try { const j = (await res.json()) as { message?: string }; if (j.message) message = j.message; } catch { /* keep the plain sentence */ }
    throw new ApiError(message, res.status);
  }
  return (await res.json()) as IntakeFile;
}
