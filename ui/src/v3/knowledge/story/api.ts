import { apiGet } from "../../../api/client";

export type ItemKind = "brief" | "gate" | "rule" | "brule" | "assumption" | "kpi" | "gold" | "silver" | "bronze" | "board" | "note" | "signal";
export interface Shared { id: string; title: string }
/** One box of a story; `detail` fills the right panel, `shared` lists the other use cases that use it. */
export interface Item {
  id: string; kind: ItemKind; label: string; sub: string; status?: string;
  detail: { k: string; v: string }[]; shared: Shared[]; links?: { label: string; to: string }[];
}
export interface Story {
  id: string; title: string; stage: string; stage_label: string; live: boolean; domain: { id: string; name: string };
  who: { name: string; role: string; at: string }; asked: string; conversation: string;
  decisions: Item[]; kpis: Item[]; gold: Item[]; silver: Item[]; bronze: Item[]; used_by: Item[]; edges: [string, string][];
}
export interface UseCaseRow { id: string; title: string; stage: string; stage_label: string; live: boolean; asked_by: string; role: string; figures: number; find: string }
export interface DomainCount { id: string; name: string; count: number }
export interface UseCases { groups: { domain: string; name: string; count: number; items: UseCaseRow[] }[]; domains: DomainCount[]; total: number }
export type RowKey = "decisions" | "kpis" | "gold" | "silver" | "bronze";
export interface DomainItem { id: string; label: string; sub: string; kind: ItemKind; cols: number[]; shared_outside: boolean }
export interface Domain {
  id: string; name: string; usecases: { id: string; title: string; who: string; role: string }[]; people: number;
  rows: Record<RowKey, { label: string; items: DomainItem[]; hidden: number }>; others: DomainCount[];
}
export interface LogicalObject {
  id: string; label: string; about: string; count: number | null; table: string;
  properties: { label: string; derived?: string }[]; relations: { to: string; to_label: string; label: string }[];
  kpis: { id: string; name: string; usecases: Shared[] }[];
}
export interface Logical { objects: LogicalObject[]; pack: { id: string; label: string; version: number } | null }
export interface PhysicalKpi { id: string; name: string; status: string; usecases: (Shared & { who: string })[]; used_by: { kind: string; label: string; sub: string }[]; gold: string[]; silver: string[]; bronze: string[] }
export interface Physical {
  bronze: { items: { id: string; label: string; rows: number; kinds: string }[]; total: number };
  silver: { items: { id: string; label: string; rows: number | null }[]; total: number };
  gold: { items: { id: string; label: string; rows: number | null; usecase: string }[]; total: number };
  kpis: { items: PhysicalKpi[]; total: number }; picked: PhysicalKpi | null; path: { gold: string[]; silver: string[]; bronze: string[] } | null;
}
export interface DecisionRow { id: string; kind: "rule" | "decision" | "assumption"; label: string; sub: string; detail: { k: string; v: string }[]; usecases: Shared[] }
export interface Decisions { items: DecisionRow[]; counts: Record<"rule" | "decision" | "assumption", number>; in_force: number }

const B = "/api/v3/knowledge";
export const getUseCases = () => apiGet<UseCases>(`${B}/usecases`);
export const getStory = (id: string) => apiGet<Story>(`${B}/usecase/${encodeURIComponent(id)}`);
export const getDomain = (id: string) => apiGet<Domain>(`${B}/domain/${encodeURIComponent(id)}`);
export const getLogical = () => apiGet<Logical>(`${B}/model/logical`);
export const getPhysical = (kpi?: string) => apiGet<Physical>(`${B}/model/physical${kpi ? `?kpi=${encodeURIComponent(kpi)}` : ""}`);
export const getDecisions = () => apiGet<Decisions>(`${B}/decisions`);

/** Everything on the path of one box: what it rests on and what rests on it, along the edges (both ways, transitively). */
export function pathOf(edges: [string, string][], id: string): Set<string> {
  const out = new Set([id]);
  for (const up of [true, false]) {
    const todo = [id];
    const seen = new Set([id]);
    while (todo.length) {
      const x = todo.pop() as string;
      for (const [a, b] of edges) {
        const [here, next] = up ? [b, a] : [a, b];
        if (here === x && !seen.has(next)) { seen.add(next); out.add(next); todo.push(next); }
      }
    }
  }
  return out;
}
export const KIND_NAME: Record<ItemKind, string> = {
  brief: "Decision", gate: "Decision", rule: "Rule", brule: "Rule in the brief", assumption: "Assumption", kpi: "KPI", gold: "Gold table", silver: "Silver table",
  bronze: "Bronze source", board: "Board", note: "Morning note", signal: "Signal",
};
export const day = (iso?: string) => {
  const d = iso ? new Date(`${iso.slice(0, 10)}T12:00:00`) : null;
  return d && !Number.isNaN(d.getTime()) ? d.toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : iso ?? "";
};
