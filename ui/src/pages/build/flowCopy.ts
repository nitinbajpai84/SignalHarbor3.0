// Words for Span's target card and Span's notes (SF17). Plain words, no vendor names, British spelling.
export const flowCopy = {
  spanTag: "Span's suggestion",
  flowTag: "Flow's note",
  target: {
    title: "Span's target architecture",
    loading: "Span's target is on its way.",
    error: "Span's target could not be read. Nothing was changed. Try again in a moment.",
    refused: "The target architecture is for the people on this change.",
    empty: "Span drafts the target architecture once an Initiative is handed to Build.",
    whyHead: "Why Span suggests this",
    diagramAlt: "Span's suggested target architecture as a diagram",
    ask: "Ask Span to draft the target",
    asking: "Span is drafting",
    drafting: "Span is drafting the target... This can take a minute.",
    askAgain: "Ask Span to draft again",
    askFailed: "Span could not draft the target. Nothing was changed.",
    placements: (n: number) => `${n} ${n === 1 ? "component is" : "components are"} suggested.`,
  },
  run: {
    button: "Flow's note",
    loading: "Flow is reading the run.",
    error: "Flow's note could not be read. Nothing was changed. Try again in a moment.",
    refused: "Flow's notes on runs are for the data team.",
    empty: "Flow has nothing to say about this run yet.",
    again: "Ask Span again",
    close: "Hide the note",
  },
  incident: {
    head: "Flow's notes on open alerts",
    loading: "Flow is reading the alerts.",
    error: "Flow's notes could not be read. Nothing was changed. Try again in a moment.",
    refused: "Flow's notes on alerts are for the data team.",
    empty: "No open alert needs a note from Span.",
    next: "Next step",
    ack: "Acknowledge with this note",
    edit: "Edit",
    save: "Acknowledge with my words",
    cancel: "Cancel",
    failed: "Could not save. Try again.",
    waits: (who: string | null) => (who ? `Waiting for ${who} to check it.` : "Waiting for the person named on the alert."),
  },
  dialect: {
    title: "SQL for your warehouse",
    loading: "Reading the warehouse translation.",
    error: "The warehouse translation could not be read. Nothing was changed. Try again in a moment.",
    refused: "The warehouse translation is for the data team.",
    download: "Download the SQL draft",
    show: "Show the SQL",
    differs: (n: number) => `${n} ${n === 1 ? "statement is" : "statements are"} written for your warehouse.`,
  },
  na: "Not available yet",
  /** A count a person reads. Under five is never a figure (egress rule): "Fewer than five rows"; none reads "No rows". */
  rows: (n: number | null | undefined): string =>
    typeof n !== "number" ? "Not available yet" : n === 0 ? "No rows" : n < 5 ? "Fewer than five rows" : `${n} rows`,
};

export interface Quarantined { rule: string; field: string; count: number }
/** The check's words from a rule id such as "k12:fund id must not be empty". */
export const checkText = (rule: string): string => rule.split(":").slice(1).join(":").trim() || rule;
/** "12 rows set aside for fund id must not be empty". */
export const setAside = (q: Quarantined): string => `${flowCopy.rows(q.count)} set aside for ${checkText(q.rule)}`;
