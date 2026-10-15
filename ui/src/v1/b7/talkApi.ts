// STUDIO2 F1: talk and history against DASH = /api/v1/build/p/{pid}/studio/{did}.
import { apiGet, apiSend } from "../../api/client";
import type { Picture } from "../cxui/api";

export interface Step { n: number; at: string; by: string; said: string; summary: string }
export interface Compare { added: string[]; removed: string[]; changed: string[] }

const d = (pid: string, did: string) => `/api/v1/build/p/${encodeURIComponent(pid)}/studio/${encodeURIComponent(did)}`;
export const talk = (pid: string, did: string, body: { text: string; widget?: string; reading?: Picture }) =>
  apiSend<{ reply: string; changed: string[]; step: number }>("POST", `${d(pid, did)}/talk`, body);
export const getHistory = (pid: string, did: string) => apiGet<{ steps: Step[]; now: number }>(`${d(pid, did)}/history`);
export const undo = (pid: string, did: string) => apiSend<unknown>("POST", `${d(pid, did)}/undo`, {});
export const restore = (pid: string, did: string, n: number) => apiSend<unknown>("POST", `${d(pid, did)}/history/${n}/restore`, {});
export const compare = (pid: string, did: string, n: number) => apiGet<Compare>(`${d(pid, did)}/history/${n}/compare`);
export const withdraw = (pid: string, did: string) => apiSend<unknown>("POST", `${d(pid, did)}/withdraw`, {});
