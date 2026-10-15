// Typed calls for module 3. Everything goes through the shared client; nothing here calls fetch.
// One block per package area (M3-P01 to M3-P04); each package adds its own block below its heading.
import { apiGet, apiSend } from "../../api/client";

export const BASE = "/api/modules/m3_connect";

export interface ConnectStatus {
  module: string;
  baselines: number;
  assessments: number;
}
export const getStatus = () => apiGet<ConnectStatus>(`${BASE}/status`);

export interface Assessment {
  id: string;
  baseline_outcome_id: string;
  charter_outcome_id: string | null;
  state: "draft" | "signed";
  created_by: string;
  created_at: string;
  baseline_label?: string;
}
export type StepState = "not_started" | "in_progress" | "done";
export interface Step {
  id: "map" | "request" | "scan" | "trial" | "findings" | "plan";
  label: string;
  state: StepState;
  waiting_on: string;
}
/** A measure the viewer may not see is only its id, the words "A restricted measure" and the flag. */
export interface Measure {
  id: string;
  name: string;
  restricted: boolean;
  priority?: string | null;
  definition?: string | null;
}
export interface AssessmentInputs {
  measures: Measure[];
  sources: Record<string, unknown>[];
  pain_points: { id: string; title: string; measures: string[] }[];
  future_signals: { id: string; title: string; measures: string[] }[];
  levers: { id: string; title: string; measures: string[] }[];
}
export interface AssessmentDetail {
  assessment: Assessment;
  steps: Step[];
  inputs: AssessmentInputs | null;
}

export const listAssessments = () =>
  apiGet<{ assessments: Assessment[]; signed_baseline: boolean; can_start?: boolean; baseline_label?: string }>(`${BASE}/assessments`);
export const startAssessment = () => apiSend<{ assessment: Assessment }>("POST", `${BASE}/assessments`);
export const getAssessment = (id: string) => apiGet<AssessmentDetail>(`${BASE}/assessments/${id}`);

// ---- M3-P01 source map
export type ZoneId = "p1" | "p2" | "identify" | "unknown";
export type SourceKind = "spreadsheet" | "email" | "outside feed" | "system" | "hidden";
export interface Override {
  impact: number | null;
  readiness: number | null;
  reason: string;
  by: string;
  at: string;
}
export interface MapSource {
  id: string;
  name: string;
  restricted: boolean;
  kind: SourceKind;
  measures_fed: number;
  impact: number;
  readiness: number;
  zone: ZoneId;
  zone_label: string;
  marks: { restricted?: boolean; blocked_upstream?: boolean; effort?: "small" | "medium" | "large"; licence?: boolean; owners_disagree?: boolean };
  summary: string;
  draft?: { impact: number; readiness: number };
  override: Override | null;
}
export interface SourceMapData {
  scored_at: string;
  zones: Record<ZoneId, string>;
  sources: MapSource[];
}
export interface Reason {
  text: string;
  effect: "raises" | "lowers";
}
export interface SourcePanelData {
  source: MapSource;
  tables: { name: string; kind: string; fields: { name: string; meaning: string; type: string }[] }[];
  measures: { id: string; name: string; priority: string | null; owners: Record<string, string | null> }[];
  missing: string[];
  impact_reasons: Reason[];
  readiness_reasons: Reason[];
}
export const getSourceMap = (id: string) => apiGet<SourceMapData>(`${BASE}/assessments/${id}/sources`);
export const rescoreSources = (id: string) => apiSend<SourceMapData>("POST", `${BASE}/assessments/${id}/sources/score`);
export const getSource = (id: string, sourceId: string) => apiGet<SourcePanelData>(`${BASE}/assessments/${id}/sources/${sourceId}`);
export const moveSource = (id: string, sourceId: string, body: { impact?: number; readiness?: number; reason: string }) =>
  apiSend<{ source: MapSource }>("PUT", `${BASE}/assessments/${id}/sources/${sourceId}/override`, body);
