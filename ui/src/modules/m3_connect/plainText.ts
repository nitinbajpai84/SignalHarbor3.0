// Small text clean-ups shared by the module 3 screens. Server text may carry markdown marks from module 2 notes.

/** Backticks and asterisks removed, so a note reads as plain words. */
export function plainText(text: string): string {
  return text.replace(/[`*]/g, "").replace(/\s+/g, " ").trim();
}

/** At most `max` words; the rest is cut with an ellipsis. */
export function shortReason(text: string, max = 12): string {
  const words = plainText(text).split(" ").filter(Boolean);
  return words.length > max ? `${words.slice(0, max).join(" ")}...` : words.join(" ");
}

const ACCEPTED_BY = /\s*\(accepted in module 2 by ([^)]+)\)\s*$/;

/** Splits "text (accepted in module 2 by Mei Tan)" into the text and the name; by is "" when the line has no such tail. */
export function splitAccepted(text: string): { text: string; by: string } {
  const m = ACCEPTED_BY.exec(text);
  return m ? { text: plainText(text.replace(ACCEPTED_BY, "")), by: (m[1] ?? "").trim() } : { text: plainText(text), by: "" };
}

/** One line per person who accepted notes in module 2, instead of the same tail repeated on every line. */
export function acceptedSummary(texts: string[]): string[] {
  const counts = new Map<string, number>();
  for (const t of texts) {
    const by = splitAccepted(t).by;
    if (by) counts.set(by, (counts.get(by) ?? 0) + 1);
  }
  return [...counts].map(([by, n]) => `${by} accepted ${n === 1 ? "this one" : `${n} of these`} in module 2.`);
}

/** The date for a plan card: a real date, else "No date yet" (null, empty or the old "[date]" placeholder). */
export function dateOrNone(value: string | null | undefined, none: string): string {
  const v = (value ?? "").trim();
  return !v || /^\[.*\]$/.test(v) ? none : v;
}
