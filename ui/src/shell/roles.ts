// The one role table (A-073): which centres each role sees, in bar order, and where it lands.
// sh_platform/route_permissions.yaml follows it; tests/auth/test_role_table.py reads the table below from this file's
// text, so keep it plain JSON between the two markers.
// PF2: every role reads Consume (Nitin, 10 Oct); the figures in it stay filtered by each person's access.
// V6: `head_of_data` is a seat held in addition to analyst (it opens no centre on its own); the plan, design pack and verified map are approved by it.
export type Centre = "pulse" | "intent" | "build" | "consume" | "tickets" | "map" | "control";

export const ROLE_TABLE: Record<string, { centres: readonly Centre[]; lands: string }> = /* role table */ {
  "participant": { "centres": ["pulse", "intent", "consume", "tickets", "map"], "lands": "/centre/action" },
  "owner": { "centres": ["pulse", "intent", "consume", "tickets", "map"], "lands": "/centre/action" },
  "approver": { "centres": ["pulse", "intent", "consume", "tickets", "map"], "lands": "/centre/action" },
  "sponsor": { "centres": ["pulse", "intent", "consume", "tickets", "map"], "lands": "/centre/action" },
  "analyst": { "centres": ["pulse", "intent", "build", "consume", "tickets", "map"], "lands": "/centre/action" },
  "head_of_data": { "centres": [], "lands": "/centre/action" },
  "company_admin": { "centres": ["pulse", "intent", "build", "consume", "tickets", "map", "control"], "lands": "/centre/action" },
  "super_admin": { "centres": ["control"], "lands": "/centre/control" }
} /* end role table */;

/** Every centre any of these roles sees. A person with several roles sees the union. */
export const centresFor = (roles: readonly string[] | undefined): Set<Centre> =>
  new Set((roles ?? []).flatMap((r) => ROLE_TABLE[r]?.centres ?? []));

export type FourCentre = "action" | "build" | "consume" | "map";

/** The four-centre bar (V5), in order: Action, Build, Consume, Map. Action is open to every company role; the rest follow the table above.
 *  Intent is step 1 of Build, so a role that has the Intent centre sees Build too (it opens the project list and the start of a project).
 *  Head of data and admin are analyst and company_admin. There is no separate Operations role yet. */
export const barFor = (roles: readonly string[] | undefined): FourCentre[] => {
  const mine = centresFor(roles);
  const out: FourCentre[] = [];
  if (mine.has("pulse")) out.push("action");
  if (mine.has("build") || mine.has("intent")) out.push("build");
  if (mine.has("consume")) out.push("consume");
  if (mine.has("map")) out.push("map"); // every role with the Map; the Health tab stays data-team only
  return out;
};

/** Settings, by role (ROLE1, 12 Oct). Everyone has their own three; the head of data and the data engineer each get their own set; the administrator gets all.
 *  A head of data is not also shown the engineer's tools (Anita holds analyst beside head_of_data); the approver also reads Rules (P15). Server permissions stay the real gate. */
export type SettingKey = "people" | "rules" | "identifiers" | "instruments" | "model" | "templates" | "register" | "intent" | "delivery" | "connectors" | "mcp" | "demo" | "jobs-events" | "runs" | "mode" | "memory" | "teach" | "cycle";
const OWN: SettingKey[] = ["memory", "mode", "register"]; // What the agents remember about you; Testing or Real use; Activity trail (your own, unless you are on the data team)
const HEAD_SET: SettingKey[] = ["model", "rules", "identifiers", "instruments", "cycle"]; // cycle: the company's working date (FIXE2); the administrator has it too
// model: view only. Delivery channels stay the administrator's: the server refuses it to everyone else (it sets the egress hosts), so the menu does not offer it.
const ENGINEER_SET: SettingKey[] = ["identifiers", "instruments", "connectors", "jobs-events", "model"];
export const isAdmin = (roles: readonly string[] | undefined): boolean => (roles ?? []).includes("company_admin");
export const isHeadOfData = (roles: readonly string[] | undefined): boolean => !isAdmin(roles) && (roles ?? []).includes("head_of_data");
/** The data engineer / ops manager seat: the data team without the head of data seat. */
export const isEngineer = (roles: readonly string[] | undefined): boolean => !isAdmin(roles) && !isHeadOfData(roles) && (roles ?? []).includes("analyst");
export const canOps = (roles: readonly string[] | undefined): boolean => isAdmin(roles) || isEngineer(roles);
/** Who is on the data team and so sees everyone's activity, not only their own. */
export const isDataTeam = (roles: readonly string[] | undefined): boolean => (roles ?? []).some((x) => x === "company_admin" || x === "analyst" || x === "head_of_data");
/** TEACH1: who may teach which agent (sh_platform/v1/teach.py RIGHTS is the real gate; this decides what the menu shows). Span: head of data, data engineer, admin; North: admin;
 *  Tally: business owner, sponsor, approver, admin; Lumen: business owner, head of data, admin. */
export const TEACH_RIGHTS: Record<string, readonly string[]> = {
  span: ["head_of_data", "analyst", "company_admin"], north: ["company_admin"], tally: ["owner", "sponsor", "approver", "company_admin"], lumen: ["owner", "head_of_data", "company_admin"],
};
export const canTeach = (roles: readonly string[] | undefined, agent: string): boolean => (TEACH_RIGHTS[agent] ?? []).some((r) => (roles ?? []).includes(r));
export const teachable = (roles: readonly string[] | undefined): string[] => Object.keys(TEACH_RIGHTS).filter((a) => canTeach(roles, a));
export const settingsFor = (roles: readonly string[] | undefined): Set<SettingKey | string> => {
  const r = roles ?? [];
  if (!r.some((x) => x in ROLE_TABLE && x !== "super_admin")) return new Set();
  if (isAdmin(r)) return new Set(["people", "rules", "identifiers", "instruments", "model", "templates", "register", "intent", "delivery", "connectors", "mcp", "demo", "jobs-events", "runs", "mode", "memory", "teach", "cycle"]);
  return new Set([...OWN, ...(teachable(r).length ? ["teach"] : []), ...(isHeadOfData(r) ? HEAD_SET : []), ...(isEngineer(r) ? ENGINEER_SET : []), ...(r.includes("approver") ? ["rules"] : [])]);
};
/** Everyone with a company role opens Settings; what is inside depends on the role. */
export const canSettings = (roles: readonly string[] | undefined): boolean => settingsFor(roles).size > 0;

/** Where this person lands: Action when any role has it, else the first role's own landing. */
export const landingFor = (roles: readonly string[] | undefined): string => {
  if (!(roles ?? []).includes("super_admin")) return "/v3/desk"; // 3.0: everyone with a company role lands on the Desk
  if (centresFor(roles).has("pulse")) return "/centre/action";
  return (roles ?? []).map((r) => ROLE_TABLE[r]?.lands).find(Boolean) ?? "/centre/action";
};
