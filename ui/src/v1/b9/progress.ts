import type { ProjectRow, PlanState } from "../b6/api";
import { STEPS, type StepId } from "./steps";

// V5W-2: where a project stands on the four steps. Pure, so the cards and the overview say the same thing.
export type Mark = "done" | "here" | "waiting" | "todo";
export interface RowView { marks: Mark[]; current: StepId; tag: string; line: string; live: boolean }

/** Optional fields the server may add to a project row; they win over the guess below. */
export type RowPlus = ProjectRow & { step?: StepId; waiting_for_me?: boolean; waiting_on?: string | null; note?: string | null; builder?: string | null };

const idx = (s: StepId) => STEPS.findIndex((x) => x.id === s);
const marksFor = (current: StepId, mark: Mark, allDone = false): Mark[] => STEPS.map((s, i) => (allDone || i < idx(current) ? "done" : i === idx(current) ? mark : "todo"));
const PLAN_LINE: Partial<Record<PlanState, string>> = { proposed: "Span proposed the tables. The head of data is checking them.", rejected: "The head of data sent the plan back.", approved: "The architecture is approved. Pipelines are next.", built: "The trial run is built on a copy." };

export function viewRow(r: RowPlus): RowView {
  if (r.stage === "live") return { marks: marksFor("dashboards", "done", true), current: "dashboards", tag: "LIVE · 4 OF 4", line: "Live and delivered.", live: true };
  let current: StepId = "architecture", mark: Mark = "here", tag = "STEP 2 · ARCHITECTURE";
  if (r.stage === "intent") { current = "intent"; tag = "STEP 1 · BEING DEFINED WITH NORTH"; }
  else if (r.plan_state === "proposed") { mark = "waiting"; tag = "WITH THE DATA TEAM · ARCHITECTURE"; }
  else if (r.plan_state === "approved" || r.plan_state === "built") { current = "pipelines"; tag = r.plan_state === "built" ? "TRIAL RUN · PIPELINES" : "STEP 3 · PIPELINES"; }
  if (r.step && idx(r.step) >= 0) { current = r.step; tag = `STEP ${idx(r.step) + 1} · ${(STEPS[idx(r.step)]?.name ?? "").toUpperCase()}`; }
  const line = (r.plan_state && PLAN_LINE[r.plan_state]) || (r.stage === "intent" ? "North is drafting the intent with the owner." : "Waiting for the plan from Span.");
  return { marks: marksFor(current, mark), current, tag, line: r.note || line, live: false };
}

export type Filter = "all" | "waiting" | "mine" | "live";
export function waitingForMe(r: RowPlus, canApprove: boolean): boolean {
  if (typeof r.waiting_for_me === "boolean") return r.waiting_for_me;
  return canApprove && r.plan_state === "proposed";
}
export function filterRows(rows: RowPlus[], f: Filter, me: string, canApprove: boolean): RowPlus[] {
  if (f === "waiting") return rows.filter((r) => waitingForMe(r, canApprove));
  if (f === "mine") return rows.filter((r) => !!me && r.owner === me);
  if (f === "live") return rows.filter((r) => r.stage === "live");
  return rows;
}
