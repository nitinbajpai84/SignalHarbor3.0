// Screen copy for the data-backed opportunities panels (spec 56). Plain English, British spelling.
export const C = {
  title: "Opportunities",
  sub: "Patterns the operations monitor found in the run log, alerts, feeds and check-ins",
  homeTitle: "Opportunities from the records",
  empty: "Nothing noticed yet. The operations monitor looks for patterns across run days, alerts, feeds and check-in weeks.",
  notSet: "Not available yet. Set the thresholds in the admin defaults.",
  raise: "Raise an opportunity",
  seeAll: "See all on the backlog",
  noEvidence: "No evidence yet",
  suggested: "Suggested by North from the records",
  noNumbers: (who: string) => `The operations monitor found no numbers for this. It was raised by ${who}.`,
  noTouches: "Nothing named yet",
  noEvidenceLong: "No evidence yet. Lens adds definitions and owners once noticed.",
  notJudged: "North has not judged this yet. It waits for Lens's evidence.",
  noAnswers: "North drafts these when it judges Yes.",
  guessed: "Guessed by North",
  moved: "Not available yet: there is no measure of movement after an Initiative.",
  restricted: "A restricted measure",
  titleNeeded: "A title is needed.",
  needTouch: "Name at least one measure, process or source.",
  couldNot: "That could not be saved. Try again.",
  counters: "Counters",
  fewer: "Fewer than five",
} as const;

export const STATE: Record<string, string> = {
  noticed: "Noticed", under_review: "Under review", proposed: "Proposed", picked_up: "Picked up", parked: "Parked", dismissed: "Dismissed",
};
export const CONFIDENCE: Record<string, string> = { fairly_sure: "Fairly sure", not_sure: "Not sure", unlikely: "Unlikely" };
export const SOURCES: Record<string, string> = { alert: "Alert", run: "Run day", week_item: "Check-in item", map_node: "Map node", document: "Document on a shelf" };
export const ANSWERS: [string, string][] = [
  ["goal", "Goal"], ["people", "People"], ["build", "Build"], ["definitions", "Definitions"], ["areas", "Areas"], ["deadline", "Deadline"],
];
export const COUNTER_LABELS: [string, string][] = [
  ["noticed_by_watcher", "Noticed by the operations monitor"], ["noticed_by_person", "Noticed by a person"], ["picked_up", "Picked up"], ["parked", "Parked"],
  ["dismissed", "Dismissed"], ["became_initiatives", "Became Initiatives"], ["judged_yes_then_picked_up", "North said yes, then picked up"],
];
