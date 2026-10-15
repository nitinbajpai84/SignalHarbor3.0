// K7: shapes of sh_platform/v1/k7_routes.py. Returns are Decimal strings: `value` a fraction (0.035), `pct` rounded to 4 places ("3.5000").
import { apiGet } from "../../api/client";

export interface Fig { value: string; pct: string }
export interface Component { series_key: string; weight: string; spread_bps: string }
export interface Definition {
  benchmark_code: string; benchmark_name: string; version: number; currency: string; effective_from: string; effective_to: string | null;
  status: string; components: Component[]; notice?: string; policy_question?: { question: string; case: { case_id: string; title: string; status: string } | null };
}
export interface MonthComponent { series_key: string; weight: string; index_return: Fig | null; spread_return: Fig | null; return: Fig | null }
export interface MonthRow {
  month: string; period_start: string; period_end: string; portfolio: Fig | null; benchmark: Fig | null; difference: Fig | null; components: MonthComponent[];
  liquid_sleeve: (Fig & { difference: Fig | null }) | null; certified: boolean; problems: string[];
}
export interface Comparison {
  portfolio: { id: string; code: string }; benchmark_code: string; months: MonthRow[];
  version_used: { version: number; status: string; name: string; notice?: string } | null;
}

export const getDefinitions = () => apiGet<{ definitions: Definition[] }>("/api/v1/benchmarks");
export const getComparison = (portfolio: string, code: string, start: string, end: string) =>
  apiGet<Comparison>(`/api/v1/benchmarks/comparison?portfolio=${encodeURIComponent(portfolio)}&code=${encodeURIComponent(code)}&start=${start}&end=${end}`);

export const pct = (f: Fig | null) => (f ? `${f.pct}%` : "Not available yet");
/** A difference in percentage points with its sign: "+1.9065 pts". */
export const pts = (f: Fig | null) => (f ? `${f.pct.startsWith("-") ? "" : "+"}${f.pct} pts` : "Not available yet");
