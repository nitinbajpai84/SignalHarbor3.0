// C4: the context library and each conversation's ticks (sh_platform/v1/c4_routes.py), through the shared client.
import { apiGet, apiSend } from "../../api/client";

export { readBase64 } from "../i3/api";

export interface LibItem {
  id: string; name: string; kind: "sample" | "document" | "external" | "picture"; note: string; uploaded_by: string; at: string;
  size: number; visibility: "private" | "company"; path: string; tags: string[]; mine: boolean; can_change: boolean;
  // K1: sensitivity, topic and the viewer's access state; a locked item carries only its preview
  sensitivity?: "open" | "internal" | "restricted"; topic?: string[]; locked?: boolean;
  folder?: string; folder_by?: "rules" | "Jev" | "owner"; subfolder?: string; sorting?: boolean;  // L3
  access?: "mine" | "open" | "granted" | "request" | "requested" | "denied";
  preview?: { contains_personal_data: boolean; kinds: string[]; columns?: string[] | null; heading?: string | null };
}
export interface Found { id: string; name: string; uploaded_by: string; at: string; note?: string }
export type UploadAnswer = { item: LibItem; message?: string } | { duplicate: Found } | { similar: Found[] };
export interface Upload {
  name: string; data: string; note?: string; share?: boolean; iid?: string; force?: boolean; kind?: LibItem["kind"];
  sensitivity?: "open" | "internal" | "restricted"; topic?: string[]; reviewed?: boolean;  // K1
  folder?: string; folder_by?: "rules" | "Jev" | "owner";  // L3
}

const ctx = (iid: string) => `/api/v1/intents/${encodeURIComponent(iid)}/context`;

export const listLibrary = (q = "") => apiGet<LibItem[]>(`/api/v1/library${q ? `?q=${encodeURIComponent(q)}` : ""}`);
export const uploadItem = (body: Upload) => apiSend<UploadAnswer>("POST", "/api/v1/library", body);
export const changeItem = (id: string, body: Partial<Pick<LibItem, "note" | "kind" | "visibility">>) =>
  apiSend<LibItem>("PUT", `/api/v1/library/${encodeURIComponent(id)}`, body);
export const deleteItem = (id: string) => apiSend<{ deleted: string }>("DELETE", `/api/v1/library/${encodeURIComponent(id)}`);
export const getContext = (iid: string) => apiGet<{ library_ids: string[]; items: LibItem[] }>(ctx(iid));
export const putContext = (iid: string, ids: string[]) => apiSend<{ library_ids: string[]; items: LibItem[] }>("PUT", ctx(iid), { library_ids: ids });
export const getSuggestions = (iid: string) => apiGet<LibItem[]>(`${ctx(iid)}/suggestions`);
