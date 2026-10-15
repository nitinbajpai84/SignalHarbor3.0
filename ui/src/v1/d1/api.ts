// V5 D1: Delivery against sh_platform/v1/d1_routes.py.
import { apiGet, apiSend } from "../../api/client";

export type Kind = "consume" | "morning_note" | "slack" | "teams" | "email" | "alert" | "webhook";
export type ChannelStatus = "draft" | "submitted" | "approved" | "stopped";
export interface Channel {
  id: string; kind: Kind; label: string; title: string; dashboard_id: string; status: ChannelStatus; live: boolean; set_up: boolean;
  when: { freq: string; at: string }; made_by_name: string; approved_by_name?: string; approved_at?: string; last_sent: string | null;
  sent_back: { reason: string; by: string; at: string } | null; addresses?: string[]; alert?: { tile: string; op: "lt" | "gt"; limit: string; via: string };
  preview: { subject: string; text: string; tile?: string | null } | null; can: { submit: boolean; approve: boolean; stop: boolean };
}
export interface Figures {
  month: string; month_name: string; portfolio_pct: string; benchmark_pct: string; difference_pts: string; version: number | null; name: string | null; code: string; portfolio: string;
  state: string; accepted_by: string | null; sentence: string; email_subject: string; note_line: string; mix: { component: string; weight_pct: string }[];
}
export interface OutboxRow { id: string; channel_id: string; kind: Kind; title: string; at: string; trigger: string; status: "sent" | "held" | "blocked"; reason: string; subject: string; preview: string }
export interface HookState { kind: Kind; label: string; secret: string; host: string; configured: boolean }
export interface Settings { channels: HookState[]; email: { configured: boolean; domains: string[] } }
export interface Delivery {
  project_id: string; channels: Channel[]; kinds: { kind: Kind; label: string }[]; dashboards: { id: string; title: string }[]; live_at: string | null;
  settings: Settings; outbox: OutboxRow[]; figures?: Figures | null; can: { make: boolean; go_live: boolean; settings: boolean };
}
export interface Summary {
  project_id: string; title: string | null; complete: boolean; live_at: string | null; verified: { text: string; by: string }[];
  steps?: { n: number; label: string; who: string; state: string | null }[]; figures?: Figures | null;
  knowledge?: { group: string; items: { text: string; verified: boolean }[] }[];
  delivered_to: { id: string; kind: Kind; label: string; title: string; approved_by: string; approved_at: string; live: boolean }[]; not_approved: string[];
}
export interface NewChannel { kind: Kind; dashboard_id: string; title?: string; when?: string; at?: string; addresses?: string; alert?: { tile: string; op: "lt" | "gt"; limit: string; via: string } }

const b = (pid: string) => `/api/v1/build/p/${encodeURIComponent(pid)}/delivery`;
export const getDelivery = (pid: string) => apiGet<Delivery>(b(pid));
export const getSummary = (pid: string) => apiGet<Summary>(`${b(pid)}/summary`);
export const createChannel = (pid: string, c: NewChannel) => apiSend<Channel>("POST", `${b(pid)}/channels`, c);
export const stepChannel = (pid: string, cid: string, step: "submit" | "approve" | "stop") => apiSend<Channel>("POST", `${b(pid)}/channels/${cid}/${step}`, {});
export const sendBack = (pid: string, cid: string, reason: string) => apiSend<Channel>("POST", `${b(pid)}/channels/${cid}/send-back`, { reason });
export const goLive = (pid: string) => apiSend<{ live: string[]; sent_now: number }>("POST", `${b(pid)}/go-live`, {});
export const retry = (pid: string, oid: string) => apiSend<OutboxRow>("POST", `${b(pid)}/outbox/${oid}/retry`, {});
export const getSettings = () => apiGet<Settings>("/api/v1/settings/delivery");
export const putSettings = (kind: Kind, secret: string, host: string) => apiSend<Settings>("PUT", "/api/v1/settings/delivery", { kind, secret, host });
