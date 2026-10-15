// Screen copy for the opportunity radar and the hypothesis record (spec 57). Plain English, British spelling.
/** "Not available yet" once, with the reason after it: a reason that already starts with it is not repeated. */
export const notYet = (why?: string | null) => {
  const r = (why ?? "").replace(/^not available yet[:.]?\s*/i, "").trim();
  return r ? `Not available yet: ${r}` : "Not available yet";
};

export const R = {
  title: "What the records suggest",
  sub: "Patterns in your data, documents and what people said. North checks each one before it reaches you.",
  tabs: { mine: "My line of work", areas: "By area", lenses: "By lens" },
  emptyMine: "Nothing on the radar touches your work yet.",
  noArea: "You are not tagged to an area. Ask your company admin.",
  pickArea: "Area",
  emptyColumn: "Nothing here yet.",
  rejectedTitle: "Checked and set aside",
  rejectedNone: "Nothing has been set aside yet.",
  howTitle: "How the radar works",
  notRun: "The radar has not run yet. Thresholds are not set.",
  thresholdsLink: "Radar thresholds",
  thresholdsNotice: (n: number, of: number) => `Not available yet. ${n} of ${of} radar thresholds are not set, so those checks stay silent.`,
  theme: (n: number) => `Theme, ${n} ${n === 1 ? "voice" : "voices"}`,
  proposed: "Suggested by North from the records",
  notAvailable: (why?: string | null) => notYet(why),
  couldNot: "The radar could not be read. Nothing was changed.",
  retry: "Try again",
  loading: "Reading the radar.",
  open: "Open the radar",
  hidden: (n: number) => `${n} ${n === 1 ? "opportunity is" : "opportunities are"} hidden because North is less sure than the company setting allows.`,
} as const;

export const LENSES: [string, string][] = [["new_revenue", "New revenue"], ["process_cost", "Process cost"], ["retention", "Retention"], ["risk", "Risk"]];
export const LENS_NAME: Record<string, string> = Object.fromEntries(LENSES);
export const CONFIDENCE: Record<string, string> = { fairly_sure: "Fairly sure", not_sure: "Not sure", unlikely: "Unlikely" };
export const BASIS: Record<string, string> = {
  gap_to_target: "Gap to target", stated: "Stated by a person", pack: "What others in the industry usually see (pack)", earlier_initiative: "Measured after an earlier Initiative",
};
export const STATES: Record<string, string> = { noticed: "Noticed", under_review: "Under review", proposed: "Proposed", picked_up: "Picked up", parked: "Parked", dismissed: "Dismissed", rejected: "Rejected by North" };

export const H = {
  hypothesis: "Hypothesis", notWritten: "North has not written a hypothesis yet. It waits for Lens's evidence.",
  belief: "Belief", lens: "Lens", measure: "Measure", baseline: "Baseline", target: "Target", uplift: "Expected uplift", confidence: "Confidence", review: "Review date",
  noTarget: "No target yet. Set one or leave it for the start questions.", saveTarget: "Save target", saveReview: "Save review date", saved: "Saved as a new version.",
  evidence: "Evidence by kind", groups: [["data", "Data"], ["document", "Documents"], ["voice", "Voices"]] as [string, string][], noKind: "No evidence of this kind.",
  noDoc: "A document you cannot open", anon: "Someone, anonymously", supports: "supports", counters: "counters",
  counter: "Counter-evidence check", notChecked: "North has not checked this yet.", holds: "Holds", broken: "Broken", lookedFor: "What North looked for", found: "What it found",
  voices: "Voices", rejectedBecause: "Rejected because", guess: "Guessed by North", couldNot: "That could not be saved. Try again.",
} as const;

export const T = {
  card: "Radar thresholds",
  keys: [
    ["late_same_weekday", "Late on the same weekday"], ["drift_periods", "Periods of drift"], ["checkin_items_same_step", "Check-in items on the same step"],
    ["window_days", "Days looked back"], ["min_periods_for_pattern", "Periods before a pattern counts"], ["theme_min_voices", "Voices that make a theme"], ["counter_periods", "Periods North checks against"],
  ] as [string, string][],
  unset: "Not set: this check stays silent", conf: "Show on the radar from", confOptions: [["", "Not set"], ["unlikely", "Unlikely and above"], ["not_sure", "Not sure and above"], ["fairly_sure", "Fairly sure only"]] as [string, string][],
  save: "Save radar thresholds", saved: "Saved.", bad: "That value is not valid. Use a whole number of one or more.", couldNot: "That could not be saved. Try again.",
  note: "No value is built in. An empty row means the check stays silent.",
} as const;
