// Words on the new top bar. Plain words; no ids.
export const shellText = {
  product: "Signal Harbor",
  // The bar, in its fixed order (A-073). Control sits in the avatar menu unless it is the person's only centre.
  bar: [
    { id: "pulse", label: "ACTION", to: "/centre/action" },
    { id: "intent", label: "INTENT CENTRE", to: "/centre/intent" },
    { id: "build", label: "BUILD CENTRE", to: "/centre/build/ops" },
    { id: "consume", label: "CONSUME CENTRE", to: "/centre/consume" },
    { id: "tickets", label: "TICKETS", to: "/centre/tickets" },
    { id: "map", label: "COMPANY MAP", to: "/centre/map" },
    { id: "control", label: "CONTROL", to: "/centre/control" },
  ],
  // The four centres (V5, 11 Oct), in bar order: Action first (the landing page), then Build, Consume, Map. Intent is step 1 of Build now.
  // Who sees which is decided in roles.ts (barFor).
  centres: [
    { id: "action", label: "Action", title: "Things to do", to: "/centre/action" },
    { id: "build", label: "Build", title: "Start and follow projects", to: "/centre/build" },
    { id: "consume", label: "Consume", title: "Reports and insights", to: "/centre/consume" },
    { id: "map", label: "Map", title: "How it all connects", to: "/centre/map" },
  ],
  settings: { label: "Settings", to: "/centre/settings" },
  control: "Control panel",
  // Settings sections listed in the account menu so each is two clicks away.
  sections: [
    { label: "People and access", to: "/centre/settings/people" },
    { label: "Rules", to: "/centre/settings/rules" },
    { label: "Sources and data model", to: "/centre/settings/model" },
    { label: "Templates and skills", to: "/centre/settings/templates" },
    { label: "Activity trail", to: "/centre/settings/register" },
    { label: "Agent runs and cost", to: "/centre/settings/runs" },
    { label: "Testing or Real use", to: "/centre/settings/mode" },
  ],
  agents: { label: "Agent templates and skills", to: "/centre/admin/agents" },
  model: { label: "Data model", to: "/centre/admin/model" },
  // v2.0 evidence to action (9 Oct): the morning screens; each route checks access on the server.
  v2: [
    { label: "TODAY", to: "/centre/today" },
    { label: "EVIDENCE", to: "/centre/evidence" },
    { label: "ACTION DESK", to: "/centre/desk" },
    { label: "DATA INTAKE", to: "/centre/data/intake" },
  ],
  rules: { label: "Rules register", to: "/centre/admin/rules" },
  memory: { label: "What the agents remember about you", to: "/centre/settings/memory" },
  library: { label: "Library", to: "/centre/library" },
  register: { label: "Activity trail", to: "/centre/register" },
  refused: "That page is not open to you. This is your start page.",
  notYet: "Not available yet",
  centresMenu: "Centres",
  accountMenu: "Account menu",
  signOut: "Sign out",
  legacy: "Legacy screens",
  navLabel: "Centres",
  signedInAs: "Signed in",
} as const;
