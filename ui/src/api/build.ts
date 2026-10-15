// Typed calls for the Build Centre routes (docs/plan/SHAPES.md sections 2-5). Plain wrappers over apiGet/apiSend, which stay the only callers of fetch.
import { apiGet, apiSend } from "./client";

export interface Prov { mark: "guessed" | "stated"; from: string; by?: string; at?: string }
/** A row about a measure this person may not see (sh_platform/build/blueprint.py `_shown`): the row numbers stay the same for everyone. */
export interface Hidden { hidden: true }
export interface Lineage { measure: string; source: string; fields: string[]; transform: string; mart: string }
export interface Rule { measure: string; rule: string; severity: "block" | "warn" | "inform"; from: "scan" | "trial" }
export interface Access { mart: string; may_see: string[] | null }
export interface Blueprint {
  version: number;
  state: "draft" | "signed";
  signed_by: { name: string; role: string; at: string }[];
  band: "now" | "next" | "later";
  model: {
    facts: { name: string; grain: string; keys: string[]; measures: string[] }[];
    dimensions: { name: string; keys: string[]; attributes: string[]; scd: 1 | 2 }[];
  };
  lineage: (Lineage | Hidden)[];
  rules: (Rule | Hidden)[];
  access: (Access | Hidden)[];
  schedule: { source: string; expected: string; sla: string; depends_on: string[] }[];
  infra: { warehouse: string; runner: string };
  provenance: Record<string, Prov>;
  /** "draft baseline" while drafted from an unsigned baseline; such a blueprint cannot be signed. */
  basis?: string;
}
export interface NoBlueprint { state: "none"; message: string }
export interface PipelineContract {
  source: string; lands_at: string; pattern: string; expected: string; sla: string;
  schema: { field: string; type: string }[]; rules: string[]; depends_on: string[]; owner: string; marts: string[];
}
export interface RunRecord {
  id: string; source: string; started: string; ended: string; on_time: boolean; rows: number; schema_ok: boolean;
  rules: { rule: string; passed: boolean; count: number }[];
  marts_ready: string | null; sla_met: boolean | null; owner: string; status: "ok" | "late" | "failed";
}

export const shown = <T extends object>(row: T | Hidden): row is T => !("hidden" in row);

export const getBlueprint = () => apiGet<Blueprint | NoBlueprint>("/api/company/build/blueprint");
/** One field per call, by its dotted path (`model.facts.0.grain`); the route marks it stated by the signed-in person. */
export const putBlueprint = (path: string, value: string) => apiSend<Blueprint>("PUT", "/api/company/build/blueprint", { path, value });
export const signBlueprint = () => apiSend<Blueprint>("POST", "/api/company/build/blueprint/sign");
