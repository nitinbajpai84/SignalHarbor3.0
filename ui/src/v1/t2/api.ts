// T2: the ticket centre (sh_platform/v1/t2_routes.py).
import { apiGet, apiSend, downloadFile } from "../../api/client";

export type State = "open" | "in_progress" | "waiting" | "resolved" | "closed";
export interface TicketRow {
  id: string; title: string; project: string | null; project_title: string | null; stage: string; stage_name: string;
  assigned_to: string; assigned_name: string; raised_by: string; raised_name: string; state: State; priority: "normal" | "high";
  due: string | null; created_at: string; last_change: { at: string; text: string }; age_days: number;
}
export interface TicketLink { kind: string; ref: string; label: string; href: string | null; locked: boolean; preview?: string | null }
export interface LogEntry { at: string; by: string; action: string; from: string | null; to: string | null; note: string; text: string }
export interface Ticket extends TicketRow { body: string; links: TicketLink[]; can_act: boolean; log: LogEntry[] }
export interface Filters { project?: string; stage?: string; assignee?: string; raised_by?: string; state?: string; priority?: string }

export const STATE_NAMES: Record<State, string> = { open: "Open", in_progress: "In progress", waiting: "Waiting", resolved: "Resolved", closed: "Closed" };

export const listTickets = (f: Filters) => {
  const q = new URLSearchParams(Object.entries(f).filter(([, v]) => v) as [string, string][]).toString();
  return apiGet<{ tickets: TicketRow[]; stages: Record<string, string> }>(`/api/v1/tickets${q ? `?${q}` : ""}`);
};
const t = (id: string) => `/api/v1/tickets/${encodeURIComponent(id)}`;
export const getTicket = (id: string) => apiGet<Ticket>(t(id));
export const getPeople = () => apiGet<{ people: string[]; agents: Record<string, string> }>("/api/v1/tickets/people");
export const raiseTicket = (body: { title: string; body?: string; project?: string; stage?: string; priority?: string; assigned_to?: string }) =>
  apiSend<Ticket>("POST", "/api/v1/tickets", body);
export const delegate = (id: string, to: string, note: string) => apiSend<Ticket>("POST", `${t(id)}/delegate`, { to, note });
export const comment = (id: string, text: string) => apiSend<Ticket>("POST", `${t(id)}/comment`, { text });
export const setState = (id: string, state: State, note = "") => apiSend<Ticket>("POST", `${t(id)}/state`, { state, note });
export const work = (id: string) => apiSend<Ticket>("POST", `${t(id)}/work`);
export const downloadLog = (id: string) => downloadFile(`${t(id)}/log.csv`, `${id}-audit-log.csv`);
