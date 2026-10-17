// 3.0 typed client: every /api/v3 route in docs/v3/HARBOR-SPEC.md, over the one fetch in ../api/client.ts.
import { apiGet, apiSend } from "../api/client";

export type Stage = "drafting" | "decision1" | "working" | "decision2" | "decision3" | "live" | "question" | "discarded";
export type Answer = "confirm" | "carry_on" | "go_live" | "not_yet";

export interface ThreadSummary { id: string; title: string; stage: Stage; needs: number; next_run?: string }
export interface Event { at: string; kind: "person" | "harbor" | "chips" | "decision_done" | "question"; text?: string; chips?: string[]; by?: string }
export interface BriefLine { section: string; index: number | null; field: string; label: string; value: string; suggested: boolean; changed?: boolean }
export interface BriefGroup { title: string; lines: BriefLine[] }
export interface Brief { question: string; files: string[]; read_by: string; refresh: string; cases_when: string; doc?: BriefGroup[]; title?: string }
export interface DecisionFile { name: string; read_as: string; goes_to: string; state: string; confidence: "high" | "medium" | "low" }
export interface Question { id: string; text: string; options: string[]; assumed?: string }
export interface Check { label: string; value: string; ok: boolean; note: string }
export interface Decision {
  n: 1 | 2 | 3; title: string; brief?: Brief; files?: DecisionFile[]; questions?: Question[]; checks?: Check[]; summary?: string; gaps?: string[];
  sop?: { title: string; download: { docx: string; md: string } };
  assumptions?: Assumption[];
}
export interface Assumption { figure: string; text: string; source: string }
export interface ThreadFigure { figure_id: string; name: string; v: number; status: "verified" | "held" | "draft"; hold: { v: number; reason: string } | null }
export interface Signer { id: string; name: string; email?: string }
export interface SignOff {
  state: "can_sign" | "send" | "fill" | "waiting" | "awaiting_you" | "none"; signers: Signer[]; signer?: Signer | null; raised_by?: string | null;
  sent_at?: string; sent_by?: string; mine?: boolean; message?: string; gaps?: string[];
}
export interface ThreadRecord { started_by?: string | null; started_at?: string; sent_at?: string | null; line?: string | null; signed_by?: string; role?: string; signed_at?: string; version?: number; document?: string }
export interface Thread extends ThreadSummary { signoff?: SignOff | null; events: Event[]; decision: Decision | null; asked: number; harbor_steps: number; record?: ThreadRecord | null; started_by?: string | null; now?: { skill: string; name: string; text: string } | null; brief?: Brief | null; reuse?: ReuseOffer[]; figures?: ThreadFigure[]; process?: { title: string; steps: number; download: { docx: string; md: string } } | null }
export interface CardAction { label: string; answer: string }
export interface Card { kind: "decision" | "exception" | "question"; thread: string; title: string; text: string; actions: CardAction[] }
export interface Figure { label: string; value: string; change: string; id?: string; name?: string; v?: number }
export interface Note { text: string; figures: Figure[] }
export interface FilesLine { arrived: number; recognised: number; waiting: number }
export interface Desk { needs: Card[]; note: Note | null; threads: ThreadSummary[]; files: FilesLine }
export interface FileRow { name: string; arrived_at: string; status: "recognised" | "loaded" | "waiting" | "question"; source: string; thread: string }
export interface Step { n: number; at: string; agent: string; action: string; ok: boolean; run_id?: string; detail: string }
export interface WorkTable { layer: string; name: string; rows: number; state: "reused" | "new" }
export interface Workbench { steps: Step[]; tables: WorkTable[]; rules: string[] }

const t = (id: string) => `/api/v3/threads/${encodeURIComponent(id)}`;

export const getDesk = () => apiGet<Desk>("/api/v3/desk");
export const listThreads = () => apiGet<{ threads: ThreadSummary[] }>("/api/v3/threads");
export const getThread = (id: string) => apiGet<Thread>(t(id));
export const startThread = (text: string) => apiSend<Thread>("POST", "/api/v3/threads", { text });
export const say = (id: string, text: string) => apiSend<Thread>("POST", `${t(id)}/say`, { text });
export const editBrief = (id: string, line: BriefLine, value: string) =>
  apiSend<Thread>("POST", `${t(id)}/brief`, { section: line.section, index: line.index, field: line.field, value });
export const discardThread = (id: string, reason: string) => apiSend<Thread>("POST", `${t(id)}/discard`, { reason });
export const sendForSignature = (id: string, to?: string) => apiSend<Thread>("POST", `${t(id)}/decide`, to ? { n: 1, answer: "send_for_signature", to } : { n: 1, answer: "send_for_signature" });
export const decide = (id: string, n: 1 | 2 | 3, answer: string, answers?: Record<string, string>, reuse?: Record<string, string | null>) =>
  apiSend<Thread>("POST", `${t(id)}/decide`, { n, answer, ...(answers ? { answers } : {}), ...(reuse ? { reuse } : {}) });
export const listFiles = () => apiGet<{ files: FileRow[] }>("/api/v3/files");
/** JSON form of the upload; the multipart form is posted by the Files page. */
export const sendFile = (name: string, data: string) => apiSend<{ files: FileRow[] }>("POST", "/api/v3/files", { name, data });
export const getWorkbench = (id: string) => apiGet<Workbench>(`${t(id)}/workbench`);

// Day one, the industry model, connections, trust (14 Oct addendum).
export interface ModelProperty { name: string; label: string; column?: string; derived?: string }
export interface ModelObject {
  name: string; label: string; table: string; from: "industry" | "office" | "proposed"; count: number;
  properties: ModelProperty[]; relations: { to: string; label: string }[];
}
export interface ModelProposal { id: string; text: string; object: string; property?: string }
export interface Model {
  pack: { id: string; label: string; version: string | number };
  objects: ModelObject[]; coverage: { pct: number; unmapped: string[] };
  proposals: ModelProposal[]; versions: { v: string | number; at: string; by: string; change: string }[];
}
export interface Pack { id: string; label: string; objects: number; questions: number }
export interface Word { word: string; means: string; by: string; used: number }
export interface Language {
  words: Word[]; corrections: { id: string; text: string }[]; golden: { q: string; a: string; by: string }[];
  taught: { name: string; books: number; on: boolean; version: string | number }[];
}
export type Level = "assist" | "auto" | "silent";
export interface People {
  people: { name: string; role: "decides" | "does" | "reads" }[]; second_signer: boolean;
  autonomy: { thread: string; level: Level }[];
  ask_rules: { id: string; text: string; on: boolean; value?: string | number }[];
  usage: { questions: number; builds: number; mode: "testing" | "real" };
}
export interface Run {
  run_id: string; thread: string; kind: "copy" | "live"; started: string; files: number;
  checks_passed: number; checks_total: number; result: string; signed_by: string;
}
export interface Connection {
  id: string; kind: "folder" | "mailbox" | "sftp" | "http" | "database" | "api"; name: string; target: string;
  schedule: string; last_pull: string; state: "ok" | "failing" | "coming";
}
export interface SetupStep { id: string; label: string; done: boolean; detail: string }
export interface Setup { steps: SetupStep[]; pack: { id: string; label: string; intent_examples?: string[] } | null }
export interface Tile { [key: string]: unknown }
export interface Board { title: string; as_at: string; figures: Figure[]; tiles: Tile[] }
export interface TraceStep { kind: string; label: string }
export interface AskAnswer { answer: string; figure?: Figure; understood?: string; trace: TraceStep[]; used: string[] }
export interface NoteFull { text: string; figures: Figure[]; history: { at: string; headline: string }[] }
export interface CaseEvidence { source: string; row: string }
export interface CaseStep { label: string; answer: string }
export interface Case {
  id: string; title: string; status: string; owner: string; due: string; thread: string; what: string;
  evidence: CaseEvidence[]; steps: CaseStep[]; history: { at: string; text: string }[];
}

export const getModel = () => apiGet<Model>("/api/v3/model");
export const decideProposal = (pid: string, answer: "admit" | "reject") =>
  apiSend<Model>("POST", `/api/v3/model/proposals/${encodeURIComponent(pid)}`, { answer });
export const listPacks = () => apiGet<{ packs: Pack[]; current: string }>("/api/v3/packs");
export const getLanguage = () => apiGet<Language>("/api/v3/language");
export const addWord = (word: string, means: string) => apiSend<Language>("POST", "/api/v3/language/words", { word, means });
export const decideCorrection = (id: string, answer: "admit" | "reject") =>
  apiSend<Language>("POST", `/api/v3/language/corrections/${encodeURIComponent(id)}`, { answer });
export const getPeople = () => apiGet<People>("/api/v3/people");
export const setAutonomy = (thread: string, level: Level) => apiSend<People>("POST", "/api/v3/people/autonomy", { thread, level });
export const getRuns = () => apiGet<{ runs: Run[] }>("/api/v3/runs");
export const getConnections = () => apiGet<{ connections: Connection[] }>("/api/v3/connections");
export const getSetup = () => apiGet<Setup>("/api/v3/setup");
export const setSetup = (pack: string) => apiSend<Setup>("POST", "/api/v3/setup", { pack });
export const getBoard = () => apiGet<Board>("/api/v3/board");
export const ask = (text: string) => apiSend<AskAnswer>("POST", "/api/v3/ask", { text });
export const getNote = () => apiGet<NoteFull>("/api/v3/note");
export const getCase = (id: string) => apiGet<Case>(`/api/v3/cases/${encodeURIComponent(id)}`);

// Step 1: figures the office has defined (docs/v3/STEP1-DECISION-SCHEMAS.md).
export type FigureStatus = "verified" | "held" | "draft";
export interface FigureRow { id: string; name: string; current_v: number; status: FigureStatus; built_from: { kind: string; id: string }; used_by_count: number; last_run_at: string | null }
export interface FigureVersion {
  v: number; built_from: { kind: string; id: string }; reads: string[]; sql_hash?: string; model?: string | null; prompt_hash?: string | null;
  assumptions: { text: string; source: string; at: string }[]; tie_out?: { rule: string; ok: boolean; at: string } | null;
  reason?: string | null; approved_by?: string | null; approved_at?: string | null; runs: { run_id: string; at: string; ok: boolean; rows: number }[]; status: FigureStatus;
}
export interface FigureRecord {
  id: string; name: string; definition: string; grain: string[]; versions: FigureVersion[];
  used_by: { thread: string; brief: string; person: string }[];
  current_v?: number;
  lineage: { files: { name: string; rows?: number }[]; tables: { name: string; rows?: number }[]; figure: { name?: string } };
}
export interface ReuseOffer { figure_id: string; name: string; built_from: { kind: string; id: string }; verified_runs: number; first_used_by: string; suggest: boolean }
export const listFigures = () => apiGet<FigureRow[]>("/api/v3/figures");
export const getFigure = (id: string) => apiGet<FigureRecord>(`/api/v3/figures/${encodeURIComponent(id)}`);
export const rollbackFigure = (id: string, v: number) => apiSend<FigureRecord>("POST", `/api/v3/figures/${encodeURIComponent(id)}/rollback`, { v });
