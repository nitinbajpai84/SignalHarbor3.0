// G1: who may see a project (sh_platform/v1/g1_routes.py), through the shared client.
import { apiGet, apiSend } from "../../api/client";
import type { Sensitivity } from "../k1/api";

export interface Member { name: string; role: string; account_id: string | null }
/** What a person who may not read the project is shown: Internal, its title, stage and owner; Restricted, only that it exists. */
export interface Lock {
  id: string; locked: true; access: "preview" | "none"; sensitivity: Sensitivity; can_request: boolean;
  title?: string; stage?: string; owner?: string; request: { id: string; state: string; at: string; expires: string | null } | null;
}
export interface Access {
  id: string; level: "full" | "read"; sensitivity: Sensitivity; team: Member[]; can_manage: boolean;
  requests: { id: string; requester: string; reason: string; at: string }[];
}

const base = (pid: string) => `/api/v1/projects/${encodeURIComponent(pid)}/access`;
export const getProjectAccess = (pid: string) => apiGet<Access | Lock>(base(pid));
export const setSensitivity = (pid: string, sensitivity: Sensitivity) => apiSend<unknown>("PUT", base(pid), { sensitivity });
export const requestProjectAccess = (pid: string, reason: string) => apiSend<unknown>("POST", `${base(pid)}/request`, { reason });
export const answerProjectRequest = (pid: string, id: string, approve: boolean, days: number, note = "") =>
  apiSend<unknown>("POST", `${base(pid)}/answer/${encodeURIComponent(id)}`, { approve, days, note });
export const isLock = (x: unknown): x is Lock => !!x && typeof x === "object" && (x as { locked?: boolean }).locked === true;
