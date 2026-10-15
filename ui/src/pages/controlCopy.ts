// Words for the control panel. Plain; no model, tool or vendor names.
export const NA = "Not available yet";
/** A pack folder name in plain words: "family_office" reads "Family office". */
export const pack = (industry: string) => (industry.charAt(0).toUpperCase() + industry.slice(1)).replace(/_/g, " ");
export const controlText = {
  title: "Control panel",
  banner: "THIS PANEL HOLDS NO COMPANY DATA",
  rail: "Control panel sections",
  groups: { plane: "THE PLATFORM", company: "THIS COMPANY" },
  planeNav: [
    { id: "companies", label: "Companies" },
    { id: "packs", label: "Industry packs" },
    { id: "catalogue", label: "Module catalogue" },
    { id: "agents", label: "Agents and AI services" },
    { id: "providers", label: "AI services" },
  ],
  companyNav: [
    { id: "brand", label: "Brand and people" },
    { id: "centres", label: "Centres and modules" },
    { id: "leave", label: "What may leave" },
    { id: "retention", label: "Retention" },
    { id: "log", label: "What left" },
  ],
  saved: "Saved.",
  centres: {
    title: "Centres and modules",
    pick: "Company",
    none: "No companies yet.",
    noneLine: "Create the first company above. It starts with every centre off.",
    centres: "Centres",
    modules: "Modules",
    offRule: "A centre that is off is invisible to the company: no pages, no agents, no tools.",
  },
  header: (name: string, industry: string | null, accounts: number | null, on: string[]) =>
    [name, `${industry ? pack(industry) : "No"} pack`, accounts === null ? null : `${accounts} accounts`, on.length ? `${on.join(", ")} on` : "No centre on"]
      .filter(Boolean).join(" · ") + ".",
  nextRequest: "Switches take effect the next time a page is opened.",
  create: {
    title: "Create a company",
    id: "Short name",
    display: "Display name",
    industry: "Industry pack",
    button: "Create company",
    busy: "Creating...",
    note: "The company starts with an empty space and every centre off. Switch on what it bought below.",
    failed: "The company was not created. Check the short name and try again.",
  },
  leave: {
    title: "What may leave",
    rows: {
      gateway: "Questions sent to the AI service",
      internet: "Internet for agents",
      connectors: "Outside tools",
      cloud_push: "Sending data to the cloud",
    },
    gatewayNote: "Always on. Read only.",
    cloudNote: "Needs two named approvers",
    requested: "requested",
    failed: "That change was not saved. Try again.",
  },
  centreMods: { intent: "Intent · Baseline · Assess and plan", build: "Build · Ops readiness", consume: "Foresight · feeds" } as Record<string, string>,
  domains: {
    label: "Email domains agents may write to",
    hint: "Separate with commas. Empty means only the domains of this company's own accounts.",
    save: "Save domains",
    saved: "Saved.",
    none: "None set: only the domains of the company's own accounts.",
    failed: "The domains were not saved. Use names such as example.com.",
  },
  brandRows: { logo: "Logo and colour", accounts: "Accounts", linked: "People linked to accounts", restricted: "Restricted areas" },
  logLast: "What left · the last five things sent out of the machine",
  agents: {
    title: "Agents in this company",
    rows: [
      { name: "North", role: "industry expert", tag: "runs the wall", reads: "Reads the industry pack and the documents you upload for it." },
      { name: "Lens", role: "business analyst", tag: "writes the definitions", reads: "Reads the glossary, definitions and reported figures." },
      { name: "Nira", role: "guide", tag: "guides everyone", reads: "Reads the company profile and what the other agents hand over." },
    ],
  },
  brand: { title: "Brand and people", accounts: (a: number, n: number) => `${a} active of ${n} accounts` },
  log: {
    title: "What left",
    cols: ["Time", "Part", "Type", "Sent to", "Decision", "Size"],
    empty: "Nothing has left yet. Each time an agent sends something out, it is listed here.",
    note: "The log holds a fingerprint of what left, never the text.",
  },
  retention: { title: "Retention", note: "How long this company keeps its records." },
  packs: { title: "Industry packs", note: "The packs a company can draw on." },
  agentsModels: { title: "Agents and AI services", note: "Which agent uses which AI service." },
  catalogue: { title: "Module catalogue" },
  providers: { title: "AI services", unset: "Not set" },
  companies: { title: "Companies", cols: [{ key: "name", label: "Company" }, { key: "pack", label: "Pack" }, { key: "accounts", label: "Accounts" }, { key: "on", label: "Centres on" }] },
  roles: {
    title: "Who can do what",
    rows: [
      { role: "Super admin", can: "Runs the platform. Sees no company data." },
      { role: "Company admin", can: "Sets what may leave and reads the egress log." },
      { role: "Member", can: "Works in the modules the company has on." },
      { role: "Guest", can: "Joins one room by link and sees only that room." },
    ],
  },
  planes: {
    title: "Where things sit",
    rows: [
      { name: "The platform", note: "Companies, switches and AI services. No company data." },
      { name: "The company space", note: "One company's documents, profile and logs." },
      { name: "Live rooms", note: "Rooms and links, gone when the room closes." },
    ],
  },
  notBuilt: {
    title: "Not built yet",
    rows: ["Single sign-on and automatic user sync", "Encryption of stored files beyond the disk", "Automatic clean-up of old records", "Installing in the cloud"],
  },
  refused: "The control panel is for administrators.",
  on: "On",
} as const;
