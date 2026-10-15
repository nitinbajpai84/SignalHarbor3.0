// C3: Lumen's conversation and the consumption brief, through the shared client. The file reader comes from I3.
import { apiGet, apiSend } from "../../api/client";

import type { Proposed } from "../workbench/proposals";

export { readBase64 } from "../i3/api";

export interface BriefView { name: string; audience: string; kpis: string[]; comparisons: string[]; filters: string[]; refresh: string }
export interface Lever { name: string; affects: string[]; range: string }
export interface EndUserInput { by: string; question: string; answer: string; at: string }
export interface Brief {
  views: BriefView[]; feeds_wanted: string[]; levers: Lever[];
  existing_dashboards: { name: string; path?: string; note?: string }[]; end_user_inputs: EndUserInput[]; notes: string[];
}
export interface Turn { id: string; by: "person" | "lumen"; name: string; text: string; at: string; files?: { name: string }[] }
export interface LumenChat {
  intent_id: string | null; title?: string | null; line: string | null; turns: Turn[]; needs_done: string[]; state: "open" | "ready";
  brief: Brief; kpis: { code: string; name: string }[]; feeds: { id: string; kind: string }[]; skill: string;
  ask_next: string | null; greeting: string; me: string; proposals?: Proposed;
}
export interface UpFile { name: string; data: string }

const base = (iid: string) => `/api/v1/consume/brief/${encodeURIComponent(iid)}`;

export const getBrief = (iid?: string) => apiGet<LumenChat>(`/api/v1/consume/brief${iid ? `?iid=${encodeURIComponent(iid)}` : ""}`);
export const sendChat = (iid: string, text: string, files: UpFile[]) =>
  apiSend<LumenChat>("POST", `${base(iid)}/chat`, files.length ? { text, files } : { text });
export const sendInput = (iid: string, text: string) => apiSend<LumenChat>("POST", `${base(iid)}/input`, { text });
