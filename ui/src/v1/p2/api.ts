// V5W-1: assignments and the Action landing. Shapes from sh_platform/v1/p2_assign.py (routes in p2_routes.py).
import { apiGet, apiSend } from "../../api/client";

export interface Assignment {
  id: string; event: string; pid: string; title: string | null; steps: string[]; to: string; by: string; message: string; due: string | null; at: string;
  link: string; assigned_by?: string;
}
export interface Waiting { kind: "dashboard" | "plan" | "intent" | "delivery" | "pack"; title: string; project: string; from: string | null; since: string; link: string }
export interface Landing {
  viewer: string; counts: Record<"needs_me" | "assigned_to_me" | "assigned_by_me" | "waiting_approval" | "worth_a_look", number>;
  assigned_to_me: Assignment[]; assigned_by_me: Assignment[]; waiting_approval: Waiting[];
}
export interface ProjectAssignments {
  project: { id: string; title: string | null; owner: string | null }; steps: { id: string; label: string }[]; open: Assignment[]; history: Assignment[];
}
export interface AssignBody { steps?: string[]; to: string; message: string; due: string | null }

export const getLanding = () => apiGet<Landing>("/api/v1/action/landing");
export const getAssignments = (pid: string) => apiGet<ProjectAssignments>(`/api/v1/projects/${encodeURIComponent(pid)}/assignments`);
export const assignSteps = (pid: string, b: AssignBody) => apiSend<Assignment>("POST", `/api/v1/projects/${encodeURIComponent(pid)}/assign`, b);
export const handOver = (pid: string, b: AssignBody) => apiSend<Assignment>("POST", `/api/v1/projects/${encodeURIComponent(pid)}/handover`, b);
export const finishAssignment = (id: string, how: "done" | "withdraw") => apiSend<unknown>("POST", `/api/v1/assignments/${encodeURIComponent(id)}/${how}`, {});
export const getPeople = () => apiGet<{ name: string }[]>("/api/v1/comments/people");
