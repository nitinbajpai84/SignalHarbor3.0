import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { getCompany } from "../../api/client";
import V3Frame from "../Frame";
import { Failed, Waiting, useRead } from "../board/common";
import { getKnowledge } from "./k/api";
import Atlas, { AtlasPanel } from "./k/Atlas";
import Graph from "./k/Graph";
import Lineage from "./k/Lineage";
import Matrix from "./k/Matrix";
import Network from "./k/Network";
import { PhoneList, Processes, Side, Things } from "./k/Panels";
import PersonMap from "./k/PersonMap";
import { usePhone } from "./k/usePhone";
import "./k/knowledge.css";

type View = "map" | "processes" | "things";
const VIEWS: [View, string][] = [["map", "Map"], ["processes", "Processes"], ["things", "Things we track"]];
type MapView = "atlas" | "network" | "lineage" | "person" | "matrix" | "columns" | "list";
const MAP_VIEWS: [MapView, string, boolean][] = [["atlas", "Atlas", true], ["network", "Network", false], ["lineage", "Lineage flow", false], ["person", "Around a person", true], ["matrix", "People and figures", false], ["columns", "Columns", false], ["list", "List", true]];
const ICON = { expand: "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5", collapse: "M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5", full: "M3 5h18v14H3zM8 9h8v6H8z" };
const Icon = ({ d }: { d: string }) => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>;
const LINKS: [string, string][] = [["/v3/knowledge/figures", "Figures"], ["/v3/knowledge/skills", "Skills Harbor uses"], ["/v3/knowledge/signals", "What Harbor watches for"], ["/v3/trust/proof", "Runs and proof"], ["/v3/trust/people", "People"], ["/v3/trust/connections", "Connections"]];

/** /v3/knowledge: what this company knows about itself, from its own records only. */
export default function KnowledgePage() {
  const [got, again] = useRead(getKnowledge);
  const [view, setView] = useState<View>("map");
  const [mv, setMv] = useState<MapView>("atlas");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  const [company, setCompany] = useState("the office");
  useEffect(() => { getCompany().then((c) => c.name && setCompany(c.name), () => undefined); }, []);
  const [big, setBig] = useState(false);  // the map expanded over the whole window; the same elements stay mounted, so view, selection and zoom carry over
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!big) return undefined;
    const was = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape" && !document.fullscreenElement) setBig(false); };
    document.addEventListener("keydown", esc);
    return () => {
      document.body.style.overflow = was;
      document.removeEventListener("keydown", esc);
      if (document.fullscreenElement) document.exitFullscreen?.().catch(() => undefined);
    };
  }, [big]);
  const full = () => { box.current?.requestFullscreen?.().catch(() => undefined); };  // optional: a refusal leaves the expanded layer as it is
  const phone = usePhone();
  const k = got.state === "ready" ? got.data : null;
  const mapView: MapView = phone && !MAP_VIEWS.some(([v, , p]) => v === mv && p) ? "atlas" : mv;
  const node = k?.nodes.find((n) => n.id === sel) ?? null;
  return (
    <V3Frame>
      <main className="v3-main kg-page">
        <div className="kg-head">
          <div>
            <span className="v3-mute">Knowledge</span>
            <h1>How {company} works</h1>
            <p className="v3-mute">Only this company: its people, entities, funds, files, figures, signals, rules and decisions, and how they connect.</p>
          </div>
          <div className="kg-tools">
            <div className="kg-pills" role="group" aria-label="Knowledge views">
              {VIEWS.map(([v, l]) => <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)}>{l}</button>)}
            </div>
            {!big && <input className="kg-search" type="search" aria-label="Search knowledge" placeholder="Search anything: a person, a fund, a figure, a file" value={q} onChange={(e) => setQ(e.target.value)} />}
          </div>
        </div>
        {got.state === "loading" && <Waiting what="Reading what the office knows" />}
        {got.state === "error" && <Failed message={got.message} again={again} />}
        {k && k.empty && <div className="v3-card"><p>Nothing to show yet. Once a use case is started and its brief is signed, its sources, figures and decisions appear here.</p></div>}
        {k && !k.empty && (
          <div ref={box} className={big ? "kg-body kg-big" : "kg-body"} role={big ? "dialog" : undefined} aria-modal={big || undefined} aria-label={big ? "Knowledge map, expanded" : undefined}>
            <div className="kg-main">
              {view === "map" && (
                <>
                  <div className="kg-maptools">
                    <div className="kg-pills kg-sub" role="group" aria-label="Map views">
                      {MAP_VIEWS.filter(([, , p]) => !phone || p).map(([v, l]) => <button key={v} type="button" aria-pressed={mapView === v} onClick={() => setMv(v)}>{l}</button>)}
                    </div>
                    {big && <input className="kg-search" type="search" aria-label="Search knowledge" placeholder="Search the map" value={q} onChange={(e) => setQ(e.target.value)} />}
                    <span className="kg-sizers">
                      {big && typeof document.documentElement.requestFullscreen === "function" && <button type="button" className="kg-expand" onClick={full}><Icon d={ICON.full} />Full screen</button>}
                      <button type="button" className="kg-expand" aria-label={big ? "Collapse map" : "Expand map"} aria-pressed={big} onClick={() => setBig((b) => !b)}><Icon d={big ? ICON.collapse : ICON.expand} />{big ? "Collapse map" : "Expand map"}</button>
                    </span>
                  </div>
                  {mapView === "atlas" && <div className="v3-card"><Atlas nodes={k.nodes} edges={k.edges} company={company} query={q} selected={sel} phone={phone} onSelect={setSel} /></div>}
                  {mapView === "network" && <div className="v3-card"><Network nodes={k.nodes} edges={k.edges} query={q} selected={sel} onSelect={setSel} /></div>}
                  {mapView === "lineage" && <div className="v3-card"><Lineage nodes={k.nodes} edges={k.edges} selected={sel} onSelect={setSel} /></div>}
                  {mapView === "person" && <div className="v3-card"><PersonMap nodes={k.nodes} edges={k.edges} selected={sel} onSelect={setSel} /></div>}
                  {mapView === "matrix" && <div className="v3-card"><Matrix nodes={k.nodes} edges={k.edges} selected={sel} onSelect={setSel} /></div>}
                  {mapView === "columns" && <div className="v3-card"><Graph nodes={k.nodes} edges={k.edges} query={q} selected={sel} onSelect={setSel} /></div>}
                  {mapView === "list" && <PhoneList nodes={k.nodes} query={q} selected={sel} onSelect={setSel} />}
                  {phone && mapView !== "list" && node && <AtlasPanel node={node} nodes={k.nodes} edges={k.edges} onSelect={setSel} />}
                </>)}
              {view === "processes" && <Processes items={k.processes} />}
              {view === "things" && <Things items={k.things} />}
            </div>
            {view === "map" && !phone && mapView !== "list" && (mapView === "atlas" ? <AtlasPanel node={node} nodes={k.nodes} edges={k.edges} onSelect={setSel} /> : <Side node={node} nodes={k.nodes} edges={k.edges} onSelect={setSel} />)}
          </div>
        )}
        <nav className="kg-links" aria-label="More about how Harbor works">
          {LINKS.map(([to, l]) => <Link key={to} to={to}>{l}</Link>)}
        </nav>
      </main>
    </V3Frame>
  );
}
