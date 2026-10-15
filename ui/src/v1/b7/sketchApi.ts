// F3: the sketch routes (card D). The picture is read on this machine; it never leaves.
import { apiSend } from "../../api/client";
import { readBase64 } from "../i3/api";

export type BoxStatus = "possible" | "needs_definition" | "not_possible";
export interface SketchBox {
  id: string; label: string; row: number; col: number; status: BoxStatus;
  maps_to?: { table: string; measure: string; kind: string } | null; why: string; question?: string | null; needs?: string | null; note?: string | null; headline?: boolean; alone?: boolean;
}
const d = (pid: string, did: string) => `/api/v1/build/p/${encodeURIComponent(pid)}/studio/${encodeURIComponent(did)}/sketch`;

export const readSketchFile = async (pid: string, did: string, file: File) =>
  apiSend<{ boxes: SketchBox[]; title?: string }>("POST", d(pid, did), { name: file.name, data: await readBase64(file) });
export const readSketchLabels = (pid: string, did: string, labels: string[]) =>
  apiSend<{ boxes: SketchBox[] }>("POST", d(pid, did), { labels });
export const buildSketch = (pid: string, did: string, boxes: SketchBox[], title = "") =>
  apiSend<{ placed: number; step: number }>("POST", `${d(pid, did)}/build`, { boxes, ...(title ? { title } : {}) });
export const requestSketch = (pid: string, did: string, boxes: SketchBox[]) =>
  apiSend<{ request_id: string }>("POST", `${d(pid, did)}/request`, { boxes });
