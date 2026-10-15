// F1: the data engineer's conversation with Flow (sh_platform/v1/f1_routes.py) and B4's runs and load, through the shared client.
import { apiGet, apiSend, downloadFile } from "../../api/client";
import type { Run } from "../b4/RunsPage";
import type { Proposed } from "../workbench/proposals";

export type PointKind = "mapping" | "formula" | "check" | "document" | "deviation";
export interface Point {
  id: string; kind: PointKind; row: number | null; about: string; understood: string; needs: string; why: string | null;
  question: string; sql: string | null; flagged: { note: string; by: string; at: string } | null;
}
export interface Turn { id: string; by: "person" | "flow"; name: string; text: string; at: string; point: string | null }
export interface EngineerContext {
  catalogue_tables: number; mapping_rows: number; mapping_version: number | null; transformations: number; sql_rows: number;
  data_model_tables: number; runs: number; skill: string;
}
export interface Engineer { intent_id: string; turns: Turn[]; opening: string; points: Point[]; current: string | null; context: EngineerContext; handed_over: boolean; proposals?: Proposed }
export interface Contract { source: string; title: string; owner: string; schema: { field: string }[]; rules: string[]; marts: string[] }
export interface Runs { contracts: Contract[]; runs: Run[] }
export type { Run };

export { kindOf, readBase64 } from "../i3/api";
export interface UpFile { name: string; data: string; kind: "sample" | "document" }

const base = (iid: string) => `/api/v1/build/${encodeURIComponent(iid)}`;
export const getEngineer = (iid: string) => apiGet<Engineer>(`${base(iid)}/engineer`);
export const answer = (iid: string, text: string, point?: string, files: UpFile[] = []) =>
  apiSend<Engineer>("POST", `${base(iid)}/engineer`, { text, ...(point ? { point } : {}), ...(files.length ? { files } : {}) });
export const signPack = (iid: string) => apiSend<{ project: unknown }>("POST", `/api/v1/build/${encodeURIComponent(iid)}/pack/sign`);
export const flag = (iid: string, point: string, note: string) => apiSend<Engineer>("POST", `${base(iid)}/engineer/flag`, { point, note });
export const downloadFlagged = (iid: string) => downloadFile(`${base(iid)}/engineer/flagged.md`, `open-points-${iid}.md`);
export const getRuns = (iid: string) => apiGet<Runs>(`${base(iid)}/runs`);
export const runLoad = (iid: string) => apiSend<{ runs: Run[]; missing: { title: string; reason: string }[]; rows_left_out: number }>("POST", `${base(iid)}/load`);
