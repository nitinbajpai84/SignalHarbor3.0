import { useCallback, useEffect, useState } from "react";

import * as b6 from "../b6/api";
import * as b7 from "../b7/api";
import * as api from "./api";
import { stages, type Stage } from "./stages";

// BC1: what the three room tiles count, and what the rooms draw. Each call may fail alone; a failed one just leaves its part empty.
export interface Facts { plan: b6.Plan | b6.NoPlan | null; runs: b6.Run[]; boards: b7.StudioRow[]; tables: api.ProjectTables | null; ready: boolean }
export function useFacts(pid: string): Facts & { reload: () => Promise<void> } {
  const [f, setF] = useState<Facts>({ plan: null, runs: [], boards: [], tables: null, ready: false });
  const reload = useCallback(async () => {
    if (!pid) return;
    const [plan, runs, boards, tables] = await Promise.all([
      b6.getPlan(pid).catch(() => null), b6.getRuns(pid).then((r) => r.runs).catch(() => []),
      b7.listStudio(pid).then((r) => r.dashboards).catch(() => []), api.getProjectTables(pid).catch(() => null)]);
    setF({ plan, runs, boards, tables, ready: true });
  }, [pid]);
  useEffect(() => { void reload(); }, [reload]);
  return { ...f, reload };
}

export const planOf = (p: Facts["plan"]): b6.Plan | null => (p && "tables" in p ? p : null);
export const stagesOf = (f: Facts, now = new Date()): Stage[] => stages(planOf(f.plan), f.runs, now, f.tables ?? {});

/** The live count on each tile, in plain words. */
export function counts(f: Facts) {
  const st = stagesOf(f);
  const ok = st.filter((s) => s.state === "ok").length, bad = st.filter((s) => s.state === "failed" || s.state === "late").length;
  const n = (s: string) => f.boards.filter((b) => b.status === s).length;
  const t = f.tables ? f.tables.bronze.length + f.tables.silver.length + f.tables.gold.length : planOf(f.plan)?.tables.length ?? 0;
  return {
    pipelines: !planOf(f.plan) ? "No plan yet" : bad ? `${bad} of 4 stages need a look` : `${ok} of 4 stages ok`,
    dashboards: f.boards.length ? `${n("published")} published, ${n("submitted")} waiting, ${n("draft")} draft` : "No dashboards yet",
    architecture: t ? `${t} tables in 3 layers` : "No tables yet",
  };
}
