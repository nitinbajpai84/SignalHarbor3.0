// Typed calls for module 2. Everything goes through the shared client; nothing here calls fetch.
// One block per package area (M2-P01 to M2-P05); each package adds its own block below its heading.
import { apiGet, apiSend } from "../../api/client";
import type { TechKpi } from "./technical/technicalApi";

export const BASE = "/api/modules/m2_baseline";

export interface BaselineStatus {
  module: string;
  charters: number;
}
export const getStatus = () => apiGet<BaselineStatus>(`${BASE}/status`);

// ---- shared by every package: a provenance value (modules/m2_baseline/contracts/SHARED.md)
export type Mark = "stated" | "guessed" | "unknown";
export interface Prov<T = string | null> {
  value: T | null;
  mark: Mark;
  by: string;
  at: string;
  from: string;
}

// ---- M2-P01 work list, triage, nominate, governance
export type Role = "business" | "data" | "process";
export const ROLES: Role[] = ["business", "data", "process"];
export type Personal = "yes" | "no" | "not_sure";
export type KpiState = "not_started" | "drafted" | "questions_open" | "signed";
export interface Governance {
  personal: Personal;
  sensitive: boolean;
  may_see: string[];
}
export interface Question {
  id: string;
  question: string;
  answer: Prov;
}
/** What a person not named for a personal or sensitive measure is sent: that it exists, nothing of what is in it. */
export interface KpiHidden {
  id: string;
  name: string;
  restricted: true;
  state: KpiState;
}
export interface KpiFull {
  id: string;
  name: string;
  restricted: false;
  state: KpiState;
  problem_ids: string[];
  priority: string | null;
  definition: Prov;
  owners: Record<Role, Prov>;
  governance: Governance;
  tracking: Prov;
  producer: Prov;
  gathered: Prov;
  questions: Question[];
  definition_proposal: Prov | null;
  triage: { definition: Prov; owner: Prov; producer: Prov; gathered: Prov; unknown: string[] };
  missing_owners: Role[];
  treated_as_personal: boolean;
  /** M2-E1: the pill on the list: "Ready to build", or how many things are still open. */
  build?: { ready: boolean; label: string };
}
export type Kpi = KpiFull | KpiHidden;
export interface Baseline {
  id: string;
  charter_outcome_id: string | null;
  state: string;
  created_at: string;
}
export interface WorkProblem {
  id: string;
  title: string;
  priority: string | null;
  /** problem (to solve now) or pain_point; both get measure suggestions. */
  kind?: "problem" | "pain_point";
  kpi_ids: string[];
  has_kpi: boolean;
}
/** One of the charter's four lists. Future signals and levers are context: shown, given to Lens, never baselined as problems. */
export interface CharterGroup {
  key: "problems" | "pain_points" | "future_signals" | "levers";
  heading: string;
  items: { id: string; title: string; priority: string | null; kind: string }[];
}
export interface Suggestion {
  id: string;
  name: string;
  problem_ids: string[];
  priority: string | null;
  /** Lens's first draft: from the company's documents, else the industry pack's wording. */
  definition?: Prov | null;
}
export interface WorkList {
  baseline: Baseline;
  charter: { outcome_id: string; signed_at: string | null } | null;
  problems: WorkProblem[];
  /** All four lists the signed charter hands on; absent from an older server. */
  charter_groups?: CharterGroup[];
  kpis: Kpi[];
  suggestions: Suggestion[];
  suggestion_label: string;
  pack: { available: boolean; label: string };
  owners_complete: number;
  lens_available: boolean;
  /** Set for the organiser while measures wait for someone to be named to see them. */
  governance_note?: string | null;
  /** Set when Lens's model call was refused or failed: the person is told, the pack's suggestions stand. */
  lens_note?: string;
  /** What happened to each measure Lens just drafted: documents, pack, nothing, unreachable, no_model. */
  outcomes?: Record<string, string>;
  /** After "Tell Lens what to change": redrafted, kept_yours, no_model, unreachable or no_change. */
  outcome?: string;
  /** The company's accounts, to pick an owner from. */
  people?: { account_id: string; display_name: string }[];
}
export interface BaselineRow extends Baseline {
  kpi_count: number;
  /** The charter this baseline came from: its first problem (and how many more), and when it was signed. Null without a charter. */
  charter_title?: string | null;
  charter_signed_at?: string | null;
}
export interface CharterRow {
  outcome_id: string;
  signed_at: string;
  problem_count: number;
  baseline_id: string | null;
  title?: string;
}
export interface BaselineList {
  charters: CharterRow[];
  baselines: BaselineRow[];
}
export interface TriageValue {
  text?: string;
  mark: Mark;
}
/** A person picked from the company's accounts ({account_id}) or a name typed freely ({name, has_account}). */
export type Nominee = { account_id: string } | { name: string; has_account: boolean };

const B = (id: string) => `${BASE}/baselines/${id}`;
export const listBaselines = () => apiGet<BaselineList>(`${BASE}/baselines`);
export const startBaseline = (charterOutcomeId: string | null) =>
  apiSend<WorkList>("POST", `${BASE}/baselines`, { charter_outcome_id: charterOutcomeId });
export const getWorkList = (id: string) => apiGet<WorkList>(B(id));
export const confirmKpi = (id: string, body: { suggestion_id?: string; name?: string; problem_ids?: string[] }) =>
  apiSend<WorkList>("POST", `${B(id)}/kpis`, body);
export const removeKpi = (id: string, kpi: string) => apiSend<WorkList>("DELETE", `${B(id)}/kpis/${kpi}`);
export const putTriage = (id: string, kpi: string, body: Partial<Record<"definition" | "producer" | "gathered", TriageValue>>) =>
  apiSend<WorkList>("PUT", `${B(id)}/kpis/${kpi}/triage`, body);
export const answerQuestion = (id: string, kpi: string, question: string, answer: string) =>
  apiSend<WorkList>("PUT", `${B(id)}/kpis/${kpi}/questions/${question}`, { answer });
export const putOwners = (id: string, kpi: string, body: Partial<Record<Role, Nominee>>) =>
  apiSend<WorkList>("PUT", `${B(id)}/kpis/${kpi}/owners`, body);
export const declineOwner = (id: string, kpi: string, role: Role) =>
  apiSend<WorkList>("POST", `${B(id)}/kpis/${kpi}/owners/${role}/decline`);
export const putGovernance = (id: string, kpi: string, body: Partial<Governance>) =>
  apiSend<WorkList>("PUT", `${B(id)}/kpis/${kpi}/governance`, body);
export const lensDraft = (id: string, kpiIds?: string[], suggestionIds?: string[], retry = false) =>
  apiSend<WorkList>("POST", `${B(id)}/lens/draft`, { kpi_ids: kpiIds, suggestion_ids: suggestionIds, ...(retry ? { retry: true } : {}) });

// ---- M2-AGENTS: Lens's block, its conversation, the pre-read checklist, Nira
export interface RefineItem {
  id: string;
  name: string;
  kind: "measure" | "suggestion";
  definition: Prov | null;
  label: string | null;
  problems: string[];
}
export interface LensAsk {
  id: string;
  kpi_id: string;
  kpi_name: string;
  field: "definition" | "owner" | "producer" | "gathered" | "question";
  role: Role | null;
  question_id: string | null;
  text: string;
  draft: { value: string; from: string } | null;
}
export interface LensState {
  available: boolean;
  locked: boolean;
  pack: { available: boolean; label: string };
  /** Measures and suggestions Lens has not tried to draft yet: the block drafts them one at a time. */
  pending: string[];
  failed: string[];
  /** Being drafted right now (by another tab, say): shown as "Lens is drafting", not as a blank card. */
  drafting: string[];
  documents: number;
  /** Documents waiting for the company admin's decision on personal data (empty for anyone else). */
  waiting?: { doc_id: string; title: string; personal_words: string[]; restrict_path: string }[];
  people: { account_id: string; display_name: string }[];
  refine: RefineItem[];
  asks: LensAsk[];
  say: { did: string; next: string; need: string };
  /** M2-E1: how far Lens is with the technical definitions; `pending` are the measures it has not tried yet. */
  technical?: { drafted: number; measures: number; open: number; pending: string[]; failed: string[]; say: string };
}
export interface AgentReply {
  name: string;
  role: string;
  available: boolean;
  text: string;
  changed?: boolean;
  facts?: string;
}
export interface PreReadKind {
  key: string;
  label: string;
  help: string;
  none: boolean;
  docs: { doc_id: string; title: string }[];
}
export interface PreRead {
  kinds: PreReadKind[];
  /** personal_words and restrict_path are set only for the company admin, for a document that mentions personal data and has no decision yet. */
  documents: { doc_id: string; title: string; restricted: boolean; personal_words?: string[]; restrict_path?: string }[];
  can_upload: boolean;
  pack: { available: boolean; label: string };
}
export type NiraStep = "baselines" | "requests" | "process-map" | "catalogue" | "signoff";
export const getLens = (id: string) => apiGet<LensState>(`${B(id)}/lens`);
export const lensRedraft = (id: string, itemId: string, instruction: string) =>
  apiSend<WorkList>("POST", `${B(id)}/lens/redraft`, { kpi_id: itemId, instruction });
export const askLens = (id: string, question: string) => apiSend<AgentReply>("POST", `${B(id)}/lens/ask`, { question });
export const getPreRead = (id: string) => apiGet<PreRead>(`${B(id)}/preread`);
/** "This document is not personal data": Lens may read it for every measure. "Mark it restricted" is the Company context page's own route (restrict_path). */
export const notPersonal = (id: string, docId: string) => apiSend<PreRead>("POST", `${B(id)}/preread/documents/${docId}/not-personal`);
export const markRestricted = (restrictPath: string) => apiSend<unknown>("POST", restrictPath, { restricted: true });
export const putPreRead =(id: string, kind: string, body: { docs?: string[]; none?: boolean }) => apiSend<PreRead>("PUT", `${B(id)}/preread/${kind}`, body);
export const askNira = (id: string, kind: "welcome" | "now" | "ask", step: NiraStep, question?: string) =>
  apiSend<AgentReply>("POST", `${B(id)}/nira`, { kind, step, question });
/** Something changed on the baseline (a screen or Lens's block did it): every open view of it reloads. */
export const CHANGED = "sh:baseline-changed";
export const notifyChanged = () => window.dispatchEvent(new Event(CHANGED));

// ---- M2-P02 requests, owner questionnaire, sensing, trace
import * as client from "../../api/client";

export type RequestState = "sent" | "opened" | "answered" | "no_reply" | "in_meeting";
export interface KpiRef {
  id: string;
  name: string;
}
export interface RequestRow {
  id: string;
  owner_name: string;
  role: string;
  state: RequestState;
  kpis: KpiRef[];
  sent_at: string;
  opened_at: string | null;
  answered_at: string | null;
  reminders: string[];
  link: "open" | "expired" | "revoked";
  expires_at: string;
  answered_kpis: number;
  meeting: { by: string; at: string } | null;
  days_waiting: number;
  remind_due: boolean;
  organiser_told: boolean;
  next_reminder_on: string | null;
  nira: string | null;
}
export interface Outstanding {
  requests: RequestRow[];
  summary: { asked: number; answered: number; outstanding: number; in_meeting: number };
  waiting_on: { kpi_id: string; kpi_name: string; waiting_on: string[] }[];
  alerts: string[];
  not_yet_asked: string[];
  /** The baseline is signed: read-only. */
  signed?: boolean;
}
export interface EmailText {
  subject: string;
  body: string;
}
export interface SentRequest extends RequestRow {
  /** The page address for the link, shown once. Null for a person who already had a request. */
  link_path: string | null;
  /** The full address, the same one its email text carries. */
  address?: string | null;
  email: EmailText | null;
}

export interface Hop {
  who: string;
  /** The team or system the step belongs to: its lane on the process map. */
  team?: string;
  what?: string;
  step?: string;
  /** The step number, so owners' answers merge into one sequence in time order. Typed as text, sent as a whole number. */
  order?: string | number;
  manual?: boolean;
}
/** One system or file under a measure: each cell is what the person typed or chose (a short list is written with commas). */
export type SourceRow = Record<string, string>;
export interface RowColumn {
  key: string;
  kind: "text" | "choice" | "list";
  label: string;
  choices?: { value: string; label: string }[];
}
export interface FieldSpec {
  key: string;
  kind: "choice" | "text" | "hops" | "rows";
  question: string;
  choices?: { value: string; label: string }[];
  hop?: { key: string; label: string }[];
  row?: RowColumn[];
}
export interface QuestionnaireSpec {
  fields: FieldSpec[];
  marks: { value: Mark; label: string }[];
  limits: { text_chars: number; hops: number; source_rows?: number };
}
/** A saved answer record, flat as the server keeps it: each question key holds a Prov value. */
export type AnswerRecord = Record<string, unknown> & {
  id: string;
  kpi_id: string;
  owner_name: string;
  sample_title: string | null;
  unanswered?: string[];
};
/** What a person types for one question: a value and how sure they are. */
export type AnswerInput = { value: unknown; mark: Mark };
export type AnswerInputs = Record<string, AnswerInput>;

export interface OwnerForm {
  owner_name: string;
  role: string;
  state: RequestState;
  expires_at: string;
  kpis: { id: string; name: string; answers: AnswerRecord | null }[];
  questionnaire: QuestionnaireSpec;
  /** The parts of this person's own measures they may confirm from the link (only when they have no account). */
  confirmable: { kpi_id: string; part: string; label: string; confirmed: boolean }[];
  /** Parts whose owner has an account: confirmed signed in, never from the link (decision N4). */
  sign_in_parts?: { kpi_id: string; part: string; label: string; confirmed: boolean }[];
  /** Where the sign-off screen is, for the sign-in button. */
  sign_in_path?: string;
  /** The baseline is signed: the answers can no longer be changed. */
  signed?: boolean;
  /** M2-E1: open questions put to this owner, worded for them. */
  questions?: OwnerQuestion[];
  /** The technical definitions of the measures this person is the data owner of (no account: they confirm here). */
  technical?: TechKpi[];
  /** The same, when the owner has an account: they sign in to confirm. */
  technical_sign_in?: { kpi_id: string; name: string }[];
}
export interface OwnerQuestion {
  ambiguity_id: string;
  kpi_id: string;
  kpi_name: string;
  text: string;
  /** The owner has an account: the question is read-only here until they sign in as themselves. */
  needs_sign_in?: boolean;
}
export interface FileUpload {
  filename: string;
  /** The file's bytes, base64. */
  data: string;
}

const REQ = (baselineId: string) => `${BASE}/baselines/${encodeURIComponent(baselineId)}`;
export const getOutstanding = (baselineId: string) => client.apiGet<Outstanding>(`${REQ(baselineId)}/requests`);
export const sendRequests = (baselineId: string) => client.apiSend<{ sent: SentRequest[]; new: number }>("POST", `${REQ(baselineId)}/requests`);
export const remindOwner = (baselineId: string, requestId: string) =>
  client.apiSend<{ request: RequestRow; email: EmailText }>("POST", `${REQ(baselineId)}/requests/${requestId}/remind`);
export const withdrawLink = (baselineId: string, requestId: string) =>
  client.apiSend<{ request: RequestRow }>("POST", `${REQ(baselineId)}/requests/${requestId}/revoke`);
export const newLink = (baselineId: string, requestId: string) =>
  client.apiSend<{ request: RequestRow; link_path: string; address?: string; email: EmailText }>("POST", `${REQ(baselineId)}/requests/${requestId}/relink`);
export const reopenRequest = (baselineId: string, requestId: string) =>
  client.apiSend<{ request: RequestRow; link_path: string; address?: string; email: EmailText }>("POST", `${REQ(baselineId)}/requests/${requestId}/reopen`);
export const answerInMeeting = (baselineId: string, requestId: string) =>
  client.apiSend<{ request: RequestRow }>("POST", `${REQ(baselineId)}/requests/${requestId}/meeting`);
export const getAnswers = (baselineId: string) =>
  client.apiGet<{ questionnaire: QuestionnaireSpec; kpis: KpiRef[]; answers: AnswerRecord[] }>(`${REQ(baselineId)}/answers`);
export const saveMeetingAnswers = (baselineId: string, ownerName: string, kpiId: string, answers: AnswerInputs) =>
  client.apiSend<{ saved: AnswerRecord }>("PUT", `${REQ(baselineId)}/meeting-answers`, { owner_name: ownerName, kpi_id: kpiId, answers });
export const uploadMeetingSample = (baselineId: string, ownerName: string, kpiId: string, file: FileUpload) =>
  client.apiSend<{ saved: AnswerRecord }>("POST", `${REQ(baselineId)}/sample`, { owner_name: ownerName, kpi_id: kpiId, ...file });
// The owner has no account: the link's token goes in the X-Session-Token header and nowhere else.
const ANSWER = `${BASE}/answer`;
export const getOwnerForm = (token: string) => client.guestSend<OwnerForm>("POST", `${ANSWER}/form`, undefined, token);
export const saveOwnerAnswers = (token: string, kpiId: string, answers: AnswerInputs) =>
  client.guestSend<{ saved: AnswerRecord }>("POST", `${ANSWER}/save`, { kpi_id: kpiId, answers }, token);
export const confirmOwnerPart = (token: string, kpiId: string, part: string) =>
  client.guestSend<{ confirmable: OwnerForm["confirmable"] }>("POST", `${ANSWER}/confirm`, { kpi_id: kpiId, part }, token);
export const answerOwnerQuestion = (token: string, kpiId: string, ambiguityId: string, resolution: string) =>
  client.guestSend<{ questions: OwnerQuestion[] }>("POST", `${ANSWER}/question`, { kpi_id: kpiId, ambiguity_id: ambiguityId, resolution }, token);
export const confirmOwnerTechnical = (token: string, kpiId: string) =>
  client.guestSend<{ technical: TechKpi[] }>("POST", `${ANSWER}/technical/confirm`, { kpi_id: kpiId }, token);
export const submitOwnerAnswers = (token: string) => client.guestSend<{ state: RequestState }>("POST", `${ANSWER}/submit`, undefined, token);
export const uploadOwnerSample = (token: string, kpiId: string, file: FileUpload) =>
  client.guestSend<{ saved: AnswerRecord }>("POST", `${ANSWER}/sample`, { kpi_id: kpiId, ...file }, token);

// ---- M2-P03 process map

export type TrackingId = "tracked_now" | "partly" | "not_tracked";
export type StepMark = "stated" | "guessed" | "to_confirm";
export interface MapStep {
  id: string;
  lane: string;
  text: string;
  order: number;
  manual: boolean;
  confirmed: boolean;
  from: string;
  state: "proposal" | "validated" | "edited" | "removed";
  by: string;
  owner: string | null;
  mark: StepMark;
  tracking: TrackingId | null;
  /** Set when the person who does this step has not answered: the one to ask to confirm it. */
  ask?: string;
}
export interface KpiMap {
  id: string;
  name: string | null;
  definition: Prov;
  lanes: string[];
  steps: MapStep[];
  removed: number;
  drawn: boolean;
  counts: { answers: number; to_confirm: number; manual: number };
  tracking: { status: Prov; tentative_date: Prov; next_step: Prov };
}
export interface ProcessMap {
  baseline_id: string;
  signed: boolean;
  statuses: { id: TrackingId; label: string }[];
  kpis: KpiMap[];
}
export interface StepInput {
  lane?: string;
  text?: string;
  manual?: boolean;
}
export interface TrackingInput {
  status: TrackingId;
  tentative_date?: string;
  next_step?: string;
  step_id?: string;
}
const MAP = (baseline: string) => `${BASE}/baselines/${encodeURIComponent(baseline)}/process-map`;
export const getProcessMap = (baseline: string) => apiGet<ProcessMap>(MAP(baseline));
export const drawProcessMap = (baseline: string) => apiSend<ProcessMap>("POST", `${MAP(baseline)}/draw`);
export const addStep = (baseline: string, kpi: string, body: StepInput) => apiSend<KpiMap>("POST", `${MAP(baseline)}/${kpi}/steps`, body);
export const validateStep = (baseline: string, kpi: string, step: string) => apiSend<KpiMap>("POST", `${MAP(baseline)}/${kpi}/steps/${step}/validate`);
export const editStep = (baseline: string, kpi: string, step: string, body: StepInput) => apiSend<KpiMap>("PUT", `${MAP(baseline)}/${kpi}/steps/${step}`, body);
export const removeStep = (baseline: string, kpi: string, step: string) => apiSend<KpiMap>("DELETE", `${MAP(baseline)}/${kpi}/steps/${step}`);
export const setTracking = (baseline: string, kpi: string, body: TrackingInput) => apiSend<KpiMap>("PUT", `${MAP(baseline)}/${kpi}/tracking`, body);

// ---- M2-P04 data catalogue

export type CatTab = "sources" | "tables" | "fields" | "extractions" | "kpis";
export const CAT_TABS: readonly CatTab[] = ["sources", "tables", "fields", "extractions", "kpis"];
/** One cell: a value and who said it (stated, guessed or unknown), from where, and when. */
export interface CatCell {
  value: string | number | string[] | null;
  mark: Mark;
  by: string;
  at: string;
  from: string;
}
/** A row is its cells by the template's column names. A row the person is not named for has only its id cell and `_hidden`. */
export type CatRow = Record<string, CatCell | boolean | undefined> & { _hidden?: boolean };
export interface CatColumn {
  header: string;
  guidance: string;
  required: boolean;
  options: string[];
  computed: boolean;
  picks_from: CatTab | null;
}
export interface CatTabSchema {
  sheet: string;
  title: string;
  blurb: string;
  id_header: string;
  status_header: string;
  columns: CatColumn[];
}
export interface ConflictVersion {
  value: string;
  by: string;
  at: string | null;
  from: string | null;
  kpi_id: string | null;
}
export interface Conflict {
  id: string;
  _hidden?: boolean;
  tab?: CatTab;
  row_id?: string;
  column?: string;
  versions?: ConflictVersion[];
  state?: "open" | "settled" | "closed";
  settled_by?: string | null;
  settled_value?: string | null;
  settled_at?: string | null;
  note?: string | null;
}
export type TechColumn = Record<"calculation" | "sources" | "tables" | "fields" | "filters" | "grain" | "period" | "currency_basis" | "notes" | "confirmed", string>;
/** M2-E1: each measure's calculation and inputs in words, and which measures use each field or extraction. */
export type TechColumns = { kpis: Record<string, TechColumn>; inputs: Record<string, string[]> };
export type CatalogueView = { baseline_id: string; schema: Record<CatTab, CatTabSchema>; conflicts: Conflict[]; findings: Record<string, string[]>; hidden_note?: string | null; signed?: boolean; governance?: GovColumns; technical?: TechColumns } & Record<CatTab, CatRow[]>;

const CAT = (id: string) => `${BASE}/baselines/${encodeURIComponent(id)}/catalogue`;
export const getCatalogue = (id: string) => apiGet<CatalogueView>(CAT(id));
export const refreshCatalogue = (id: string) => apiSend<{ status: string }>("POST", `${CAT(id)}/refresh`, {});
export const addCatalogueRow = (id: string, tab: CatTab, cells: Record<string, string>, mark: Mark = "stated") =>
  apiSend<{ id: string }>("POST", `${CAT(id)}/${tab}/rows`, { cells, mark });
export const editCatalogueRow = (id: string, tab: CatTab, rowId: string, cells: Record<string, string>, mark: Mark = "stated") =>
  apiSend<{ status: string }>("PUT", `${CAT(id)}/${tab}/rows/${encodeURIComponent(rowId)}`, { cells, mark });
export const settleConflict = (id: string, conflictId: string, value: string, note: string) =>
  apiSend<{ id: string; state: string; settled_by: string }>("POST", `${CAT(id)}/conflicts/${encodeURIComponent(conflictId)}/settle`, { value, note });
/** A plain link: the browser downloads the workbook with the signed-in session. */
export const catalogueExportUrl = (id: string) => `${CAT(id)}/export`;

export function cellOf(row: CatRow, header: string): CatCell | undefined {
  const v = row[header];
  return typeof v === "object" ? v : undefined;
}
export function cellText(c: CatCell | undefined): string {
  if (!c || c.mark === "unknown" || c.value === null) return "";
  return Array.isArray(c.value) ? c.value.join("; ") : String(c.value);
}

// ---- M2-P05 review, sign-off, readiness, hand-off

export type OwnerStatus = "named" | "no_owner" | "pending";
export type AnswerStatus = "stated" | "unknown" | "conflict" | "pending";
export interface PartView {
  id: string;
  label: string;
  owner_label: string;
  owner_status: OwnerStatus;
  owner_name: string | null;
  named_by_sponsor: boolean;
  confirmed: { by: string; at: string; via?: string } | null;
}
export interface SensingView {
  id: string;
  label: string;
  status: AnswerStatus;
  value: unknown;
  /** The stated choices in a conflict, with who gave each. */
  options: { value: unknown; label?: string; by: string | null }[];
  settled: { value: unknown; label?: string; by: string; at: string } | null;
}
export interface ReviewNotes {
  tentative_date: string | null;
  next_step: string | null;
  project: string | null;
  accepted: { by: string; at: string } | null;
}
export interface KpiReview {
  id: string;
  name: string;
  priority: string | null;
  state: "ready" | "blocked" | "not_ready";
  parts: PartView[];
  source: { status: AnswerStatus; value: unknown };
  sensing: SensingView[];
  waiting_on: string[];
  /** "waiting on Wei Chen": who has not answered yet. */
  waiting_note: string | null;
  tracking: { value: string | null; mark: string | null; label: string | null; today: boolean };
  unknowns: string[];
  missing: string[];
  confirmed_all: boolean;
  /** A measure the sponsor cannot see, confirmed by all its named owners: it needs no sponsor acceptance. */
  covered?: boolean;
  review: ReviewNotes | null;
}
export interface ReadinessItem {
  id: string;
  label: string;
  met: boolean;
  required: boolean;
  missing: string[];
}
export interface ComingRow extends ReviewNotes {
  kpi_id: string;
  name: string;
}
/** M2-E4: the ready-to-build checklist as this person may see it. `ok` is the whole baseline's, the same for everyone. */
export interface GateMeasure {
  kpi_id: string;
  name: string;
  ready: boolean;
  reasons: string[];
  open: number;
}
export interface LeftOut {
  kpi_id: string;
  name: string;
  reason: string;
  by: string;
  at: string;
}
export interface Gate {
  ok: boolean;
  measures: { ready: number; total: number; items: GateMeasure[] };
  glossary: { ok: boolean; reasons: string[] };
  governance: { ok: boolean; reasons: string[] };
  open: { n: number };
  left_out: LeftOut[];
  /** Something this person may not see is still open (no detail). */
  restricted: boolean;
  /** Which step of the bar fixes each line: baselines, glossary, governance or questions. */
  fix: Record<"measures" | "glossary" | "governance" | "open", string>;
  refusal: string;
}
/** One of the two signed documents; once signed, its content fingerprint and whether the content is still the same. */
export interface SignedDocument {
  id: "business_glossary" | "data_catalogue";
  name: string;
  sha256?: string;
  built_at?: string;
  unchanged?: boolean;
}
export interface SignoffView {
  /** Older answers lack these two; the screen then shows no checklist. */
  gate?: Gate;
  documents?: SignedDocument[];
  baseline_id: string;
  version: number;
  versions: number;
  status: "open" | "signed";
  locked: string | null;
  signatures: { slot: string; label: string; name: string; at: string; restricted_covered?: number; note?: string | null }[];
  /** Set when some measures are restricted from this viewer: what that means for their signature. */
  note?: string;
  restricted_count?: number;
  waiting_for: string[];
  signed_at: string | null;
  outcome_id: string | null;
  ready: boolean;
  can_countersign: boolean;
  items: ReadinessItem[];
  kpis: KpiReview[];
  coming: ComingRow[];
  viewer: { name: string; sponsor: boolean; can_settle: boolean; slot: string | null };
}
export interface AuditEntry {
  n: number;
  at: string;
  by: string;
  action: string;
  version: number;
  kpi_id?: string;
  part?: string;
  detail?: string;
}
export interface AuditLog {
  entries: AuditEntry[];
  intact: boolean;
}

const signoffPath = (id: string) => `${BASE}/baselines/${encodeURIComponent(id)}`;
export const getReview = (id: string) => apiGet<SignoffView>(`${signoffPath(id)}/review`);
export interface MyParts {
  status: string;
  parts: { kpi_id: string; kpi_name: string; part: string; label: string; confirmed: boolean }[];
}
export const getMyParts = (id: string) => apiGet<MyParts>(`${signoffPath(id)}/my-parts`);
export const getAudit = (id: string) => apiGet<AuditLog>(`${signoffPath(id)}/audit`);
export const saveReview = (id: string, kpi: string, fields: Partial<Pick<ReviewNotes, "tentative_date" | "next_step" | "project">>) =>
  apiSend<SignoffView>("PUT", `${signoffPath(id)}/review/${encodeURIComponent(kpi)}`, fields);
export const acceptUnknown = (id: string, kpi: string) => apiSend<SignoffView>("POST", `${signoffPath(id)}/review/${encodeURIComponent(kpi)}/accept`);
export const nameOwner = (id: string, kpi: string, part: string, name: string) =>
  apiSend<SignoffView>("POST", `${signoffPath(id)}/review/${encodeURIComponent(kpi)}/owner`, { part, name });
export const confirmPart = (id: string, kpi: string, part: string) => apiSend<SignoffView>("POST", `${signoffPath(id)}/confirm`, { kpi_id: kpi, part });
export const settleChoice = (id: string, kpi: string, field: string, value: string) =>
  apiSend<SignoffView>("POST", `${signoffPath(id)}/signoff/settle`, { kpi_id: kpi, field, value });
export const leaveOut = (id: string, kpi: string, reason: string) =>
  apiSend<SignoffView>("POST", `${signoffPath(id)}/review/${encodeURIComponent(kpi)}/leave-out`, { reason });
export const bringBack = (id: string, kpi: string) => apiSend<SignoffView>("POST", `${signoffPath(id)}/review/${encodeURIComponent(kpi)}/bring-back`);
/** One zip for this person: the glossary, the catalogue and a read-me page (a marked draft until signed). */
export const signedBundleUrl = (id: string) => `${signoffPath(id)}/signoff/bundle`;
export const countersign = (id: string) => apiSend<SignoffView>("POST", `${signoffPath(id)}/countersign`);
export const newVersion = (id: string) => apiSend<SignoffView>("POST", `${signoffPath(id)}/versions`);

// ---- M2-E3 governance view: who may see each measure, source and field, and whether it holds personal data
export interface GovWho {
  mode: "everyone" | "follows" | "named" | "organiser";
  text: string;
  names: string[];
}
export interface GovProposal {
  class: string;
  kind: string | null;
  mark: "guessed";
  reason: string;
  by: string;
}
export interface GovRow {
  kind: "measure" | "source" | "field";
  id: string;
  name: string;
  restricted: boolean;
  hidden?: boolean;
  personal?: string;
  sensitive?: boolean | null;
  visible_to?: GovWho;
  decided?: { by: string; at: string } | null;
  undecided?: string[];
  table?: string;
  source?: string;
  feeds?: { id: string; name: string }[];
  proposal?: GovProposal | null;
  sources?: GovRow[];
  fields?: GovRow[];
}
export interface GovCount {
  total: number;
  decided: number;
  undecided: number;
  restricted: number;
}
export interface GovernanceView {
  baseline_id: string;
  signed: boolean;
  pack_label: string;
  summary: { measures: GovCount; sources: GovCount; fields: GovCount; lines: string[] };
  measures: GovRow[];
  other_sources: GovRow[];
  other_fields: GovRow[];
  can_change: boolean;
  organiser: boolean;
  /** "Some measures are restricted to named people", with no number; null when nothing is left out. */
  note: string | null;
}
const GOV = (id: string) => `${BASE}/baselines/${encodeURIComponent(id)}/governance`;
export const getGovernance = (id: string) => apiGet<GovernanceView>(GOV(id));
export const restrictField = (id: string, fieldId: string, names: string[]) =>
  apiSend<{ status: string }>("PUT", `${GOV(id)}/fields/${encodeURIComponent(fieldId)}`, { may_see: names });
export const confirmProposals = (id: string, body: { field_ids: string[] } | { only_not_personal: true }) =>
  apiSend<{ confirmed: string[]; skipped: number }>("POST", `${GOV(id)}/proposals/confirm`, body);
/** What the catalogue screen shows beside its Fields and KPIs tabs (only rows the person may see). */
export interface GovColumn {
  personal: string;
  sensitive: string;
  who: string;
}
export type GovColumns = { kpis: Record<string, GovColumn>; fields: Record<string, GovColumn> };

// ---- IC-3e: the governed state of each measure (module 2, A-054) and "send back with a note"
export interface GovernedCell {
  value: unknown;
  mark: "stated" | "guessed" | "unknown";
  by?: string;
}
export interface GovernedMeasure {
  id: string;
  name: string | null;
  state: Record<string, GovernedCell>;
  governed: boolean;
  /** Field names (owners, classification, may_see, resolving, affects, review_date) not yet stated. */
  missing: string[];
}
export interface GovernedView {
  measures: GovernedMeasure[];
  percentages: { owned: number; classified: number; may_see_confirmed: number; sealed: number };
}
export const getGoverned = (id: string) => apiGet<GovernedView>(`${BASE}/baselines/${encodeURIComponent(id)}/governed`);
/** The note waits beside the technical definition for its data owner; the definition itself is not edited. */
export const sendBackDefinition = (id: string, measure: string, note: string) =>
  apiSend<{ kpis: TechKpi[] }>("POST", `${BASE}/baselines/${encodeURIComponent(id)}/measures/${encodeURIComponent(measure)}/send-back`, { note });
