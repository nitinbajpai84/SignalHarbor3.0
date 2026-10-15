// K3 (v4 card K1): the Map centre's four read-only views (sh_platform/v1/k3_routes.py), through the shared client.
import { apiGet, apiSend } from "../../api/client";
import type { Chat } from "../i6/api";

export type Stage = "source" | "file" | "bronze" | "silver" | "gold" | "dashboard" | "person";
export interface FlowNode {
  id: string; stage: Stage; label: string; owner: string | null; last_load: string | null; note: string; project_id: string | null;
  table: string | null; feeds: string[]; fed_by: string[]; state?: string;
}
export interface Flow { stages: { id: Stage; label: string }[]; nodes: FlowNode[]; edges: { from: string; to: string }[] }

export interface ProcessMap { iid: string; project_id: string | null; title: string; owner: string | null; signed_on: string | null; locked: boolean; process: Chat["process_map"] }

export interface Variant {
  id: string; iid: string; code: string; name: string; team: string | null; project: string; project_id: string | null;
  owner: string | null; definition: string; formula: string; unit: string; period: string; version: number | null; signed_on: string | null; hidden?: boolean;
}
export interface Concept { id: string; name: string; synonyms: string[]; variants: Variant[]; difference: string | null }

export interface SourceHealth {
  code: string; name: string; owner: string | null; cadence: string | null; last_received: string | null; never_received: boolean;
  days_late: number | null; is_late: boolean; rejected: number; stale: number | null; unverified: number | null; open_breaks: number | null;
}
export interface Health { allowed: boolean; sources: SourceHealth[]; totals: { late?: number; rejected?: number; open_breaks?: number | null } }

export const getFlow = () => apiGet<Flow>("/api/v1/centre-map/flow");
export const getProcesses = () => apiGet<{ processes: ProcessMap[] }>("/api/v1/centre-map/processes");
export const getDefinitions = () => apiGet<{ concepts: Concept[] }>("/api/v1/centre-map/definitions");
export const getHealth = () => apiGet<Health>("/api/v1/centre-map/health");

// MEM2a: the Conversations tab, the context map (sh_platform/v1/mem_graph_routes.py), already filtered by who the viewer is.
export interface TalkSummary {
  id: string; text: string; agent_name: string; who: string | null; at: string; decisions: string[]; open: string[]; prefs: string[]; topics: string[];
  source: { agent: string; turns: number; from: string; to: string }; superseded: boolean;
}
export interface TalkNode { id: string; type: string; label: string; summary?: TalkSummary }
export interface TalkMap { built_at: string | null; nodes: TalkNode[]; edges: { from: string; to: string; type: string }[] }
export const getTalkMap = () => apiGet<TalkMap>("/api/v1/memory/graph");
export const forgetSummary = (id: string) => apiSend<{ forgotten: string }>("DELETE", `/api/v1/memory/summaries/${encodeURIComponent(id)}`);

// V5 (V5W-6): the company map as one ontology (sh_platform/v1/k3_onto.py).
export type OntoType = "person" | "agent" | "project" | "intent" | "source" | "table" | "definition" | "dashboard" | "report" | "case" | "decision";
export type Relation = "owns" | "feeds" | "defined by" | "decided in" | "raised from" | "built by";
export interface OntoNode {
  id: string; type: OntoType; layer: "bronze" | "silver" | "gold" | null; label: string; sub: string; owner: string | null; project_id: string | null;
  at: string | null; health: "ok" | "attention" | "affected" | null; health_note: string | null; steps: Record<string, number>;
  state: "verified" | "in_progress"; waiting: boolean; sent_back: { by: string; at: string; reason: string } | null; verified_by: string | null; verified_at: string | null;
  col: number; band: boolean; type_word: string;
}
export interface OntoEdge { from: string; to: string; rel: Relation; state: "verified" | "in_progress" }
export interface OntoStep { n: number; name: string; label: string; at: string | null; reached: boolean; added: number }
export interface OntoProject { id: string; title: string; stage: string; stage_word: string; complete: boolean; completed_at: string | null; owner: string | null; built_by: string | null; steps: OntoStep[] }
export interface Lens { id: string; label: string; types: OntoType[]; rels: Relation[] }
export interface Ontology {
  nodes: OntoNode[]; edges: OntoEdge[]; lenses: Lens[]; columns: string[]; relations: Relation[]; counts: Record<OntoType, number>; projects: OntoProject[];
  states: { verified: number; in_progress: number }; waiting: number; can_review: boolean; team: boolean;
}
export interface ReviewItem {
  id: string; type: OntoType; kind: string; label: string; sub: string; owner: string | null; at: string | null; status: "waiting" | "approved" | "sent_back";
  by: string | null; decided_at: string | null; reason: string | null;
}
export interface ReviewProject { id: string; title: string; owner: string | null; built_by: string | null; completed_at: string | null; mine: boolean; items: ReviewItem[]; counts: Record<ReviewItem["status"], number> }
export interface Review { allowed: boolean; can_review: boolean; projects: ReviewProject[]; totals: Partial<Record<ReviewItem["status"], number>> }

export const getOntology = () => apiGet<Ontology>("/api/v1/centre-map/ontology");
export const getReview = () => apiGet<Review>("/api/v1/centre-map/review");
export const approveItems = (ids: string[]) => apiSend<{ approved: string[] }>("POST", "/api/v1/centre-map/review/approve", { ids });
export const rejectItem = (id: string, reason: string) => apiSend<{ sent_back: string }>("POST", "/api/v1/centre-map/review/reject", { id, reason });

// Operations (the old Health tab): the live pipelines and their last run, from the run log (sh_platform/v1/run_log.py, GET /api/v1/ops/pipelines).
export interface PipelineRow { source: string; title: string; owner: string | null; next_run?: string | null; last_run: { started: string; seconds?: number | null; status: "ok" | "late" | "failed"; rules: { passed: boolean }[] } | null }
export const getPipelines = () => apiGet<{ pipelines: PipelineRow[] }>("/api/v1/ops/pipelines");

// DM1: the Map's Data model view (sh_platform/v1/k3_model.py). Row counts only, never rows.
export type ModelLayer = "bronze" | "silver" | "gold";
export interface ModelColumn { name: string; type: string; meaning: string; required: boolean }
export interface ModelFeed { kind: "table" | "dashboard" | "report"; label: string; project: string; id?: string }
export interface ModelTable {
  id: string; real: string; layer: ModelLayer; group: string; group_label: string; added: boolean; rows: number | null; loaded: boolean; meaning: string;
  source: string; cadence: string; owner: string; project: string; columns: ModelColumn[]; reads: string[]; feeds: ModelFeed[];
}
export interface LineageNode { id: string; kind: "source" | ModelLayer | "dashboard" | "report" | "project"; label: string; used_by: number }
export interface DataModel {
  lineage: { nodes: LineageNode[]; edges: { from: string; to: string; rows?: number }[] };
  version: number; additions: number; intro: string; team: boolean;
  layers: Record<ModelLayer, { label: string; title: string; meaning: string }>;
  tables: ModelTable[]; counts: { loaded: number; whole: number };
}
export const getModel = () => apiGet<DataModel>("/api/v1/centre-map/model");

// RUN1: the run log (sh_platform/v1/r1_runs_routes.py). Data team only.
export interface RunRow { run_id: string; kind: string; mode: "test" | "production"; trigger: string; who: string; started?: string; seconds: number | null; status: string }
export interface RunStep { name: string; layer: string | null; target: string | null; rows_in: number | null; inserted: number | null; rejected: number | null; checks_passed: number; checks_failed: number; error: string | null }
export const getRuns = () => apiGet<{ runs: RunRow[] }>("/api/v1/ops/runs");
export const getRun = (id: string) => apiGet<RunRow & { steps: RunStep[] }>(`/api/v1/ops/runs/${encodeURIComponent(id)}`);
