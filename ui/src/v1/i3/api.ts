// I3: the thread and SOW records as V1-BUILD.md names them, called through the shared client (never fetch here).
import { apiGet, apiSend } from "../../api/client";

export type Need = "goal" | "process" | "inputs" | "kpis" | "rules" | "unclear";
export interface ThreadFile { name: string; path: string; kind: "sample" | "document" }
export interface Turn { id: string; by: "person" | "north"; name: string; text: string; at: string; need: Need | null; files: ThreadFile[] }
export interface Thread { intent_id: string; turns: Turn[]; needs_done: Need[]; state: "open" | "sow_ready" }

export interface Sow {
  id: string; intent_id: string; title: string; state: "draft" | "signed"; version: number;
  goal: { line: string; why: string; readers: string[]; decisions: string[]; needed_by: string } | null;
  process: { steps: { n: number; name: string; who: string; does: string }[]; handovers: unknown[] } | null;
  kpis: { code: string; name: string; definition: string; unit: string; period: string; status: "defined" | "unclear"; pack_suggested: boolean }[];
  sources: { id: string; name: string; kind: "file" | "system" | "document"; holds: string }[];
  catalogue: { table: string; layer: string; meaning: string }[];
  governance: { rule: string; kind: string }[];
  unclear: { id: string; question: string; about: string; who_can_settle: string; settled: boolean }[];
}

const base = (iid: string) => `/api/v1/intents/${encodeURIComponent(iid)}`;

export const createIntent = (line: string) =>
  apiSend<{ id?: string; intent_id?: string }>("POST", "/api/v1/intents", { line });
export const getThread = (iid: string) => apiGet<Thread>(`${base(iid)}/thread`);
export const getSow = (iid: string) => apiGet<Sow>(`${base(iid)}/sow`);
export const sendTurn = (iid: string, text: string, files: ThreadFile[]) =>
  apiSend<unknown>("POST", `${base(iid)}/thread`, { text, files });
// The file travels as base64 in JSON, as 2.0's context_docs upload does; the answer is the stored file.
export const sendFile = (iid: string, name: string, data: string, kind: ThreadFile["kind"]) =>
  apiSend<ThreadFile>("POST", `${base(iid)}/thread/files`, { name, data, kind });

const SAMPLE = /\.(csv|xlsx|xls|tsv|json)$/i;
export const kindOf = (name: string): ThreadFile["kind"] => (SAMPLE.test(name) ? "sample" : "document");

export const readBase64 = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",")[1] ?? "");
    r.onerror = () => reject(new Error("read"));
    r.readAsDataURL(file);
  });
