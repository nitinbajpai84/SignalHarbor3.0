// K3: shapes of sh_platform/v1/k5_routes.py (fixtures/*.json are real responses of k5_managers).
import { apiGet, apiSend } from "../../api/client";

export type StatementState = "received" | "received_late" | "late" | "not_due" | "not_expected" | "no_rule";
export interface LastValue { amount: string; currency: string; valuation_date: string; recorded_at?: string; status: string; status_word?: string; valuation_id: string }
export interface Revision { from: string; to: string; change: string; currency: string }
export interface StatementRef { id: string; title: string; valuation_date: string; received_at: string; status: string; current: boolean; revision?: Revision | null }
export interface FundRow {
  fund_id: string; fund_name: string; manager: string; currency: string | null; cadence: "monthly" | "quarterly"; period_end: string; due: string | null;
  state: StatementState; state_word: string; received_on: string | null; days_late: number | null; revised_count: number; revisions_total: number;
  last_value: LastValue | null; statements: StatementRef[];
  earlier_missing?: { period_end: string; due: string; days_late: number }[];
}
export interface ManagerRow { manager_id: string; name: string; funds: FundRow[]; counts: { expected: number; received: number; late: number; revised: number; missing_earlier?: number } }
export interface Inbox { as_of: string; due_rule_signed: boolean; rule_note: string | null; managers: ManagerRow[] }
export interface Followup { manager: string; contact?: string | null; draft: string | null; sent: false; subject?: string; body?: string; note?: string; message?: string }

export interface Note { id: string; kind: "note" | "meeting" | "question"; text: string; by: string; on: string; at: string; system: boolean; state: string }
export interface TimelineRow { document_id: string; fund_id: string; fund_name: string; valuation_date: string; received_at: string; status: string; current: boolean; replaces: string | null; title: string;
  days_late?: number; value?: { amount: string; currency: string } | null; revision?: Revision | null }
export interface CommitmentRow { commitment_id: string; fund_id: string; entity: string | null; currency: string; committed_on: string | null; commitment: string; called: string; uncalled: string }
export interface DiligenceDoc { id: string; name: string; kind: string; at: string; uploaded_by: string; access: string; preview: unknown; passage?: string | null }
export interface Profile {
  manager_id: string; name: string; as_of: string; funds: FundRow[]; commitments: { available: boolean; rows: CommitmentRow[]; message: string | null };
  timeline: TimelineRow[]; notes: Note[]; questions: Note[]; documents: DiligenceDoc[]; last_meeting: string | null;
}
export interface ChangeItem { date: string; kind: string; text: string; source: { label: string; link: string | null } }
export interface Passage { file: string; from: number; to: number; text: string; date: string }
export interface Changes { manager_id: string; name: string; since: string | null; items: ChangeItem[]; passages?: Passage[]; answer: string; worded_by: string; note?: string }

const base = (id: string) => `/api/v1/managers/${encodeURIComponent(id)}`;
export const getInbox = (asOf?: string) => apiGet<Inbox>(`/api/v1/managers/inbox${asOf ? `?as_of=${encodeURIComponent(asOf)}` : ""}`);
export const draftFollowup = (id: string, fundId?: string, asOf?: string) =>
  apiSend<Followup>("POST", `${base(id)}/followup`, { ...(fundId ? { fund_id: fundId } : {}), ...(asOf ? { as_of: asOf } : {}) });
export const getProfile = (id: string) => apiGet<Profile>(base(id));
export const getChanges = (id: string, since?: string) => apiGet<Changes>(`${base(id)}/changes${since ? `?since=${encodeURIComponent(since)}` : ""}`);
export const addNote = (id: string, text: string, kind: Note["kind"], on?: string) => apiSend<Note>("POST", `${base(id)}/notes`, { text, kind, ...(on ? { on } : {}) });
export const answerQuestion = (id: string, noteId: string) => apiSend<Note>("POST", `${base(id)}/notes/${encodeURIComponent(noteId)}/answered`);

/** "USD 10,000,000": thousands separators on the whole-number part only. */
export const money = (v: { amount: string; currency: string }) => {
  const [whole = "", frac] = v.amount.split(".");
  return `${v.currency} ${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}${frac ? `.${frac}` : ""}`;
};
export { day } from "../../design";

/** "revised from USD 8,420,000 to USD 8,275,000 (-145,000)": the old and new figures of a replaced statement. */
export const revisedWords = (r: Revision) =>
  `revised from ${money({ amount: r.from, currency: r.currency })} to ${money({ amount: r.to, currency: r.currency })} (${r.change.replace(/^([+-]?)(\d+)/, (_, s: string, w: string) => s + w.replace(/\B(?=(\d{3})+(?!\d))/g, ","))})`;
