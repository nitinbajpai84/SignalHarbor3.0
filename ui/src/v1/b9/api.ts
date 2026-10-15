// V5W-2: the assignment calls. Package 1 (V5W-1) owns the routes under /api/v1/projects/{pid}/assign*; the shapes below follow the plan
// and are read leniently, so a different field name degrades to "not shown", never to a crash. See docs/plan/v5-landings/V5W-2-build-shell.md.
import { apiGet, apiSend } from "../../api/client";
import type { StepId } from "./steps";

export interface Assignment { step: StepId; assignee: string; assignee_name?: string; role?: string; note?: string | null; due?: string | null; by?: string; by_name?: string; at?: string; state?: string }
export interface Candidate { id: string; name: string; role?: string; open_steps?: number }

const base = (pid: string) => `/api/v1/projects/${encodeURIComponent(pid)}`;
export const listAssignments = (pid: string) => apiGet<{ assignments: Assignment[] }>(`${base(pid)}/assignments`);
export const listCandidates = (pid: string) => apiGet<{ people: Candidate[] }>(`${base(pid)}/assign/candidates`);
export const assignSteps = (pid: string, body: { steps: StepId[]; to: string; note?: string; due?: string; handover?: boolean }) =>
  apiSend<{ assignments?: Assignment[] }>("POST", `${base(pid)}/assign`, body);

/** A person's name for display: names pass, raw ids (32 hex) do not. */
export const nice = (v: string | null | undefined): string => (!v ? "" : /^[0-9a-f]{24,}$/i.test(v) ? "A colleague" : v);
export const initials = (n: string): string => n.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w.charAt(0).toUpperCase()).join("") || "?";
