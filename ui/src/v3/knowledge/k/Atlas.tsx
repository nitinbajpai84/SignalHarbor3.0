import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import type { KEdge, KNode, Kind } from "./api";
import { KIND_LABEL, KIND_ONE, KINDS, KIND_VAR, lines, neighbours, receipt, thingPath } from "./kinds";
import Network from "./Network";

/** The few calls this view makes on 3d-force-graph; the library itself is loaded only when the Atlas opens. */
interface G3 {
  graphData(d: { nodes: A3[]; links: L3[] }): G3; graphData(): { nodes: A3[] }; nodeColor(f: (n: A3) => string): G3; nodeVal(f: (n: A3) => number): G3; nodeLabel(f: (n: A3) => string): G3; nodeOpacity(o: number): G3;
  nodeResolution(r: number): G3; linkColor(f: (l: L3) => string): G3; linkOpacity(o: number): G3; linkWidth(f: (l: L3) => number): G3; linkDirectionalParticles(f: (l: L3) => number): G3;
  linkDirectionalParticleWidth(w: number): G3; onNodeClick(f: (n: A3) => void): G3; onBackgroundClick(f: () => void): G3; backgroundColor(c: string): G3; showNavInfo(b: boolean): G3;
  width(w: number): G3; height(h: number): G3; warmupTicks(n: number): G3; cooldownTicks(n: number): G3; cameraPosition(p: { x: number; y: number; z: number }, look?: { x?: number; y?: number; z?: number }, ms?: number): G3;
  controls(): { autoRotate: boolean; autoRotateSpeed: number; addEventListener(e: string, f: () => void): void }; refresh(): G3; onEngineStop(f: () => void): G3; zoomToFit(ms?: number, pad?: number): G3; _destructor(): void;
}
interface A3 { id: string; kind: Kind; label: string; deg: number; x?: number; y?: number; z?: number }
interface L3 { source: string | A3; target: string | A3; up: string; from: string; to: string }
const endId = (e: string | A3) => (typeof e === "string" ? e : e.id);

interface Props { nodes: KNode[]; edges: KEdge[]; company: string; query: string; selected: string | null; phone: boolean; onSelect: (id: string | null) => void }

/** View 0, the Atlas: every thing the office knows as a dot in a cloud you can spin and zoom; the colour is the kind, a click opens what it rests on and what it feeds. */
export default function Atlas({ nodes, edges, company, query, selected, phone, onSelect }: Props) {
  const [off, setOff] = useState<Set<Kind>>(new Set());
  const [mode, setMode] = useState<"loading" | "3d" | "flat">(phone ? "flat" : "loading");
  const stage = useRef<HTMLDivElement>(null), g = useRef<G3 | null>(null), calmRef = useRef(false), sel = useRef<string | null>(selected), pick = useRef(onSelect), near = useRef<Set<string> | null>(null);
  sel.current = selected; pick.current = onSelect;
  near.current = useMemo(() => (selected ? neighbours(edges, selected) : null), [edges, selected]);
  const shown = useMemo(() => nodes.filter((n) => !off.has(n.kind)), [nodes, off]);
  const data = useMemo(() => {
    const ids = new Set(shown.map((n) => n.id)), deg = new Map<string, number>();
    for (const e of edges) for (const id of [e.from, e.to]) deg.set(id, (deg.get(id) ?? 0) + 1);
    return {
      nodes: shown.map((n): A3 => ({ id: n.id, kind: n.kind, label: n.label, deg: deg.get(n.id) ?? 0 })),
      links: edges.filter((e) => ids.has(e.from) && ids.has(e.to)).map((e): L3 => { const up = e.up ?? e.from; return { source: up, target: up === e.from ? e.to : e.from, up, from: e.from, to: e.to }; }),
    };
  }, [shown, edges]);
  const total = nodes.length, links = edges.length;

  useEffect(() => {
    if (phone || !stage.current) return undefined;
    let dead = false, ro: ResizeObserver | undefined, mm: MediaQueryList | undefined, mo: MutationObserver | undefined, redo: (() => void) | undefined;
    const el = stage.current;
    (async () => {
      try {
        const Force = (await import("3d-force-graph")).default as unknown as new (el: HTMLElement, o: { controlType: string }) => G3;
        if (dead) return;
        const css = (v: string) => getComputedStyle(el).getPropertyValue(v).trim() || "#888";
        const calm = typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        calmRef.current = calm;
        const lit = (id: string) => !near.current || near.current.has(id);
        const graph = new Force(el, { controlType: "orbit" })
          .nodeColor((n) => (lit(n.id) ? css(KIND_VAR[n.kind]) : css("--line-2"))).nodeVal((n) => (n.id === sel.current ? 14 : 1.5 + Math.min(8, n.deg * 0.5))).nodeLabel((n) => `${KIND_ONE[n.kind]}: ${n.label}`)
          .nodeOpacity(0.95).nodeResolution(10).showNavInfo(false).backgroundColor("rgba(0,0,0,0)")
          .linkColor((l) => (sel.current && (l.from === sel.current || l.to === sel.current) ? css("--act") : css("--line-2"))).linkOpacity(0.4)
          .linkWidth((l) => (sel.current && (l.from === sel.current || l.to === sel.current) ? 1.4 : 0.2))
          .linkDirectionalParticles((l) => (!calm && sel.current && (l.from === sel.current || l.to === sel.current) ? 3 : 0)).linkDirectionalParticleWidth(1.6)
          .onNodeClick((n) => pick.current(n.id))  // the camera follows the selection, below
          .onEngineStop(() => { if (!sel.current) graph.zoomToFit(calm ? 0 : 600, 30); }).onBackgroundClick(() => pick.current(null)).warmupTicks(calm ? 120 : 40).cooldownTicks(calm ? 0 : 200);
        const ctl = graph.controls();
        ctl.autoRotate = !calm; ctl.autoRotateSpeed = 0.5;
        ctl.addEventListener("start", () => { ctl.autoRotate = false; });
        const fit = () => graph.width(el.clientWidth).height(el.clientHeight);
        fit();
        if (typeof ResizeObserver !== "undefined") { ro = new ResizeObserver(fit); ro.observe(el); }
        redo = () => graph.refresh();  // a new theme: the colours are read again
        if (typeof window.matchMedia === "function") { mm = window.matchMedia("(prefers-color-scheme: dark)"); mm.addEventListener("change", redo); }
        mo = new MutationObserver(redo); mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "class"] });
        g.current = graph.graphData({ nodes: [], links: [] });
        setMode("3d");
      } catch {  // no WebGL here: the flat network does the same job
        if (!dead) setMode("flat");
      }
    })();
    return () => { dead = true; ro?.disconnect(); mo?.disconnect(); if (mm && redo) mm.removeEventListener("change", redo); g.current?._destructor(); g.current = null; };
  }, [phone]);

  useEffect(() => { if (mode === "3d") g.current?.graphData(JSON.parse(JSON.stringify(data)) as typeof data); }, [mode, data]);
  useEffect(() => {  // whatever picked the figure (a click, the search, the side panel), the camera flies to it; reduced motion jumps there
    const graph = g.current;
    if (mode !== "3d" || !graph) return;
    graph.refresh();
    const ns = graph.graphData().nodes, n = Array.isArray(ns) ? ns.find((d) => d.id === selected) : undefined;
    if (!n || n.x === undefined) return;
    const r = 1 + 110 / Math.max(1, Math.hypot(n.x ?? 0, n.y ?? 0, n.z ?? 0));
    graph.cameraPosition({ x: (n.x ?? 0) * r, y: (n.y ?? 0) * r, z: (n.z ?? 0) * r }, n, calmRef.current ? 0 : 900);
  }, [mode, selected]);

  const q = query.trim().toLowerCase();
  const hits = q ? nodes.filter((n) => n.label.toLowerCase().includes(q)).slice(0, 6) : [];
  return (
    <section className="kg-atlas" aria-label="Atlas">
      <div className="kg-atlas-head">
        <h2>Everything {company} knows</h2>
        <p>{total.toLocaleString("en")} things and {links.toLocaleString("en")} links, each saying what it rests on and why. {phone || mode === "flat" ? "Tap" : "Drag to spin, scroll to zoom, tap"} any dot to see everything it rests on and everything it feeds.</p>
      </div>
      {hits.length > 0 && <ul className="kg-hits" aria-label="Matches">{hits.map((n) => <li key={n.id}><button type="button" onClick={() => onSelect(n.id)}>{KIND_ONE[n.kind]}: {n.label}</button> <Link className="kg-link" to={thingPath(n.id)} aria-label={`Open full page: ${n.label}`}>Open full page</Link></li>)}</ul>}
      <ul className="kg-key kg-toggle" aria-label="Kinds of thing">
        {KINDS.filter((k) => nodes.some((n) => n.kind === k)).map((k) => (
          <li key={k}><button type="button" aria-pressed={!off.has(k)} onClick={() => setOff((o) => { const s = new Set(o); if (!s.delete(k)) s.add(k); return s; })}>
            <i style={{ background: `var(${KIND_VAR[k]})` }} />{KIND_LABEL[k]} <b>{nodes.filter((n) => n.kind === k).length}</b>
          </button></li>))}
      </ul>
      {mode === "flat" ? <Network nodes={shown} edges={edges} query={query} selected={selected} onSelect={onSelect} legend={false} />
        : (
          <div className="kg-3dwrap">
            <div ref={stage} className="kg-3d" role="img" aria-label={`A cloud of ${total} dots, one for each thing ${company} knows`} />
            {mode === "loading" && <p className="v3-mute kg-3d-wait" role="status">Drawing the atlas</p>}
          </div>)}
    </section>
  );
}

/** The panel of a selected dot: what it rests on (upstream) and what it feeds (downstream), each line with the reason for the link and its receipt. */
export function AtlasPanel({ node, nodes, edges, onSelect }: { node: KNode | null; nodes: KNode[]; edges: KEdge[]; onSelect: (id: string) => void }) {
  if (!node) return <aside className="v3-card kg-side" aria-label="Selected"><p className="v3-mute">Tap a dot to see what it rests on, what it feeds, and the receipts.</p></aside>;
  const { rests, feeds } = lines(edges, nodes, node.id);
  const list = (ls: typeof rests, empty: string) => (ls.length
    ? <ul>{ls.map((l, i) => (
      <li key={i}><button type="button" className="kg-link" onClick={() => onSelect(l.node.id)}>{l.node.label}</button> <span className="v3-mute">{l.label}</span>
        {l.why && <><br />{l.why}</>}<br /><span className="v3-mute">{receipt(l.node) || KIND_ONE[l.node.kind]}</span></li>))}</ul>
    : <p className="v3-mute">{empty}</p>);
  return (
    <aside className="v3-card kg-side" aria-label="Selected">
      <span className="kg-kind"><i className="kg-dot" style={{ background: `var(${KIND_VAR[node.kind]})` }} />{KIND_ONE[node.kind]}</span>
      <h2>{node.label}</h2>
      <p><Link className="kg-link" to={thingPath(node.id)}>Open full page</Link></p>
      <p className="v3-mute">Rests on {rests.length} thing{rests.length === 1 ? "" : "s"}</p>
      <h3>Rests on</h3>
      {list(rests, "Nothing is recorded upstream of this.")}
      <h3>Feeds into</h3>
      {list(feeds, "Nothing is recorded downstream of this yet.")}
      <h3>What we know</h3>
      {node.facts.length ? <ul>{node.facts.map((f, i) => <li key={i}>{f.text}<br /><span className="v3-mute">{f.source}{f.at ? `, ${f.at}` : ""}</span></li>)}</ul> : <p className="v3-mute">Nothing recorded yet.</p>}
    </aside>
  );
}
