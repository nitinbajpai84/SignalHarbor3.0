import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { getCompany } from "../../api/client";
import V3Frame from "../Frame";
import MoreViews from "./k/MoreViews";
import Decisions from "./story/Decisions";
import Domains from "./story/Domains";
import Library from "./story/Library";
import Model from "./story/Model";
import UseCases from "./story/UseCases";
import "./k/knowledge.css";
import "./story/story.css";

type Tab = "usecases" | "domains" | "model" | "decisions" | "library" | "more";
const TABS: [Tab, string][] = [["usecases", "Use cases"], ["domains", "Domains"], ["model", "Data model"], ["decisions", "Decisions and rules"], ["library", "Library"], ["more", "More views"]];
const LINKS: [string, string][] = [["/v3/knowledge/figures", "Figures"], ["/v3/knowledge/skills", "Skills Harbor uses"], ["/v3/knowledge/signals", "What Harbor watches for"], ["/v3/trust/proof", "Runs and proof"], ["/v3/trust/people", "People"], ["/v3/trust/connections", "Connections"]];

/** /v3/knowledge: what this company knows about itself, from its own records only. Five tabs, and the older map views behind "More views".
 * The place is in the address (?tab=, uc, domain, model, kpi) so a link can point at one use case or one KPI's path. */
export default function KnowledgePage() {
  const [sp, setSp] = useSearchParams();
  const [find, setFind] = useState("");
  const [company, setCompany] = useState("the office");
  useEffect(() => { getCompany().then((c) => c.name && setCompany(c.name), () => undefined); }, []);
  const asked = sp.get("tab");
  const tab: Tab = TABS.some(([t]) => t === asked) ? (asked as Tab) : "usecases";
  const set = (changes: Record<string, string | null>) => setSp((prev) => {
    const next = new URLSearchParams(prev);
    for (const [k, v] of Object.entries(changes)) { if (v) next.set(k, v); else next.delete(k); }
    return next;
  }, { replace: false });
  return (
    <V3Frame>
      <main className="v3-main kg-page">
        <h1 className="ks-sr">Knowledge: how {company} works</h1>
        <div className="ks-tabs">
          <div className="kg-pills" role="group" aria-label="Knowledge tabs">
            {TABS.map(([t, l]) => <button key={t} type="button" aria-pressed={tab === t} onClick={() => set({ tab: t })}>{l}</button>)}
          </div>
          {tab === "usecases" && (
            <label className="ks-find">Find <input type="search" aria-label="Find" placeholder="a use case, a KPI, a table, a person" value={find} onChange={(e) => setFind(e.target.value)} /></label>
          )}
        </div>
        {tab === "usecases" && <UseCases find={find} ucId={sp.get("uc")} onPick={(id) => set({ tab: "usecases", uc: id })} />}
        {tab === "domains" && <Domains id={sp.get("domain")} onDomain={(id) => set({ domain: id })} onOpen={(id) => set({ tab: "usecases", uc: id })} />}
        {tab === "model" && <Model view={sp.get("model") === "physical" ? "physical" : "logical"} onView={(v) => set({ model: v === "physical" ? "physical" : null })} kpi={sp.get("kpi")} onKpi={(id) => set({ kpi: id })} />}
        {tab === "decisions" && <Decisions />}
        {tab === "library" && <Library />}
        {tab === "more" && <MoreViews company={company} />}
        <nav className="kg-links" aria-label="More about how Harbor works">
          {LINKS.map(([to, l]) => <Link key={to} to={to}>{l}</Link>)}
        </nav>
      </main>
    </V3Frame>
  );
}
