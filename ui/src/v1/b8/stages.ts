import type { Plan, Run, Schedule } from "../b6/api";

// BC1: the pipeline as four stages with a state each. All pure, so the room and its test share one reading of the runs.
export type StageState = "new" | "approved" | "running" | "ok" | "late" | "failed";
export const STATE_WORD: Record<StageState, string> = { new: "New", approved: "Approved", running: "Running", ok: "Ok", late: "Late", failed: "Failed" };
export const STATE_TONE = { new: "open", approved: "signed", running: "draft", ok: "ok", late: "late", failed: "failed" } as const;
export const STAGES = [
  { id: "sources", name: "Sources", line: "Files as they arrive" },
  { id: "bronze", name: "Bronze", line: "Raw, as landed" },
  { id: "silver", name: "Silver", line: "The company model" },
  { id: "gold", name: "Gold", line: "Ready for dashboards" },
] as const;
export interface Stage { id: (typeof STAGES)[number]["id"]; name: string; line: string; state: StageState; items: string[]; last: string | null; next: string | null }

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const hm = (s: Schedule) => { const [h, m] = (s.at || "06:00").split(":"); return [Number(h) || 0, Number(m) || 0] as const; };
const wd = (s: Schedule) => { const i = DAYS.indexOf(String(s.day ?? "").slice(0, 3).toLowerCase()); return typeof s.day === "number" ? s.day % 7 : i < 0 ? 0 : i; };
const dom = (s: Schedule) => Math.min(Math.max(Number(s.day) || 1, 1), 28);
const add = (d: Date, days: number) => { const x = new Date(d); x.setDate(x.getDate() + days); return x; };

/** The newest slot at or before now (as the server scheduler reads it); null for "when a file arrives". */
export function lastSlot(s: Schedule, now: Date): Date | null {
  const [h, m] = hm(s);
  const today = new Date(now); today.setHours(h, m, 0, 0);
  if (s.freq === "daily") return today <= now ? today : add(today, -1);
  if (s.freq === "weekly") { const t = add(today, -((now.getDay() + 6 - wd(s)) % 7)); return t <= now ? t : add(t, -7); }
  if (s.freq === "monthly") { const t = new Date(today); t.setDate(dom(s)); if (t <= now) return t; t.setMonth(t.getMonth() - 1); return t; }
  return null;
}
export function nextSlot(s: Schedule, now: Date): Date | null {
  const [h, m] = hm(s);
  const last = lastSlot(s, now);
  if (!last) return null;
  if (s.freq === "daily") return add(last, 1);
  if (s.freq === "weekly") return add(last, 7);
  const t = new Date(last); t.setMonth(t.getMonth() + 1); t.setDate(dom(s)); t.setHours(h, m, 0, 0); return t;
}

/** The core silver tables this plan's lineage and depends_on name without rebuilding them (what its gold tables read), in plan order. */
export function silverRead(plan: Plan): string[] {
  const planned = new Set(plan.tables.map((t) => t.name));
  const names = [...plan.tables.flatMap((t) => t.depends_on ?? []), ...(plan.lineage ?? []).flatMap((e) => [e.from, e.to])];
  return [...new Set(names.filter((n) => !planned.has(n) && !n.startsWith("bronze_") && !n.startsWith("gold_") && !plan.sources.some((x) => x.code === n)))];
}

export function stages(plan: Plan | null, runs: Run[], now: Date, fallback: { bronze?: string[]; silver?: string[]; gold?: string[] } = {}): Stage[] {
  const latest = runs[0];
  const live = plan?.state === "live";
  const last = latest ? (latest.finished ?? latest.started) : null;
  const slot = plan && live ? lastSlot(plan.schedule, now) : null;
  const next = plan && live ? nextSlot(plan.schedule, now) : null;
  const behind = !!(slot && (!last || new Date(last) < slot));
  const read = plan ? silverRead(plan) : [];
  return STAGES.map((s) => {
    const own = plan?.tables.filter((t) => t.layer === s.id).map((t) => t.name) ?? [];
    const items = s.id === "sources" ? (plan?.sources ?? []).map((x) => x.code)
      : s.id === "silver" && plan ? [...new Set([...own, ...read])] // never the whole company model: only what this project's gold reads
      : own.length ? own : fallback[s.id] ?? [];
    let state: StageState = "new";
    if (s.id === "sources") state = plan?.sources.some((x) => x.files.length) ? (behind ? "late" : "ok") : "new";
    else if (plan && ["approved", "built", "live"].includes(plan.state)) {
      const mine = new Set(items);
      if (latest?.status === "running") state = "running";
      else if (latest?.steps.some((x) => mine.has(x.table) && x.status === "failed")) state = "failed";
      else if (latest?.status === "failed") state = latest.steps.some((x) => x.status === "failed") ? "late" : "failed"; // a stage after the broken one did not refresh
      else if (live && latest?.status === "ok") state = behind ? "late" : "ok";
      else state = "approved";
    }
    return { ...s, state, items, last: s.id === "sources" ? null : last, next: next ? next.toISOString() : null };
  });
}
