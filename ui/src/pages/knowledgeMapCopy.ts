// Words for the data knowledge map (spec 55): the Lineage view, the scan filter, the "Where it lives" column and panel. Plain words; no ids.
const n = (count: number, one: string, many = `${one}s`) => `${count} ${count === 1 ? one : many}`;

export const kmText = {
  chips: {
    lineage: "Lineage", lineageHint: "Pick a thing on the map first", checked: (k: number) => `Checked by the scan (${k})`, noneYet: "None yet",
    groups: { data: "Data", processes: "Processes", people: "People", work: "Work" },
  },
  where: { title: "Where it lives", column: "Where it lives", empty: "Nothing recorded yet. The map learns where data lives when a charter is signed." },
  lineage: {
    title: "Lineage", empty: "Nothing is linked to this yet.", restricted: "A restricted field",
    columns: ["Process and step", "System", "File or source", "Field", "Pipeline and mart", "Measure", "Charter and release"],
    back: "Back to the whole map", of: (label: string) => `Everything upstream and downstream of ${label}. Nothing else is shown.`,
  },
  tag: {
    Available: "Available", Missing: "Missing", found: (where: string | null) => (where ? `Found in ${where}` : "Found in another system"),
    confirmed: (who: string) => `, confirmed by ${who}`, rejected: "Said not the same",
  },
  last: { title: "Last map update", none: "The map has not been updated yet.", see: "See what changed" },
  selected: { lives: (where: string) => `Lives in ${where}.` },
  panel: {
    heldIn: "Held in", holds: "Holds", landsAt: "Lands at", writtenIn: "Written down in", feeds: "Feeds", fedBy: "Fed by", producedBy: "Produced by", owners: "Owners",
    lastChecked: "Last checked",
    noSystem: "Not recorded yet: no system named for this", notRecorded: "Not recorded yet", noDocument: "Not written down in any document on the shelves",
    noFeeds: "Feeds no measure yet", noProcess: "No process named yet", noHolds: "Nothing recorded as held here yet", noFedBy: "Fed by nothing yet",
    ownerKinds: { business: "Business owner", data: "Data owner", source: "Source owner" } as Record<string, string>,
    noOwner: (kind: string) => `Not available yet: ${kind.toLowerCase()} not named`,
    notChecked: "Not checked yet. The first scan in the gap analysis checks it.",
    checked: (word: string, when: string, where: string | null, confirmed: string | null) =>
      `${word}${where ? ` in ${where}` : ""}${confirmed ? `, confirmed by ${confirmed}` : ""}. Scanned ${when}.`,
    openGap: "Open the gap report", showLineage: "Show lineage", confirm: "Confirm it is the same", reject: "Not the same thing",
    reason: "Why is it not the same thing?", send: "Save", cancel: "Cancel", saved: "Saved. The map is updating.", failed: "That could not be saved. Nothing was changed. Try again.",
    unavailable: "Not available yet: the scan results could not be read.",
  },
  fresh: (k: number) => `${n(k, "update")} this week`,
} as const;
