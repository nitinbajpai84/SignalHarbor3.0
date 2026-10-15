// Screen copy and shapes for Proving (spec 58). Plain English, British spelling. Every figure shows only when the server sends it.
export type Verdict = "working" | "partly" | "not" | "too_early";
export type Action = "keep" | "more_time" | "send_back" | "stop";
export interface Trace { kind: string; ref: string | null }
export interface Figure { value: number | null; unit?: string | null; periods?: number | null; period?: string | null; by?: string | null; trace?: Trace | null }
export interface Note { text: string; by: string; trace: Trace | null; at: string }
export interface Report {
  week_key: string; drafted_at: string; state: "drafted" | "confirmed" | "no_change";
  figures: boolean; before: Figure | null; now: Figure | null; target: Figure | null;
  series: { period: string; value: number; change?: number | null }[]; normal_range: { low: number; high: number; periods: unknown } | null;
  notes: Note[] | null; verdict: Verdict; verdict_word: string; rule: string; confidence: "fairly_sure" | "not_sure" | "unlikely"; confidence_word?: string | null;
  changed_verdict: { from: Verdict; to: Verdict; reason: string } | null;
  confirmed_by: string | null; confirmed_at: string | null; measure?: { code: string; name: string | null; unit?: string | null };
  start_period?: string | null; can?: { confirm: boolean; add_note: boolean }; missing?: string[];
}
export interface ReviewDraft {
  summary: string | null; verdicts: string[]; proposed: Action | null; learning: string | null; sent: boolean;
  action: Action | null; by: string | null; reason: string | null; review_date: string | null;
  returned: { by: string; at: string; reason: string } | null; confirmed_by: string | null; confirmed_at: string | null;
}
export interface Proving {
  state: "waiting" | "proving" | "reviewing" | "proved" | "returned" | "stopped";
  title: string; sponsor: string | null; organiser: string | null; review_date: string | null; proving_since?: string | null; verdict_word?: string | null;
  hypothesis: { belief: string | null; lens: string | null; measure: { id: string; name: string | null } | null; target: { value: number; unit: string | null } | null; target_by: string | null; version: number; href: string | null } | null;
  start: { at: string; from: "release" | "closure" | "go_live"; who: string | null; changed: { by: string; at: string; reason: string } | null } | null;
  measure: { code: string; name: string; unit: string | null; grain?: string } | null; figures?: boolean;
  reports: { week_key: string; state: Report["state"]; verdict_word: string }[];
  latest: Report | null; rules: { proving_min_periods: number | null; counter_periods: number | null; report_day?: string; set?: { proving_min_periods: boolean; counter_periods: boolean } };
  receipts: { named: number; anonymous: number; seen?: number } | null; review: ReviewDraft | null; returned_to: string | null;
  can: { change_start: boolean; review: boolean; confirm_review: boolean; add_note?: boolean };
}

export const P = {
  title: "Proving",
  chip: { waiting: "Waiting for release", proving: (d: string) => `Proving since ${d}`, proved: "Proved", returned: "Sent back to the radar", stopped: "Stopped" },
  noHypothesis: "Not available yet: this Initiative carries no hypothesis. North drafted one from the charter's measures; confirm it below.",
  hypothesisHead: "What we believed", frozen: (v: number) => `Frozen at charter v${v}`, openHypothesis: "Open the hypothesis",
  waitingLine: (m: string) => `Waiting for release: the measure ${m} is not in a signed release yet.`,
  live: (d: string, from: string) => `Live since ${d}, from ${from}.`,
  fromRelease: (who: string | null, d: string) => `the release signed${who ? ` by ${who}` : ""} on ${d}`,
  fromClosure: (d: string) => `the closure on ${d}`,
  fromGoLive: (d: string) => `the go-live on ${d}`,
  trace: { hypothesis: "From the frozen hypothesis", data: "From the measure's data", record: "From a record" } as Record<string, string>,
  changeStart: "Change the start date", startReason: "Why the start date moved", saveStart: "Save the start date", startNeeded: "A date and a reason are needed.",
  startChanged: (by: string, reason: string) => `Start date changed by ${by}: ${reason}.`,
  latest: "Latest report", noReports: "No reports yet.", firstReport: "The first report is drafted on the first Friday after the start date.",
  before: "Before", now: "Now", target: "Target", series: "Since the start", chartNone: (m: string) => `Not available yet: no period of ${m} has landed since the start.`,
  noFigures: "You cannot see this measure's figures.", figureMissing: (what: string) => `Not available yet: ${what}.`,
  how: "How the verdict is decided",
  howRules: [
    "Too early: fewer periods have landed since the start than the company needs, or the baseline, target or settings are missing.",
    "Working: the last periods are all at or past the target.",
    "Partly: the latest period is outside the usual range towards the target but not at it, or a named group has not moved.",
    "Not working: the latest period is inside the usual range, or has moved the wrong way.",
  ],
  howNotSet: "Not available yet. The company has not set the periods a verdict needs and the periods North checks against, so every verdict reads Too early.",
  periodsNeed: (n: number) => `A verdict needs ${n} ${n === 1 ? "period" : "periods"}.`,
  periodsCheck: (n: number) => `North checks against the ${n} ${n === 1 ? "period" : "periods"} before the start.`,
  setRules: "Set these rules",
  hears: "Who hears about it", hearsNone: "Nobody raised this from a voice; no receipts are due.",
  hearsLine: (sponsor: string | null, named: number, anon: number) => [
    sponsor ? `${sponsor} (sponsor)` : null, "the people on the Initiative",
    named ? `${named} named ${named === 1 ? "voice" : "voices"}` : null,
    anon ? `${anon} anonymous ${anon === 1 ? "voice" : "voices"}, told only through the item they raised` : null,
  ].filter(Boolean).join(", "),
  openReview: "Open the review", unreadable: "The Proving record could not be read. Nothing was changed.", retry: "Try again", saving: "Saving", couldNot: "That could not be saved. Try again.",
  weekOf: (d: string) => `Week of ${d}`, state: { drafted: "Drafted by North", confirmed: "Confirmed", no_change: "No change" },
  confirmedBy: (who: string, d: string) => `Confirmed by ${who} on ${d}`,
  verdict: { working: "Working", partly: "Partly", not: "Not working", too_early: "Too early" } as Record<Verdict, string>,
  confidence: { fairly_sure: "Fairly sure", not_sure: "Not sure", unlikely: "Unlikely" },
  verdictBy: "North's verdict", noChange: (m: string) => `No new period of ${m} since last week. Nothing to confirm.`,
  notes: "What else moved this measure", noNotes: "North found nothing else that moved this measure.", addNote: "Add a note",
  noteText: "Note", noteRecord: "The record it rests on", noRecord: "No record",
  saveNote: "Save the note", noteNeeded: "A note needs its text and either a record or \"No record\".",
  confirm: "Confirm this report", change: "Change the verdict", newVerdict: "New verdict", changeReason: "Why you are changing it",
  saveChange: "Confirm with this verdict", changeNeeded: "Choose a different verdict and give a reason.",
  changed: (from: string, by: string, to: string, why: string) => `North said ${from}. ${by} changed it to ${to}: ${why}.`,
  earlier: "Earlier weeks", back: "Back to Proving", seriesTable: "Period by period", period: "Period", value: "Value", fromBefore: "Change from before",
  review: {
    title: "The review", summary: "North's summary", none: "No report was confirmed. North cannot propose an outcome; choose one yourself.", proposed: "North proposes this",
    keep: "It works, keep it running", more: "Give it more time", back: "Send back to the radar", stop: "Stop proving",
    newDate: "New review date", reason: "Reason", learning: "What we learnt", learningHint: "North drafted this. Edit it so it says what held, what did not, and for whom.",
    send: (who: string) => `Send to ${who}`, confirm: "Confirm the outcome", returnTo: (who: string) => `Send back to ${who}`, returnReason: "Why it goes back",
    returnedBy: (by: string, why: string) => `${by} sent it back: ${why}`,
    chosen: (by: string) => `${by} chose a way forward and sent it for your confirmation.`, sentTo: (who: string) => `Sent to ${who}. They confirm the outcome.`,
    needs: "Choose one and fill in what it asks for.", pick: "Choose a way forward", returned: "It went back to the organiser.", notYet: "The review has not been sent yet.",
  },
  rules: { title: "Proving rules", min: "Periods a verdict needs", counter: "Periods North checks against", notSet: "Not set: every verdict reads Too early", save: "Save", saved: "Saved.", linkRadar: "Set in the radar thresholds", bad: "Use a whole number of one or more." },
  came: (title: string, chip: string) => `This became ${title} (${chip})`,
} as const;

export const ACTION_LABEL: Record<Action, string> = { keep: P.review.keep, more_time: P.review.more, send_back: P.review.back, stop: P.review.stop };
