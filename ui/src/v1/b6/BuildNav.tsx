import { Link } from "react-router-dom";

import { canOps } from "../../shell/roles";
import { useSessionIfAny } from "../../useSession";

// Build's sub-navigation: Projects and Operations. Operations is the data engineer's and the administrator's, so everyone else sees no nav at all.
export default function BuildNav({ current }: { current: "projects" | "operations" }) {
  if (!canOps(useSessionIfAny()?.user?.roles)) return null;
  const item = (id: typeof current, to: string, label: string) => (
    <Link className="ds-link" to={to} aria-current={current === id ? "page" : undefined} style={current === id ? { fontWeight: 600, textDecoration: "underline" } : undefined}>{label}</Link>);
  return <nav aria-label="Build" style={{ display: "flex", gap: 18, fontSize: 14, marginBottom: 12 }}>{item("projects", "/centre/build", "Projects")}{item("operations", "/centre/operations", "Operations")}</nav>;
}
