import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getCompany } from "../../api/client";
import V3Frame from "../Frame";
import { Failed, Waiting, useRead } from "../board/common";
import { getKnowledge } from "./k/api";
import Graph from "./k/Graph";
import { PhoneList, Processes, Side, Things } from "./k/Panels";
import { usePhone } from "./k/usePhone";
import "./k/knowledge.css";

type View = "map" | "processes" | "things";
const VIEWS: [View, string][] = [["map", "Map"], ["processes", "Processes"], ["things", "Things we track"]];
const LINKS: [string, string][] = [["/v3/knowledge/figures", "Figures"], ["/v3/knowledge/skills", "Skills Harbor uses"], ["/v3/knowledge/signals", "What Harbor watches for"], ["/v3/trust/proof", "Runs and proof"], ["/v3/trust/people", "People"], ["/v3/trust/connections", "Connections"]];

/** /v3/knowledge: what this company knows about itself, from its own records only. */
export default function KnowledgePage() {
  const [got, again] = useRead(getKnowledge);
  const [view, setView] = useState<View>("map");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  const [company, setCompany] = useState("the office");
  useEffect(() => { getCompany().then((c) => c.name && setCompany(c.name), () => undefined); }, []);
  const phone = usePhone();
  const k = got.state === "ready" ? got.data : null;
  return (
    <V3Frame>
      <main className="v3-main kg-page">
        <div className="kg-head">
          <div>
            <span className="v3-mute">Knowledge</span>
            <h1>How {company} works</h1>
            <p className="v3-mute">Only this company: its people, entities, funds, files, figures and decisions, and how they connect.</p>
          </div>
          <div className="kg-tools">
            <div className="kg-pills" role="group" aria-label="Knowledge views">
              {VIEWS.map(([v, l]) => <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)}>{l}</button>)}
            </div>
            <input className="kg-search" type="search" aria-label="Search knowledge" placeholder="Search anything: a person, a fund, a figure, a file" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
        </div>
        {got.state === "loading" && <Waiting what="Reading what the office knows" />}
        {got.state === "error" && <Failed message={got.message} again={again} />}
        {k && k.empty && <div className="v3-card"><p>Nothing to show yet. Once a use case is started and its brief is signed, its sources, figures and decisions appear here.</p></div>}
        {k && !k.empty && (
          <div className="kg-body">
            <div className="kg-main">
              {view === "map" && (phone ? <PhoneList nodes={k.nodes} query={q} selected={sel} onSelect={setSel} />
                : <div className="v3-card"><Graph nodes={k.nodes} edges={k.edges} query={q} selected={sel} onSelect={setSel} /></div>)}
              {view === "processes" && <Processes items={k.processes} />}
              {view === "things" && <Things items={k.things} />}
            </div>
            {view === "map" && !phone && <Side node={k.nodes.find((n) => n.id === sel) ?? null} nodes={k.nodes} edges={k.edges} onSelect={setSel} />}
          </div>
        )}
        <nav className="kg-links" aria-label="More about how Harbor works">
          {LINKS.map(([to, l]) => <Link key={to} to={to}>{l}</Link>)}
        </nav>
      </main>
    </V3Frame>
  );
}
