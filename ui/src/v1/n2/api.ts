// N2: comments with history. Routes are sh_platform/v1/n2_routes.py; the server decides who may see a thread and builds every word shown.
import { apiGet, apiSend } from "../../api/client";

export type CommentKind = "dashboard" | "widget" | "office_line" | "brief_line" | "case" | "valuation" | "position" | "cash" | "nav" | "metric" | "tile";
export interface Target { kind: CommentKind; id: string }
export interface Raised { id: string; number: string; link: string | null }
export interface Comment {
  id: string; parent_id: string | null; by: string; at: string; text: string | null; edited: boolean; edited_at: string | null;
  deleted: boolean; deleted_by: string | null; history: { text: string; at: string }[]; mentions: string[];
  case: Raised | null; ticket: Raised | null; may: { reply: boolean; edit: boolean; delete: boolean; raise: boolean };
}
export interface Thread { kind: string; id: string; count: number; comments: Comment[] }
export interface Written { id: string; not_told?: string[]; thread: Thread }

const q = (t: Target) => `kind=${encodeURIComponent(t.kind)}&id=${encodeURIComponent(t.id)}`;
export const getThread = (t: Target) => apiGet<Thread>(`/api/v1/comments?${q(t)}`);
export const getPeople = () => apiGet<{ name: string }[]>("/api/v1/comments/people");
export const addComment = (t: Target, text: string, parent_id?: string) => apiSend<Written>("POST", "/api/v1/comments", { ...t, text, parent_id });
export const editComment = (cid: string, text: string) => apiSend<Written>("PUT", `/api/v1/comments/${cid}`, { text });
export const deleteComment = (cid: string) => apiSend<Written>("DELETE", `/api/v1/comments/${cid}`);
export const raiseComment = (cid: string, as: "case" | "ticket") => apiSend<Written>("POST", `/api/v1/comments/${cid}/raise`, { as });
