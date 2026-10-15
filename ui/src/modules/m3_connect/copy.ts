// Module 3's screen copy, in one place (ui-copy.md). One block per package area; each package adds its own.
export const m3 = {
  title: "Assess and plan",
  eyebrow: "Module 3 · with Lens, the business analyst",
  intro: "Score your sources, check sample data against the figures you already report, and agree a phased build plan.",
  crumbModules: "Modules",
  crumbAssess: "Assess and plan",
  yourAssessments: "Your assessments",
  noAssessments: "No assessment yet.",
  noBaseline: "There is no signed baseline yet. Sign your baseline in the Baseline module first, then come back to start the assessment.",
  startTitle: "Start an assessment",
  startHelp: "It starts from your newest signed baseline. Nothing is changed in the baseline.",
  start: "Start from the signed baseline",
  open: "Open the assessment",
  startedOn: (when: string) => `Started ${when}`,
  startNew: "Start a new assessment",
  startNewHelp: (label: string) => `A newer signed baseline exists${label ? `: ${label}` : ""}. Your earlier assessments stay as they are.`,
  saveFailed: "That could not be started. Please try again.",
  comingNext: "Coming in the next package",
  loadFailed: "We could not open that assessment. Please try again.",
} as const;

/** The step strip every assessment screen shows. */
export const m3Steps = {
  label: "Assessment steps",
  map: "Source map",
  request: "Data request",
  scan: "Scan",
  trial: "Trial",
  findings: "Findings",
  plan: "Plan",
  state: { not_started: "Not started", in_progress: "In progress", done: "Done" },
} as const;

/** Nira's small side panel. */
export const m3Nira = {
  name: "Nira, your guide",
  next: "What is next",
  allDone: "Every step is done.",
} as const;

/** The screens the later packages fill in. */
export const m3Area = {
  map: { title: "Source map", sub: "Where each source sits on impact and readiness." },
  intake: { title: "Data request and scan", sub: "What to ask each source owner for, and what came back." },
  trial: { title: "Trial and findings", sub: "Lens's figures against the ones you already report." },
  plan: { title: "Build plan", sub: "The phased plan, for the sponsor and the head of data to sign." },
} as const;
