// The Prepare form's values and the checks the screen shows live. The server checks again and has the last word.
import { m1 } from "./copy";
import type { Lists, NamesRule, Preparation, Split } from "./api";

export interface Form {
  purpose: string;
  outcome: string;
  charter_template: string;
  seats: number;
  /** A preset's minutes as text, or "custom". */
  lengthChoice: string;
  customLength: string;
  split: { briefing: string; individual: string; together: string };
  practice: boolean;
  library: boolean;
  video: string;
  names: NamesRule;
  approver: string;
  /** Kept as it was when a draft already names an account; this screen only asks for a name. */
  approverAccountId: string | null;
  /** One signature (the default) or two. */
  signers: 1 | 2;
}

export const CUSTOM = "custom";

/** Whole minutes for a length, shared by the contract's percentages; the remainder goes to the last part. */
export function defaultSplit(length: number, percent: Split): Split {
  const briefing = Math.floor((length * percent.briefing) / 100);
  const individual = Math.floor((length * percent.individual) / 100);
  return { briefing, individual, together: length - briefing - individual };
}

const text = (s: Split) => ({ briefing: String(s.briefing), individual: String(s.individual), together: String(s.together) });

export function formFrom(p: Preparation, lists: Lists): Form {
  const preset = lists.time_presets_minutes.includes(p.length_minutes);
  return {
    purpose: p.purpose,
    outcome: p.outcome,
    charter_template: p.charter_template,
    seats: p.seats,
    lengthChoice: preset ? String(p.length_minutes) : CUSTOM,
    customLength: preset ? "" : String(p.length_minutes),
    split: text(p.split),
    practice: p.north_industry_practice,
    library: p.north_problem_library,
    video: p.briefing_video,
    names: p.names ?? "choice",
    approver: p.approver_name,
    approverAccountId: p.approver_account_id,
    signers: p.signers === 2 ? 2 : 1,
  };
}

export function blankForm(lists: Lists): Form {
  const length = lists.default_length_minutes;
  const base: Preparation = {
    purpose: "",
    outcome: "",
    charter_template: lists.default_template,
    seats: lists.seats.min,
    length_minutes: length,
    split: lists.default_split,
    north_industry_practice: false,
    north_problem_library: false,
    briefing_video: lists.briefing_video_options[0] ?? "standard",
    approver_name: "",
    approver_account_id: null,
    names: "choice",
  };
  return formFrom(base, lists);
}

/** The blank form with what the profile drafted laid over it, and the labels of the values it laid. */
export function formFromDraft(lists: Lists): Form {
  const f = lists.profile_draft?.fields ?? {};
  let form = blankForm(lists);
  form = {
    ...form,
    purpose: f.purpose?.value ?? form.purpose,
    outcome: f.outcome?.value ?? form.outcome,
    seats: f.seats?.value ?? form.seats,
    approver: f.approver_name?.value ?? form.approver,
    names: f.names?.value ?? form.names,
  };
  const n = f.length_minutes?.value;
  return n ? withLength(form, lists.time_presets_minutes.includes(n) ? String(n) : CUSTOM, String(n), lists) : form;
}

export function lengthOf(f: Form): number {
  return f.lengthChoice === CUSTOM ? Number.parseInt(f.customLength, 10) : Number.parseInt(f.lengthChoice, 10);
}

/** The length for display: 0 when what was typed is not a number yet. */
export function lengthOrZero(f: Form): number {
  const n = lengthOf(f);
  return Number.isNaN(n) ? 0 : n;
}

const whole = (s: string): number => (/^\d+$/.test(s.trim()) ? Number.parseInt(s, 10) : Number.NaN);

/** The plain-words problem with the time split, or null when it is fine. */
export function splitProblem(f: Form, lists: Lists): string | null {
  const length = lengthOf(f);
  const parts = [whole(f.split.briefing), whole(f.split.individual), whole(f.split.together)];
  if (Number.isNaN(length) || parts.some(Number.isNaN)) return m1.wizard.splitBad(0, Number.isNaN(length) ? 0 : length);
  if (parts.some((n) => n < lists.min_stage_minutes)) return m1.wizard.splitMin(lists.min_stage_minutes);
  const total = parts.reduce((a, b) => a + b, 0);
  return total === length ? null : m1.wizard.splitBad(total, length);
}

export function lengthProblem(f: Form, lists: Lists): boolean {
  const n = lengthOf(f);
  return Number.isNaN(n) || n < lists.custom_length_minutes.min || n > lists.custom_length_minutes.max;
}

export function toPreparation(f: Form): Preparation {
  return {
    purpose: f.purpose.trim(),
    outcome: f.outcome.trim(),
    charter_template: f.charter_template,
    seats: f.seats,
    length_minutes: lengthOf(f),
    split: { briefing: whole(f.split.briefing), individual: whole(f.split.individual), together: whole(f.split.together) },
    north_industry_practice: f.practice,
    north_problem_library: f.library,
    briefing_video: f.video,
    names: f.names,
    approver_name: f.approver.trim(),
    approver_account_id: f.approverAccountId,
    signers: f.signers === 2 ? 2 : null,
  };
}

/** A new length brings the contract's default split with it. */
export function withLength(f: Form, choice: string, custom: string, lists: Lists): Form {
  const next = { ...f, lengthChoice: choice, customLength: custom };
  const n = lengthOf(next);
  return Number.isNaN(n) || n < lists.min_stage_minutes * 3
    ? next
    : { ...next, split: text(defaultSplit(n, lists.default_split_percent)) };
}
