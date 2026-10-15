// Words on "How my organisation connects" (Desk-Graph and Phone-Graph artboards). Plain words; no ids, no figures.
const n = (count: number, one: string, many = `${one}s`) => `${count} ${count === 1 ? one : many}`;

export const graphText = {
  title: "How my organisation connects",
  subline: (s: { walls: number; charters: number; baselines: number; things: number; links: number }) =>
    `Built from ${n(s.walls, "wall")}, ${n(s.charters, "charter")} and ${n(s.baselines, "baseline")}. ${n(s.things, "thing")}, ${n(s.links, "link")}. `
    + "Open to everyone in the company. No figures: names and links only.",
  phoneSubline: (s: { things: number; links: number }) => `${n(s.things, "thing")} · ${n(s.links, "link")} · open to everyone · no figures`,
  chips: {
    whole: "Whole map", wall: "By wall", trace: "Trace a measure", holes: (k: number) => `Gaps: ${k}`, fresh: (k: number) => `New this week: ${k}`,
    phoneTrace: "Trace", phoneFresh: (k: number) => `New: ${k}`,
  },
  columns: { walls: "Walls", problems: "Problems", measures: "Measures", systems: "Systems", owners: "Owners" },
  more: (k: number) => `${k} more`,
  howTo: "Hover a thing to see what it links to. Click a measure to trace it from the problem that asked for it to the system and owner that supply it. "
    + "A dashed ring is a gap: a measure nobody has a source for yet.",
  traceHint: "Click a measure on the map to trace it.",
  selected: (label: string) => `Selected: ${label}`,
  openDefinition: "Open the definition",
  trail: {
    asked: (walls: string[], problems: string[]) =>
      walls.length ? `Asked for by the ${walls.join(" and the ")} wall${problems.length ? ` (problem: ${problems.join(", ").toLowerCase()})` : ""}.`
        : problems.length ? `Asked for by the problem: ${problems.join(", ").toLowerCase()}.` : "No wall has asked for it yet.",
    defined: "Defined in the baseline.",
    supplied: (s: string[]) => (s.length ? `Supplied by ${s.join(" and ")}.` : "No source yet: this is a gap."),
    owned: (o: string[]) => (o.length ? `Owned by ${o.join(" and ")}.` : "No owner named yet."),
    links: (k: number) => `Linked to ${n(k, "thing")} on the map.`,
  },
  phoneTraceTitle: "Tap a measure to trace it",
  phoneTraceHint: "Tap a measure on the wall above to see who asked for it, where it comes from and who owns it.",
  wallTitle: (label: string) => `${label} wall`,
  wallCounts: (p: number, m: number) => `${n(p, "problem")} · ${n(m, "measure")}`,
  nextWall: "Next wall",
  legend: "■ Wall · ● Problem · ● Measure · ■ System · ◌ Gap",
  fresh: {
    title: "New this week", none: "Nothing new on the map this week.", andMore: (k: number) => `and ${k} more`,
    groups: { Measure: "Measures", Problem: "Problems", System: "Systems", Source: "Systems", Person: "Owners" } as Record<string, string>,
    // One true sentence from the versions of the week; the strongest change wins. Names only, never an id or a figure.
    say: (label: string, rows: { what: string; by: string }[]) => {
      const has = (w: string) => rows.filter((r) => r.what.startsWith(w));
      const acc = has("Accepted:"), conf = has("Definition confirmed"), drafted = has("Definition drafted");
      if (acc.length) return `${label} changed after ${acc[0]?.by} accepted ${acc.length === 1 ? "a suggestion" : `${acc.length} suggestions`}.`;
      if (conf.length) return `${label} was confirmed by ${conf[0]?.by}.`;
      if (drafted.length) return `${label} was defined in the baseline.`;
      if (has("Name changed").length) return `${label} was renamed.`;
      if (has("Who may see it changed").length) return `Who may see ${label} changed.`;
      // a row written as a full sentence (an ambiguity raised, a comment added, a suggestion accepted) speaks for itself
      const said = rows.find((r) => /^(An? |The )/.test(r.what) && !r.what.startsWith("Linked") && !r.what.startsWith("No longer"));
      if (said) return `${label}: ${said.what.charAt(0).toLowerCase()}${said.what.slice(1)}.`;
      return `The links around ${label} were updated.`;
    },
  },
  keptOut: {
    title: "What is kept out",
    body: "Figures, records and documents never appear here. Anonymous cards are never linked to a person. Pay and HR areas show as grey silhouettes to anyone not on their list, even here.",
  },
  phoneFoot: "Pay and HR areas show as grey silhouettes to anyone not on their list.",
  noneInView: "Nothing on the map fits this view.",
  loading: { title: "Drawing the map", lines: ["Reading the walls, charters and baseline your company has signed."] },
  empty: { title: "Nothing is on the map yet", lines: ["The map grows from the walls, the charter and the baseline. It fills in as soon as the first charter is signed."] },
  refused: { title: "The map is not open to you here", lines: ["Your company space could not be opened. Please ask your administrator."] },
  error: { title: "The map could not be loaded", lines: ["Nothing was changed. Try again in a moment."], retry: "Try again" },
  tabs: { pulse: "Pulse", intent: "Intent", build: "Build", consume: "Consume", map: "Map" },
} as const;
