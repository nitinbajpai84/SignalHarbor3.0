// K11: shapes of sh_platform/v1/k11_routes.py. Figures are Decimal strings: `value` a fraction (0.035), `pct` the same in percent to 4 places.
import { apiGet } from "../../api/client";
import type { Fig } from "../k7/api";

export interface TrailRef { kind: string; id: string; as_of: string; date: string }
export interface Sleeve {
  sleeve: string; label: string; portfolio_weight: Fig | null; benchmark_weight: Fig; active_weight: Fig | null; portfolio_return: Fig | null; benchmark_return: Fig;
  contribution: Fig | null; allocation: Fig | null; selection: Fig | null; interaction: Fig | null; total: Fig | null; trail: TrailRef[]; benchmark_source: { code: string; version: number };
  masked?: boolean; note?: string;  // a sleeve holding a fund the viewer may not see: only the benchmark side is given
}
export interface FundLine {
  instrument_id: string | null; name: string; sleeve: string; visible: boolean; asset_class?: string | null;
  weight?: Fig; return?: Fig | null; contribution?: Fig; trail?: TrailRef[];
}
export type Split = { available: false; missing: string } | { available: true; attribute: string; groups: Record<string, { weight: Fig; contribution: Fig }> };
export interface Attribution {
  portfolio: { id: string; code: string }; benchmark_code: string; period: { start: string; end: string };
  version_used: { version: number; status: string; name: string } | null; certified: boolean; problems: string[];
  sleeves: Sleeve[]; funds: FundLine[]; splits: Record<string, Split>;
  totals: { portfolio_return: Fig | null; benchmark_return: Fig; active_return: Fig | null; allocation: Fig; selection: Fig; interaction: Fig; explained: Fig; unexplained: Fig | null;
    reconciles: boolean | null; partial: boolean; note?: string } | null;  // partial: some sleeves are masked, totals cover the sleeves shown
}

export const getAttribution = (portfolio: string, code: string, month: string) =>
  apiGet<Attribution>(`/api/v1/attribution?portfolio=${encodeURIComponent(portfolio)}&code=${encodeURIComponent(code)}&start=${month}&end=${month}`);
