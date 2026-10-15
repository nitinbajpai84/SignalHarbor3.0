// X5: the extraction spec, the review queue and the revised spec, through the shared client.
import { apiGet, apiSend } from "../../api/client";

export type Format = "number" | "date" | "percent" | "text";
export interface Field { name: string; meaning: string; format: Format; where_usually: string; required: boolean }
export interface Check { kind: "present" | "parses" | "range" | "ties_to"; field: string; detail: string }
export interface Revision { field: string; why: string; fields: Field[]; before_after: { file: string; field: string; before: string; after: string }[] }
export interface DocType {
  id: string; name: string; sample_files: string[]; fields: Field[]; checks: Check[]; version: number;
  examples: { file: string; field: string; value: string }[]; state: "proposed" | "confirmed"; revision: Revision | null;
}
export interface DocRow { doc_id: string; file: string; type_name: string; version: number; status: "ok" | "review"; at: string }
export interface Overview { types: DocType[]; documents: DocRow[]; queue: { count: number; line: string } }
export interface Value { value: string; raw: string; line: number | null; by: "model" | "rules" | "person" }
export interface CheckResult extends Check { ok: boolean; why: string }
export interface Extraction {
  doc_id: string; file: string; intent_id: string; type: string; type_name: string; version: number;
  values: Record<string, Value>; checks: CheckResult[]; status: "ok" | "review"; lines: string[];
}
export interface QueueItem { doc_id: string; file: string; type: string; intent_id: string; failed: { field: string; kind: string; why: string }[] }
export interface Queue { count: number; line: string; items: QueueItem[] }

const base = (iid: string) => `/api/v1/intents/${encodeURIComponent(iid)}/extract`;
export const getOverview = (iid: string) => apiGet<Overview>(base(iid));
export const propose = (iid: string, file: string) => apiSend<DocType>("POST", `${base(iid)}/propose`, { file });
export const confirmType = (iid: string, tid: string) => apiSend<Overview>("PUT", `${base(iid)}/types/${encodeURIComponent(tid)}`, { confirm: true });
export const decideRevision = (iid: string, tid: string, accept: boolean) =>
  apiSend<DocType>("POST", `${base(iid)}/types/${encodeURIComponent(tid)}/revision`, { accept });
export const getQueue = () => apiGet<Queue>("/api/v1/extract/queue");
export const getExtraction = (docId: string) => apiGet<Extraction>(`/api/v1/extract/${encodeURIComponent(docId)}`);
export const accept = (docId: string, values: Record<string, string>) =>
  apiSend<{ extraction: Extraction; revision: Revision | null }>("POST", `/api/v1/extract/${encodeURIComponent(docId)}/accept`, { values });
export const fileName = (path: string) => path.split("/").pop() ?? path;
