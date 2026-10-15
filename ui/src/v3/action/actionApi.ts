// The skills calls (HARBOR-SPEC, "Added 15 Oct"). Everything else on these pages comes from ../api.
import { apiGet, apiSend } from "../../api/client";

export type SkillStatus = "in_use" | "waiting" | "retired";
export type Centre = "intent" | "build" | "action" | "consume" | "knowledge";
export type Source = "core" | "industry" | "office";
export interface SkillRow {
  id: string; name: string; goal: string; when: string; centre: Centre; source: Source; tier: "fast" | "strong" | "tools";
  version: number; status: SkillStatus; tested: { passed: number; total: number } | null; used: number;
  last_changed: { by: string; at: string } | null;
}
export interface SkillTest { input: string; expected: string; got: string; ok: boolean }
export interface SkillDetail extends SkillRow {
  inputs: string; output: string; steps: string[]; tools: string[]; checks: string[]; never: string[];
  history: { v: number; at: string; by: string; change: string }[];
  why?: string; evidence?: { at: string; text: string }[]; tests?: SkillTest[]; cache?: { answers: number; golden: number };
}
/** The lines a person can change on a waiting skill: text fields hold a string, list fields a list of lines. */
export type TextField = "goal" | "when" | "inputs" | "output";
export type ListField = "steps" | "tools" | "checks" | "never";

const s = (id: string) => `/api/v3/skills/${encodeURIComponent(id)}`;
export const listSkills = () => apiGet<{ skills: SkillRow[] }>("/api/v3/skills");
export const getSkill = (id: string) => apiGet<SkillDetail>(s(id));
export const editSkill = (id: string, field: TextField | ListField, value: string | string[]) =>
  apiSend<SkillDetail>("POST", `${s(id)}/edit`, { field, value });
export const trySkill = (id: string) => apiSend<SkillDetail>("POST", `${s(id)}/try`, {});
export const admitSkill = (id: string) => apiSend<SkillDetail>("POST", `${s(id)}/admit`, {});
export const rejectSkill = (id: string, reason: string) => apiSend<SkillDetail>("POST", `${s(id)}/reject`, { reason });

export const CENTRE: Record<Centre, string> = { intent: "Intent", build: "Build", action: "Action", consume: "Consume", knowledge: "Knowledge" };
export const SOURCE: Record<Source, string> = { core: "Core", industry: "Industry", office: "This office" };
export const STATUS: Record<SkillStatus, string> = { in_use: "In use", waiting: "Waiting for you", retired: "Retired" };
export const when = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
};
