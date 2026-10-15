import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import ScreenState from "../../components/ScreenState";
import { useLoad } from "../../components/useLoad";
import { Button } from "../../design";
import { getOntology, type OntoNode, type OntoProject, type Ontology } from "./api";
import { day } from "./dates";
import NodeCard from "./NodeCard";
import OntoGraph from "./OntoGraph";
import { GROUPS, matches, visible } from "./onto";
import StepIcon from "../b9/StepIcons";
import type { StepId } from "../b9/steps";

// The ontology view of the Map (MapPage frames it): people, projects, data, definitions, decisions and cases on one graph, full width.
// Solid is verified, dashed is still being worked on. Agents own nothing, so they are left off (filtered here, the data keeps them).
const STEP_ICON: StepId[] = ["intent", "architecture", "pipelines", "dashboards"];
// Meaning (definitions, decisions, cases) starts hidden so the flow from people to dashboards fills the page; the chips bring it back.
const OFF = ["definition", "case", "decision"];
const FIELD = { font: "inherit", padding: "4px 8px", background: "var(--ds-surface)", color: "var(--ds-ink)", border: "1px solid var(--ds-line-2)", borderRadius: 10 } as const;

function Growth({ p, step, setStep, nodes, playing, play }: { p: OntoProject; step: number; setStep: (n: number) => void; nodes: OntoNode[]; playing: boolean; play: () => void }) {
  const cur = p.steps[step - 1] ?? p.steps[0];
  const added = nodes.filter((n) => n.steps[p.id] === step);
  const next = p.steps[step];
  return (
    <div className="ds-card" style={{ padding: 16, display: "grid", gap: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <strong>Show the map as it stood at</strong>
        <Button onClick={play}>{playing ? "Stop" : "Replay the growth"}</Button>
      </div>
      <div role="group" aria-label="Project steps" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 8 }}>
        {p.steps.map((s) => (
          <button key={s.n} type="button" className="ds-card" aria-pressed={step === s.n} disabled={!s.reached} onClick={() => setStep(s.n)}
            style={{ textAlign: "left", padding: 10, font: "inherit", cursor: s.reached ? "pointer" : "default", opacity: s.reached ? 1 : 0.5, outline: step === s.n ? "2px solid var(--ds-teal-bright)" : "none" }}>
            <span style={{ display: "flex", gap: 6, alignItems: "center", color: "var(--ds-teal-bright)" }}><StepIcon step={STEP_ICON[s.n - 1] ?? "intent"} size={16} /> <span className="ds-footnote">{s.n} · {s.name}</span></span>
            <div>{s.label}</div>
            <div className="ds-muted" style={{ fontSize: 13 }}>{s.reached ? `${day(s.at)} · +${s.added} on the map` : "Not reached yet"}</div>
          </button>
        ))}
      </div>
      <div aria-live="polite">
        <strong>Step {step} of 4: {cur?.label}{cur?.at ? `, ${day(cur.at)}` : ""}</strong>
        <p className="ds-muted" style={{ margin: "4px 0" }}>What this step added</p>
        {added.length ? <ul style={{ margin: 0, paddingLeft: 18 }}>{added.map((n) => <li key={n.id}>{n.label} <span className="ds-muted">({n.type_word.toLowerCase()})</span></li>)}</ul>
          : <p className="ds-muted" style={{ margin: 0 }}>Nothing new is drawn at this step.</p>}
        {next ? <p className="ds-muted">Next: {next.label}{next.reached ? `, ${day(next.at)}` : ", not reached yet"}. Faded and dashed items arrive then.</p> : null}
      </div>
    </div>
  );
}

export default function OntologyPage() {
  const nav = useNavigate();
  const [q, setQ] = useSearchParams();
  const { state, data: raw, message, retry } = useLoad<Ontology>(getOntology, "k3-onto", (o) => o.nodes.length === 0);
  const [find, setFind] = useState("");
  const [hidden, setHidden] = useState<Set<string>>(new Set(OFF));
  const [st, setSt] = useState<"all" | "verified" | "in_progress">("all");
  const [step, setStep] = useState(4);
  const [playing, setPlaying] = useState(false);
  const project = q.get("project"), focus = q.get("focus");
  const set = (kv: Record<string, string | null>) => { const n = new URLSearchParams(q); for (const [k, v] of Object.entries(kv)) { if (v === null) n.delete(k); else n.set(k, v); } setQ(n); };
  const data = useMemo(() => {
    if (!raw) return null;
    const nodes = raw.nodes.filter((n) => n.type !== "agent"), ids = new Set(nodes.map((n) => n.id));
    return { ...raw, nodes, edges: raw.edges.filter((e) => ids.has(e.from) && ids.has(e.to)) };
  }, [raw]);
  const proj = data?.projects.find((p) => p.id === project) ?? null;

  useEffect(() => { if (proj) setStep(Math.max(1, proj.steps.filter((s) => s.reached).length)); setPlaying(false); }, [proj?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!playing || !proj) return;
    const reached = proj.steps.filter((s) => s.reached).length;
    const t = setTimeout(() => (step >= reached ? setPlaying(false) : setStep(step + 1)), 1100);
    return () => clearTimeout(t);
  }, [playing, step, proj]);

  const view = useMemo(() => (data ? visible(data, { lens: "all", hidden, state: st, project, q: find }) : { nodes: [], edges: [] }), [data, hidden, st, project, find]);
  const lit = useMemo(() => (data ? matches(data, find) : new Set<string>()), [data, find]);
  const picked = data?.nodes.find((n) => n.id === focus) ?? null;
  const toggle = (id: string) => setHidden((h) => { const n = new Set(h); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const fade = proj ? (n: OntoNode) => (n.steps[proj.id] ?? 0) > step : undefined;
  const verified = data ? data.nodes.filter((n) => n.state === "verified").length : 0;

  return (
    <ScreenState state={state} message={state === "empty" ? "Nothing is on the map yet. It grows as intents are signed and projects are built." : message} onRetry={retry}>
      {data ? (
        <div style={{ display: "grid", gap: 12 }}>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}>Find on the map
              <input type="search" value={find} onChange={(e) => setFind(e.target.value)} style={{ ...FIELD, width: 180 }} />
            </label>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}>One project
              <select value={project ?? ""} onChange={(e) => set({ project: e.target.value || null, focus: null })} style={FIELD}>
                <option value="">All projects</option>
                {data.projects.map((p) => <option key={p.id} value={p.id}>{p.title} ({p.stage_word})</option>)}
              </select>
            </label>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}>State
              <select value={st} onChange={(e) => setSt(e.target.value as typeof st)} style={FIELD}>
                <option value="all">Everything</option><option value="verified">Verified</option><option value="in_progress">In progress</option>
              </select>
            </label>
            <span className="ds-muted">{verified} verified · {data.nodes.length - verified} in progress</span>
          </div>
          <div role="group" aria-label="Show" style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
            <span className="ds-footnote">SHOW</span>
            {GROUPS.map((g) => { const n = data.nodes.filter((x) => g.types.includes(x.type)).length; return n ? (
              <button key={g.id} type="button" className="ds-chip" aria-pressed={!hidden.has(g.id)} onClick={() => toggle(g.id)}
                style={{ padding: "2px 10px", fontSize: 12, background: "transparent", opacity: hidden.has(g.id) ? 0.55 : 1, borderColor: hidden.has(g.id) ? undefined : "var(--ds-teal-bright)" }}>{g.label} {n}</button>) : null; })}
          </div>
          {proj ? <>
            <h2 style={{ margin: 0, fontSize: 18 }}>How {proj.title} grew the map</h2>
            <Growth p={proj} step={step} setStep={(n) => { setPlaying(false); setStep(n); }} nodes={data.nodes} playing={playing} play={() => { if (!playing && step >= proj.steps.filter((s) => s.reached).length) setStep(1); setPlaying(!playing); }} />
          </> : null}
          <div style={{ position: "relative", minWidth: 0 }}>
            {view.nodes.length === 0 ? <p className="ds-muted">Nothing matches these choices. Show more kinds of item, or clear the state or project choice.</p>
              : <OntoGraph nodes={view.nodes} edges={view.edges} columns={data.columns} selected={focus} onSelect={(id) => set({ focus: id })} lit={lit} fade={fade} company />}
            {picked ? (
              <aside aria-label="Selected" className="ds-card" style={{ position: "absolute", top: 8, right: 8, zIndex: 2, width: "min(360px, 92%)", maxHeight: "70vh", overflow: "auto", padding: 8, boxShadow: "0 8px 24px rgba(0,0,0,.4)" }}>
                <div style={{ textAlign: "right" }}><Button onClick={() => set({ focus: null })}>Close</Button></div>
                <NodeCard node={picked} o={data} edges={data.edges} onGo={(id) => set({ focus: id })} onReview={data.team ? () => nav("/centre/map/review") : undefined} />
              </aside>) : null}
          </div>
          <p className="ds-footnote" style={{ margin: 0 }}>How things relate: owns (accountable for it) · feeds (data moves on) · defined by (its signed meaning) · decided in (where it was chosen) · raised from (what it came out of) · built by (who made it). Choose anything on the map to see what it is.</p>
        </div>
      ) : null}
    </ScreenState>
  );
}
