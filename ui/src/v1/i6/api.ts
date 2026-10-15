// I6b: the one screen's calls (I6a chat and open intent, I1 company), through the shared client. Types and the file reader come
// from I3 and I4 so the records stay one contract.
import { apiGet, apiSend } from "../../api/client";
import type { Thread, ThreadFile } from "../i3/api";
import type { Sow } from "../i4/api";
import type { Layout } from "../t1/api";
import type { Used } from "../teach/api";
import type { Proposed } from "../workbench/proposals";

export { kindOf, readBase64 } from "../i3/api";
export { editLine } from "../i4/api";
export type { ThreadFile, Sow };

type Process = NonNullable<Sow["process"]>;
export type Step = Process["steps"][number];
/** I6a's view: the thread record flattened, the SOW and the process map. Ready is the thread's `sow_ready`. */
export interface Chat extends Thread { used?: Used[]; id: string; sow: Sow; process_map: Process; layout?: Layout | null; proposals?: Proposed;
  landing?: boolean; project_id?: string | null; build?: { by: string; at: string; project_id: string | null } | null }
export interface UpFile { name: string; data: string; kind: ThreadFile["kind"] }

const base = (iid: string) => `/api/v1/intents/${encodeURIComponent(iid)}`;
const body = (text: string, files: UpFile[]) => (files.length ? { text, files } : { text });

export const getOpen = () => apiGet<{ id: string | null; greeting: string; recent?: { id: string; title: string; state: string }[] }>("/api/v1/intents/open");
export const startChat = (text: string, files: UpFile[], templateId?: string) =>
  apiSend<Chat>("POST", "/api/v1/intents/chat", templateId ? { ...body(text, files), template_id: templateId } : body(text, files));
export const getChat = (iid: string) => apiGet<Chat>(`${base(iid)}/chat`);
export const sendChat = (iid: string, text: string, files: UpFile[]) => apiSend<Chat>("POST", `${base(iid)}/chat`, body(text, files));
export const sendChatFile = (iid: string, f: UpFile) => apiSend<ThreadFile>("POST", `${base(iid)}/chat/files`, f);
/** I1: the signed intent of work is ready for Build; the head of data gets a card in Action. */
export const sendToBuild = (iid: string) => apiSend<NonNullable<Chat["build"]>>("POST", `${base(iid)}/send-to-build`);
export const downloadHref = (iid: string) => `${base(iid)}/sow/download`;

export interface Company {
  who: Record<string, { value: string | null }>;
  systems: { name: string | null }[];
  documents: { doc_id: string; title: string; filename: string }[];
}
export const getCompany = () => apiGet<Company>("/api/v1/company");

/** K7: the SOP of a signed intent of work (GET /api/v1/intents/{iid}/sop; the download is the same path + /download). */
export interface Sop {
  title: string; version: number; signed: string; purpose: string; scope: string; roles: string[]; systems: string[];
  steps: { n: number; name: string; who: string; system: string; does: string; input: string; output: string; control: string; exception: string;
    manual: boolean; handovers: { to_step: number; what: string }[] }[];
  manual_steps: number[]; controls: string[]; definitions: string[]; open_points: string[];
}
export const getSop = (iid: string) => apiGet<Sop>(`${base(iid)}/sop`);
export const sopHref = (iid: string) => `${base(iid)}/sop/download`;
