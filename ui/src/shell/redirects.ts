// Old entry paths and their new homes (9 Oct, four centres). Pure: a path in, the new place (or null) out.
// CentreShell applies it, so it wins over any route another card still registers at the old path.
const SECTION: Record<string, string> = { agents: "templates", model: "model", rules: "rules" };

// Intent is step 1 of Build (V5). /centre/intent and /centre/intent/<one id> move into Build; the other Intent pages keep their paths.
const INTENT_PAGES = new Set(["new", "bring", "outcomes", "past", "backlog", "admin", "graph", "map", "baseline", "charter", "wall", "define", "truth"]);

export function redirectFor(pathname: string): string | null {
  const parts = pathname.replace(/\/+$/, "").split("/"); // "", "centre", a, b, c
  const [, root, a, b] = parts;
  if (root !== "centre" || !a) return null;
  if (a === "intent" && parts.length === 3) return "/centre/build/new";
  if (a === "intent" && parts.length === 4 && b && !INTENT_PAGES.has(b)) return `/centre/build/intent/${encodeURIComponent(b)}`;
  if (a === "today" || a === "pulse" || a === "home") return "/centre/action";
  if (a === "desk") return b ? `/centre/action/cases/${encodeURIComponent(b)}` : "/centre/action/cases";
  if (a === "evidence") return b ? `/centre/action/evidence/${encodeURIComponent(b)}` : "/centre/action/evidence";
  if (a === "admin") return b && SECTION[b] ? `/centre/settings/${SECTION[b]}` : "/centre/settings";
  if (a === "register") return "/centre/settings/register";
  if (a === "memory") return "/centre/settings/memory";
  return null;
}
