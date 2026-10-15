// B3: the mapping sheet as V1-BUILD.md names it, through the shared client.
import { apiGet, apiSend, downloadFile } from "../../api/client";

export type Layer = "landing" | "silver" | "gold";
export type RowStatus = "mapped" | "unclear";
export interface MappingRow {
  n: number; layer: Layer; target_table: string; target_field: string; source_id: string; source_table: string; source_field: string;
  transformation: string; rule: string; test: string; status: RowStatus;
}
export interface Sheet { intent_id: string; version: number; rows: MappingRow[] }
export interface MappingView { sheet: Sheet; fallback: boolean; message: string | null; drafted_at: string | null }
export type RowEdit = Partial<Pick<MappingRow, "source_field" | "transformation" | "rule" | "test" | "status">>;

const base = (iid: string) => `/api/v1/build/${encodeURIComponent(iid)}/mapping`;
export const getMapping = (iid: string) => apiGet<MappingView>(base(iid));
export const draftMapping = (iid: string) => apiSend<MappingView>("POST", base(iid));
export const editRow = (iid: string, n: number, edit: RowEdit) => apiSend<{ row: MappingRow }>("PUT", `${base(iid)}/rows/${n}`, edit);
export const downloadSheet = (iid: string, version: number) => downloadFile(`${base(iid)}.xlsx`, `mapping-${iid}-v${version}.xlsx`);
