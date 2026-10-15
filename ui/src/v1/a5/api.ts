// A1: the Reconciliations tab. Routes are E3b's (`GET /api/v1/recon/runs`, `POST /api/v1/recon/{code}/run`); shapes from sh_platform/v1/e3_recon.py.
import { apiGet, apiSend } from "../../api/client";

export interface ReconRun {
  recon_code: string; as_of_date: string; ran_at: string; checked: number; breaks: number; opened: string[]; skipped: string[];
  tolerance_rule_version_id?: string | null;
}
/** The two checks E3b knows (e3_recon.CODES), with the words a person reads. */
export const CHECKS: { code: string; title: string; what: string }[] = [
  { code: "cash_by_entity", title: "Cash by entity", what: "Administrator cash against the trading export, for each legal entity." },
  { code: "nav_vs_investment", title: "NAV against investments", what: "Each portfolio's NAV against the sum of its investment valuations." },
  { code: "limits", title: "Limits", what: "Each portfolio's share in a class, manager or holding against the signed limits." },
  { code: "trade_vs_admin", title: "Trades against the administrator", what: "The trading export against the administrator's record, for the last 30 days." },
];
export const listRuns = () => apiGet<ReconRun[]>("/api/v1/recon/runs");
/** `cutoff`: only what had arrived by then counts (a past month re-checked as it stood when its files came in); blank means now. */
export const runCheck = (code: string, asOf: string, cutoff = "") => apiSend<ReconRun>("POST", `/api/v1/recon/${encodeURIComponent(code)}/run`,
  cutoff ? { as_of_date: asOf, cutoff } : { as_of_date: asOf });
