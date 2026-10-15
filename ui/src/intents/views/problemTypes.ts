// The Problem's screen record: what GET /api/intents/<id>/problem answers (sh_platform/intents/problem.py, view_of).
export interface Row { id: string; title: string | null; type: string; state: string; why: string; owner: string | null; organiser: string | null; can_open: boolean; closed_at: string | null; root_cause?: string | null; fix?: string | null }
export interface Clock { starts: string; ends: string; working_days_total: number; working_days_left: number; day_of: number; state: string; words?: string }
export interface TriageNote {
  drafted_at: string | null; drafted_plainly: boolean; summary?: string | null; similar: Row[]; related: Row[]; terms: string[]; ops_unreadable: boolean; can_redraw: boolean;
  alerts: { id: string; kind: string; state: string; opened: string | null; by: string | null; note: string | null; source: string | null }[];
  range_breaks: { mart: string; basis: string | null; latest: number | null; hidden: boolean }[];
}
export interface Cause { text: string | null; drafted_by_north: boolean; confirmed_by: string | null; confirmed_at: string | null; based_on: string[]; unknown: boolean; reason: string | null; questions?: string[]; fallback?: boolean }
export interface Fix { kind: string; what: string | null; by: string | null; done_at: string | null; real_fix_by: string | null; accepted_by: string | null; reason: string | null }
export interface Sentence { text: string; pinned: boolean; source_ref: { kind: string; id: string; label: string } }
export interface Note { id: string; by: string | null; role: string; at: string; text: string; anonymous: boolean }
export interface AffectedRow { name: string; mine: boolean; state: string; at: string | null; comment: string | null }
export interface Closing { waiting: string | null; summary: string | null; why: string | null; came_out: string | null; reopened_once: boolean; can_reopen: boolean; can_confirm_owner: boolean; can_confirm_reporter: boolean; can_finish: boolean }
export interface ProblemRecord {
  version: number;
  id: string; state: string; short_ref: string | null; title: string; purpose: string; stage: string | null; stage_key: string | null; triage: string | null; tz: string; clock: Clock | null;
  created_at: string; closed_at?: string | null; reporter: string | null; owner: string | null; organiser: string | null; tier: "content" | "outcome" | "card"; reads?: boolean; people_count: number; waiting_for: string | null;
  affected_may_read: boolean; areas: string[]; extended: { on: string; reason: string } | null; links: { from?: string };
  me: { reporter: boolean; owner: boolean; proposed: boolean; organiser: boolean; admin: boolean; affected: boolean };
  as_reported?: { what: string; saw: string; bites: { kind: string; count: number | null; amount: number | null; unit: string | null }; about: { kind: string; id: string | null; name: string | null }; areas: string[]; affected: string[]; reported_at: string };
  passes?: { from: string; to: string; reason: string; at: string }[]; escalated?: boolean;
  triage_note?: TriageNote; proposed_owner?: { name: string; source: string; label: string; picked_by_reporter: boolean } | null;
  can: { accept: boolean; pass: boolean; assign: boolean; redraw: boolean; extend: boolean; change_owner: boolean };
  alert_line?: { id: string };
  affected?: AffectedRow[]; root_cause?: Cause | null; fix?: (Fix & { by: string | null; accepted_by: string | null }) | null; tally?: { fixed: number; still: number; affected: number; no_answer: number };
  fix_line?: string; what_we_know?: { text: string; sentences: Sentence[]; drafted_at: string } | null; notes?: Note[]; node?: { id: string; name: string | null; found: boolean } | null; north_banner?: string | null;
  can_resolve?: { draft_cause: boolean; confirm_cause: boolean; cause_unknown: boolean; save_fix: boolean; note: boolean; tap: boolean; close: boolean };
  close_checks?: { key: string; ok: boolean; line: string }[] | null; closing?: Closing;
  closed_summary?: string | null; became?: { id: string; title: string; state: string; may_open: boolean };
}
export interface Person { id: string; name: string; team: string | null; can_own?: boolean }
