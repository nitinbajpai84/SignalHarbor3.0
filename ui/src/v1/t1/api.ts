// T1: templates, the intent's template, requests and the company admin's agent context (sh_platform/v1/t1_routes.py).
import { apiGet, apiSend } from "../../api/client";

export interface Field {
  key: string; label: string; help: string; required: boolean;
  type: "text" | "long_text" | "list" | "table" | "number" | "date" | "person" | "choice"; choices?: string[]; columns?: string[];
  ask?: string; default?: string; learn?: string; parse?: string;
}
/** T1b: one section of a template, a document skeleton: heading, grey instruction, example, and how it is shown. */
export interface Section {
  key: string; heading: string; instruction: string; example: string; required: boolean; type: Field["type"];
  columns?: string[]; labels?: Record<string, string>; view?: "swimlane" | "steps" | "table" | "cards";
}
export type OutlineItem = Pick<Section, "key" | "heading" | "required" | "type"> & { columns?: string[] | null; view?: string | null };
export interface TemplateSummary {
  id: string; kind: string; kind_name: string; name: string; description: string; version: number; state: "draft" | "adopted" | "retired";
  standard: boolean; required: string[]; good_to_have: string[]; examples: { id: string; name: string }[];
  unadopted_changes: boolean; adopted_by: string | null; adopted_at: string | null;
  /** The headings of its sections (for the thumbnail) and the process map and definitions templates it comes with. */
  outline?: OutlineItem[]; companions?: Record<string, { id: string; name: string }>;
}
export interface Template extends Omit<TemplateSummary, "required" | "good_to_have" | "examples"> {
  fields: Field[]; sections?: Section[]; free_text: { label: string; required: boolean }; examples: string[]; summary?: TemplateSummary;
}
/** T1b: a document laid out from its template, with what the statement of work already holds in each section (I6's chat view carries it). */
export interface LayoutSection extends Omit<Section, "columns" | "labels" | "view" | "type"> {
  type: Field["type"]; columns?: string[] | null; labels?: Record<string, string> | null; view?: Section["view"] | null;
  filled: boolean; from: string[];
  value: string | string[] | { columns: string[]; rows: Record<string, unknown>[] };
  edits: { label: string; section: string; field: string; value: string; index?: number }[];
}
export interface LayoutDoc {
  kind: string; title: string; template: { id: string; name: string; version: number }; choices: { id: string; name: string }[];
  sections: LayoutSection[]; map?: { steps: unknown[]; handovers: unknown[] };
}
export interface Layout { documents: LayoutDoc[] }
export interface Example { id: string; name: string; template_id: string; values: Record<string, string | string[]> }
export interface Req { id: string; kind: "template" | "skill"; about: string; text: string; by: string; at: string; state: "open" | "done" | "declined"; note: string }
export interface SkillFile { name: string; source: "company" | "repo"; text: string }
export interface AgentSkill { agent: string; label: string; files: SkillFile[] }
export interface Governance { version: number; rules: { rule: string; owner: string }[]; by: string | null; at: string | null }
export interface LogRow { at: string; by: string; what: string; ref: string; note: string }

export const KIND_NAMES: Record<string, string> = {
  intent_of_work: "Intent of work", process_map: "Process map", definitions: "Business definitions", benchmarks: "Benchmark sheet",
  system_design: "System design", data_model: "Data model", build_pack: "Build pack", run_book: "Run book", consumption_brief: "Consumption brief",
};

const t = (id: string) => `/api/v1/templates/${encodeURIComponent(id)}`;
export const listTemplates = (kind = "", all = false) =>
  apiGet<TemplateSummary[]>(`/api/v1/templates?kind=${encodeURIComponent(kind)}${all ? "&all=1" : ""}`);
export const getTemplate = (id: string) => apiGet<Template>(t(id));
export const getExample = (id: string) => apiGet<Example>(`/api/v1/templates/examples/${encodeURIComponent(id)}`);
export const createTemplate = (body: { from_id?: string; kind?: string; name: string; description?: string }) => apiSend<Template>("POST", "/api/v1/templates", body);
export const saveTemplate = (id: string, body: Partial<Pick<Template, "name" | "description" | "fields">>) => apiSend<Template>("PUT", t(id), body);
export const adoptTemplate = (id: string, standard = false) => apiSend<Template>("POST", `${t(id)}/adopt`, { standard });
export const retireTemplate = (id: string) => apiSend<Template>("POST", `${t(id)}/retire`, {});
export const chooseTemplate = (iid: string, template_id: string) =>
  apiSend<{ id: string; version: number }>("PUT", `/api/v1/intents/${encodeURIComponent(iid)}/template`, { template_id });
export const raiseRequest = (body: { kind?: "template" | "skill"; about?: string; text: string }) => apiSend<Req>("POST", "/api/v1/template-requests", body);
export const listRequests = () => apiGet<Req[]>("/api/v1/admin/requests");
export const answerRequest = (id: string, state: Req["state"], note = "") => apiSend<Req>("POST", `/api/v1/admin/requests/${encodeURIComponent(id)}`, { state, note });
export const listSkills = () => apiGet<AgentSkill[]>("/api/v1/admin/skills");
const sk = (a: string, n: string) => `/api/v1/admin/skills/${encodeURIComponent(a)}/${encodeURIComponent(n)}`;
export const saveSkill = (agent: string, name: string, text: string) => apiSend<unknown>("PUT", sk(agent, name), { text });
export const resetSkill = (agent: string, name: string) => apiSend<unknown>("DELETE", sk(agent, name));
export const getGovernance = () => apiGet<Governance>("/api/v1/admin/governance");
export const saveGovernance = (rules: Governance["rules"]) => apiSend<Governance>("PUT", "/api/v1/admin/governance", { rules });
export const getLog = () => apiGet<LogRow[]>("/api/v1/admin/log");
export const switchTemplate = (iid: string, kind: string, template_id: string) =>
  apiSend<{ id: string; version: number }>("PUT", `/api/v1/intents/${encodeURIComponent(iid)}/template/${encodeURIComponent(kind)}`, { template_id });
