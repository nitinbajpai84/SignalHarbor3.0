// Words on the pulse page (the five pulse artboards). Plain words; no ids.
export type Layout = "participant" | "organiser" | "data" | "sponsor";

export const pulseText = {
  strips: {
    invited: "Invited", decide: "Decide", give: "Give", watch: "Watch", start: "Requests to start", running: "Walls running",
    waiting: "Waiting on others", ops: "Today's ops report", sign: "Sign", quarter: "Your walls so far", initiatives: "Your initiatives",
  } as Record<string, string>,
  amber: new Set(["decide", "start", "waiting", "ops", "sign"]),
  warnWhenAny: new Set(["Late", "Checks failed"]), // ops report counters shown in amber when not zero
  // The order of the sections per artboard. "quarter" and "initiatives" are tables of counts, not lines.
  order: {
    participant: ["invited", "decide", "give", "watch"],
    organiser: ["start", "running", "waiting", "invited", "decide", "give", "watch", "quarter"],
    data: ["ops", "sign", "invited", "decide", "give", "watch"],
    sponsor: ["decide", "initiatives", "invited", "give", "watch"],
  } as Record<Layout, string[]>,
  greeting: (hour: number, first: string) => `${hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening"}, ${first}.`,
  summary: (n: number, m: number | null) => `${n} ${n === 1 ? "thing needs" : "things need"} you${m ? ` · about ${m} minutes` : ""}`,
  // The data team and the sponsor read their day as kinds of work (artboards Desk-Data, Desk-Sponsor): the first class a line matches names it.
  kinds: [
    { test: (id: string) => id.startsWith("gap:"), one: "critical gap", many: "critical gaps" },
    { test: (id: string) => id.startsWith("late:"), one: "late file", many: "late files" },
    { test: (id: string, kind: string) => kind === "signature", one: "signature", many: "signatures" },
    { test: (id: string) => id.startsWith("purpose:"), one: "sentence to write", many: "sentences to write" },
    { test: (id: string, kind: string) => kind === "invite", one: "invite", many: "invites" },
    { test: () => true, one: "other thing", many: "other things" },
  ],
  minutes: (m: number | null) => (m ? `about ${m} minutes` : ""),
  drafted: "Nira, your guide, drafted all of them",
  nothing: "Nothing needs you today.",
  nothingLine: "New asks appear here when someone names you. Open the map to see how your measures connect.",
  dayTitle: "Your day",
  reading: "Reading your day from the company's records.",
  error: "Your day could not be read.",
  errorLine: "The records may be busy. Try again in a moment.",
  retry: "Try again",
  notYet: "Not available yet",
  none: "None",
  watchLabel: { measure: "Your measures", brief: "Market brief", ops: "Data runs", outcome: "Outcome shared with you", clock: "Time box", rating: "Rate it" } as Record<string, string>,
  outside: "Outside material",
  table: [
    { key: "name", label: "Initiative" }, { key: "where", label: "Where it is" }, { key: "hurdle", label: "Hurdle" }, { key: "who", label: "Who clears it" },
  ],
  map: {
    title: "How my organisation connects",
    open: "Open",
    body: {
      participant: "Problems, measures, systems and owners, and how they link. Open to everyone in the company. No figures.",
      organiser: "Problems, measures, systems and owners, and how they link. Open to everyone in the company. No figures.",
      data: "For you the map opens on the trace: each measure followed to its source, its fields and the data run that feeds it.",
      sponsor: "For you the map opens on impact: which problems each initiative moves, and who is involved.",
    } as Record<Layout, string>,
    openLabel: { participant: "Open", organiser: "Open", data: "Open the trace", sponsor: "Open" } as Record<Layout, string>,
    legend: {
      participant: ["Problems", "Measures", "Systems", "Owners"], organiser: ["Problems", "Measures", "Systems", "Owners"],
      data: ["Measure", "Sources", "Late source", "Data run"], sponsor: ["Initiatives", "Problems", "People"],
    } as Record<Layout, string[]>,
    newWeekTitle: "New this week",
    newWeekItems: (names: string[]) => [...new Set(names)].slice(0, 3),
    newWeekMore: (names: string[]) => { const k = new Set(names).size - 3; return k > 0 ? `and ${k} more` : ""; },
    owned: (n: number) => (n === 0 ? "" : n === 1 ? " You own one of them." : ` You own ${n} of them.`),
    none: "Nothing new this week.",
  },
  phoneMap: { participant: "Open to everyone in the company. No figures.", data: "Trace a measure to its source", organiser: "", sponsor: "" } as Record<Layout, string>,
  memory: { title: "What the agents remember about you", body: "What you told them and what they learned, kept for your next conversation.", link: "Read or correct" },
  drafts: {
    title: "Drafts from Nira, your guide, waiting for you to send",
    kinds: {
      invite: ["wall invite", "wall invites"], reminder: ["reminder", "reminders"], sponsor_ask: ["note from a sponsor", "notes from sponsors"],
      ops_report: ["ops report", "ops reports"], owner_ask: ["ask to an owner", "asks to owners"],
    } as Record<string, [string, string]>,
    
    review: (n: number) => (n === 1 ? "Review it" : `Review all ${n}`),
  },
  buildOnly: { title: "Only you see Build and Ops", body: "The business roles never see data runs, logs or build plans. They see the measures that come out, and the map." },
  ask: { title: "Ask for a new wall", body: "One line on what you want to know. The organiser starts the wall from it.", link: "Write one line" },
  footer: {
    participant: "Everything here is read from the company's own records. Nothing is typed into this page. A line disappears when the record changes.",
    organiser: "Nothing is sent until you press Send. Names are replaced before anything leaves the company.",
    data: "The ops report is written from the day's data runs. No figure here is typed by a person.",
    sponsor: "Status comes from the records, not from anyone's report. Hurdles are named from what is late or unanswered.",
  } as Record<Layout, string>,
  tabs: { pulse: "Pulse", intent: "Intent", build: "Build", consume: "Consume", map: "Map" } as Record<string, string>,
  centres: { intent: "Intent Centre", build: "Build Centre", consume: "Consume Centre", map: "How my organisation connects" } as Record<string, string>,
};
