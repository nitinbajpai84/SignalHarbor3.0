// V5W-3: the Pipelines step's verify and business-review calls (sh_platform/v1/b9_routes.py).
import { apiGet, apiSend } from "../../api/client";

export interface Figure { figure: string; source: string | null; run: string | null; traced_to: string; check: "Match" | "Differs" | "Not compared"; trail: { kind: string; id: string } | null }
export interface Verified { by: string; at: string; matched: number; total: number; run_id: string | null }
export interface CompareRow { component: string; label?: string; return_pct: string | null; signed_weight_pct: string; used_weight_pct: string; gap_pts: string; differs: boolean }
export interface Comparison {
  month: string; table: string; benchmark_name: string | null; signed_version: number | null; rows: CompareRow[];
  portfolio_pct: string | null; benchmark_run_pct: string | null; benchmark_signed_pct: string | null;
  difference_run_pts: string | null; difference_signed_pts: string | null; same: boolean; problems: string[]; lumen_note?: string;
}
export interface Review {
  state: "requested" | "flagged" | "accepted"; owner: string; requested_by: string; requested_at: string; portfolio: string; code: string; month: string; message: string;
  issues: { by: string; at: string; text: string }[]; case_id: string | null; first: Comparison | null; fix?: { rule_version_id: string; run_status: string; by: string; at: string };
  accepted_by: string | null; accepted_at: string | null;
}
export interface VerifyView {
  project_id: string; figures: Figure[]; matched: number; total: number; verified: Verified | null; stale?: boolean; review: Review | null; owner: string | null;
  comparison: Comparison | null; comparison_error: string | null; suggest?: { portfolio: string; code: string; month: string; message: string } | null;
  can: { verify: boolean; send: boolean; flag: boolean; accept: boolean; fix: boolean };
}

const p = (pid: string) => `/api/v1/build/p/${encodeURIComponent(pid)}/verify`;
export const getVerify = (pid: string) => apiGet<VerifyView>(p(pid));
export const markVerified = (pid: string) => apiSend<VerifyView>("POST", `${p(pid)}/mark`, {});
export const sendForReview = (pid: string, b: { portfolio: string; code: string; month: string; message: string }) => apiSend<VerifyView>("POST", `${p(pid)}/send`, b);
export const flagIssue = (pid: string, text: string) => apiSend<VerifyView>("POST", `${p(pid)}/flag`, { text });
export const fixAndRun = (pid: string) => apiSend<VerifyView>("POST", `${p(pid)}/fix`, {});
export const acceptNumbers = (pid: string) => apiSend<VerifyView>("POST", `${p(pid)}/accept`, {});
