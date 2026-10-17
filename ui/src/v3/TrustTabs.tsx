import { NavLink } from "react-router-dom";

const TABS: [string, string][] = [
  ["ontology", "What Harbor knows"], ["model", "Industry model"], ["language", "Language"], ["people", "People"],
  ["proof", "Runs and proof"], ["workbench", "Workbench"], ["connections", "Connections"],
];

/** Sub-tabs under Trust; each Trust page renders this above its content. */
export default function TrustTabs() {
  return (
    <nav className="v3-tabs" aria-label="Trust">
      {TABS.map(([p, label]) => <NavLink key={p} to={`/v3/trust/${p}`}>{label}</NavLink>)}
    </nav>
  );
}
