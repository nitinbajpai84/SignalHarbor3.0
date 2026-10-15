// E3a: the rules register (sh_platform/v1/e3a_routes.py).
import { apiGet, apiSend } from "../../api/client";

export interface RuleVersion {
  rule_version_id: string; rule_code: string; rule_type: string; owner: string; version_number: number; definition_text: string;
  parameters: Record<string, unknown>; effective_from: string; effective_to: string | null; state: "draft" | "approved" | "retired";
  approved_by: string | null; approved_at: string | null;
}
export interface RuleLine extends RuleVersion { in_force: boolean; waiting: number }
export interface NewVersion { definition_text: string; parameters: Record<string, unknown>; effective_from: string; rule_type?: string }

export const listRules = () => apiGet<RuleLine[]>("/api/v1/rules");
export const ruleHistory = (code: string) => apiGet<RuleVersion[]>(`/api/v1/rules/${encodeURIComponent(code)}/history`);
export const proposeRule = (code: string, body: NewVersion) => apiSend<RuleVersion>("POST", `/api/v1/rules/${encodeURIComponent(code)}`, body);
export interface ImportResult { version: string | null; effective_from: string; unchanged: string[]; waiting: string[]; case_id: string | null;
  proposed: { rule_code: string; before: { min_pct: number; max_pct: number } | null; after: { min_pct: number; max_pct: number }; rule_version_id: string }[] }
/** UC5: a signed limits workbook already uploaded to intake, read as proposed versions for the signer. */
export const importSigned = (fileId: string, sheet = "") => apiSend<ImportResult>("POST", "/api/v1/rules/import", sheet ? { file_id: fileId, sheet } : { file_id: fileId });
export const approveRule = (versionId: string) => apiSend<RuleVersion>("POST", `/api/v1/rules/versions/${encodeURIComponent(versionId)}/approve`, {});
