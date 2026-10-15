import { apiGet, apiSend } from "../../api/client";

export { readBase64 } from "../i3/api";

// TEACH1: what each agent was taught (sh_platform/v1/teach_routes.py). The server decides who may teach which agent; this list is only what the menu offers.
export interface Teachable { key: string; name: string }
export interface Knowledge { id: string; agent: string; title: string; kind: "file" | "note"; name: string; size: number; taught_by: string; taught_at: string; active: boolean; version: number; always?: boolean }
export interface Used { id: string; title: string; passage: number; line: string }
export interface Body { title?: string; name?: string; data?: string; text?: string; always?: boolean }

const k = (agent: string) => `/api/v1/knowledge/${encodeURIComponent(agent)}`;
export const getTeachable = () => apiGet<{ agents: Teachable[] }>("/api/v1/knowledge").then((d) => d.agents);
export const getKnowledge = (agent: string) => apiGet<{ agent: string; items: Knowledge[] }>(k(agent)).then((d) => d.items);
export const teach = (agent: string, body: Body) => apiSend<Knowledge>("POST", k(agent), body);
export const replaceItem = (agent: string, id: string, body: Body) => apiSend<Knowledge>("PUT", `${k(agent)}/${encodeURIComponent(id)}`, body);
export const setActive = (agent: string, id: string, active: boolean) => apiSend<Knowledge>("POST", `${k(agent)}/${encodeURIComponent(id)}/active`, { active });

export { TEACH_RIGHTS, canTeach, teachable } from "../../shell/roles";
