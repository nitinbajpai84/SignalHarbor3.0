import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import V3Frame from "../Frame";
import { Failed, Waiting } from "../board/common";
import { getThing, type Hop, type KEdge, type KNode, type Kind, type Thing1 } from "./k/api";
import { look } from "./k/Graph";
import { KIND_LABEL, KIND_ONE, KINDS, kindColour, thingPath } from "./k/kinds";
import "./k/knowledge.css";

const SHOW = 10, COL_MAX = 12, CW = 170, GAP = 64, NH = 28, NG = 8, TOP = 26, PAD = 10;
const cut = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + "…" : s);
const lower = (s: string) => s.toLowerCase();
const STATUS: Record<string, string> = { verified: "Checked", held: "Held back", draft: "Draft" };

/** The thing's own detail page, if it has one: a figure with a record, a use case thread, a signal, a person. */
function detail(n: KNode): [string, string] | null {
  const key = n.id.slice(n.id.indexOf(":") + 1);
  if (n.kind === "figure" && n.versions) return [`/v3/knowledge/figures/fig-${key}`, "Open the figure page"];
  if (n.kind === "usecase" && n.stage && n.stage !== "suggested" && key.startsWith("th-")) return [`/v3/thread/${key}`, "Open the use case thread"];
  if (n.kind === "signal") return ["/v3/knowledge/signals", "See the signals Harbor watches"];
  if (n.kind === "person") return ["/v3/trust/people", "See the people"];
  return null;
}

/** "3 figures, 2 signals and 4 people", counted over the downstream chain. */
export function impact(feeds: Hop[]): string {
  const parts = KINDS.map((k) => [k, feeds.filter((h) => h.kind === k).length] as const).filter(([, c]) => c).map(([k, c]) => `${c} ${lower(c === 1 ? KIND_ONE[k] : KIND_LABEL[k])}`);
  if (!parts.length) return "Nothing depends on this yet.";
  return `If this changes, ${parts.length > 1 ? parts.slice(0, -1).join(", ") + " and " + parts[parts.length - 1] : parts[0]} ${feeds.length === 1 ? "is" : "are"} affected.`;
}

/** Left to right by hop: what it rests on on the left, the thing in the middle, what it feeds on the right. */
export function layoutHops(nodes: (KNode & { hop: number })[]) {
  const hops = [...new Set(nodes.map((n) => n.hop))].sort((a, b) => a - b);
  const cols = hops.map((h, c) => {
    const all = nodes.filter((n) => n.hop === h).sort((a, b) => a.label.localeCompare(b.label)), shown = all.slice(0, COL_MAX);
    return { hop: h, x: PAD + c * (CW + GAP), nodes: shown, more: all.length - shown.length };
  });
  const tall = Math.max(...cols.map((c) => c.nodes.length + (c.more ? 1 : 0)), 1);
  const pos = new Map<string, { x: number; y: number }>();
  for (const c of cols) c.nodes.forEach((n, i) => pos.set(n.id, { x: c.x, y: TOP + i * (NH + NG) }));
  return { cols, pos, w: PAD * 2 + cols.length * CW + (cols.length - 1) * GAP, h: TOP + tall * (NH + NG) + PAD };
}

const heading = (h: number) => (h === 0 ? "This thing" : h === -1 ? "Rests on" : h === 1 ? "Feeds into" : h < 0 ? `${-h} steps up` : `${h} steps down`);

function FocusMap({ t, onOpen }: { t: Thing1; onOpen: (id: string) => void }) {
  const lay = useMemo(() => layoutHops(t.nodes), [t.nodes]);
  const [said, setSaid] = useState("");
  const by = new Map(t.nodes.map((n) => [n.id, n]));
  const reason = (e: KEdge) => `${by.get(e.from)?.label} ${e.label} ${by.get(e.to)?.label}${e.why ? `: ${e.why}` : ""}`;
  return (
    <div>
      <div className="kg-scroll">
        <svg width="100%" style={{ maxWidth: lay.w, height: "auto" }} viewBox={`0 0 ${lay.w} ${lay.h}`} role="group" aria-label="Map of this thing and its neighbours" className="kg-flow">
          {lay.cols.map((c) => <text key={c.hop} x={c.x} y={14} fontSize="12" className="kg-cluster">{heading(c.hop)}</text>)}
          {t.edges.map((e, i) => {
            const a = lay.pos.get(e.from), b = lay.pos.get(e.to);
            if (!a || !b) return null;
            const [l, r] = (e.up ?? e.from) === e.from ? [a, b] : [b, a];  // the upstream end is the left one
            const x1 = l.x + CW, x2 = r.x, mx = (x1 + x2) / 2, y1 = l.y + NH / 2, y2 = r.y + NH / 2;
            return (
              <path key={i} d={`M${x1} ${y1}C${mx} ${y1} ${mx} ${y2} ${x2} ${y2}`} fill="none" strokeWidth={3} opacity={0.45} style={{ stroke: "var(--info)", cursor: "pointer" }} tabIndex={0} role="button" aria-label={`Link: ${reason(e)}`}
                onClick={() => setSaid(reason(e))} onKeyDown={(ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); setSaid(reason(e)); } }}><title>{reason(e)}</title></path>);
          })}
          {lay.cols.flatMap((c) => c.nodes).map((n) => {
            const p = lay.pos.get(n.id) as { x: number; y: number }, mid = n.hop === 0, lk = look(n);
            return (
              <g key={n.id} tabIndex={mid ? undefined : 0} role={mid ? "img" : "button"} aria-label={`${KIND_ONE[n.kind]}: ${n.label}`} style={{ cursor: mid ? "default" : "pointer" }}
                onClick={() => !mid && onOpen(n.id)} onKeyDown={(e) => { if (!mid && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onOpen(n.id); } }}>
                <rect x={p.x} y={p.y} width={CW} height={NH} rx={6} style={{ fill: mid ? "var(--harbor-soft)" : lk.fill, stroke: mid ? "var(--act)" : kindColour(n.kind) }} strokeWidth={mid ? 3 : 1.4} />
                <text x={p.x + 8} y={p.y + NH / 2 + 4} fontSize="12" style={{ fill: "var(--ink)" }}>{cut(n.label, 24)}</text>
                <title>{`${KIND_ONE[n.kind]}: ${n.label}`}</title>
              </g>);
          })}
          {lay.cols.filter((c) => c.more).map((c) => <text key={`m${c.hop}`} x={c.x + 6} y={TOP + c.nodes.length * (NH + NG) + 12} fontSize="11" style={{ fill: "var(--mute)" }}>+{c.more} more, listed below</text>)}
        </svg>
      </div>
      <p className="v3-mute tp-said" role="status">{said || "Hover or tap a line to see why the two are linked. Tap a box to centre the page on it."}</p>
    </div>
  );
}

function Chain({ title, items, empty }: { title: string; items: Hop[]; empty: string }) {
  const [more, setMore] = useState<ReadonlySet<Kind>>(new Set());
  const groups = KINDS.map((k) => [k, items.filter((h) => h.kind === k)] as const).filter(([, hs]) => hs.length);
  return (
    <section className="v3-card tp-chain" aria-label={title}>
      <h2>{title} <span className="v3-mute">{items.length}</span></h2>
      {!groups.length && <p className="v3-mute">{empty}</p>}
      {groups.map(([k, hs]) => {
        const open = more.has(k);
        return (
          <div key={k} className="tp-group">
            <h3>{KIND_LABEL[k]} <span>{hs.length}</span></h3>
            <ul>{(open ? hs : hs.slice(0, SHOW)).map((h) => <li key={h.id}><Link className="kg-link" to={thingPath(h.id)}>{h.label}</Link></li>)}</ul>
            {hs.length > SHOW && <button type="button" className="kg-link" onClick={() => setMore((s) => { const n = new Set(s); if (!n.delete(k)) n.add(k); return n; })}>{open ? "Show fewer" : `+${hs.length - SHOW} more`}</button>}
          </div>);
      })}
    </section>
  );
}

type Got = { state: "loading" } | { state: "error"; message: string } | { state: "ready"; data: Thing1 };

function Thing({ id }: { id: string }) {
  const nav = useNavigate();
  const [up, setUp] = useState(1), [down, setDown] = useState(1), [again, setAgain] = useState(0), [allFacts, setAllFacts] = useState(false);
  const [got, setGot] = useState<Got>({ state: "loading" });
  useEffect(() => {
    let live = true;
    getThing(id, up, down).then((data) => live && setGot({ state: "ready", data }), (e: unknown) => live && setGot({ state: "error", message: e instanceof Error && e.message ? e.message : "Something went wrong. Please try again." }));
    return () => { live = false; };
  }, [id, up, down, again]);
  const t = got.state === "ready" ? got.data : null, node = t?.node, d = node ? detail(node) : null;
  const tag = node ? look(node).tag ?? STATUS[node.status ?? ""] : undefined;
  const steps = (side: string, v: number, set: (n: number) => void, max: number) => (
    <>
      {v < max && <button type="button" onClick={() => set(v + 1)}>Show one more step {side}</button>}
      {v > 1 && <button type="button" onClick={() => set(1)}>Back to one step {side}</button>}
    </>);
  return (
    <V3Frame>
      <main className="v3-main kg-page tp-page">
        <nav aria-label="Back"><Link to="/v3/knowledge" className="kg-link">Knowledge</Link></nav>
        {got.state === "error" && <Failed message={got.message} again={() => setAgain((x) => x + 1)} />}
        {got.state === "loading" && <Waiting what="Reading this thing" />}
        {t && node && (
          <>
            <header className="tp-head">
              <span className="kg-kind"><i className="kg-dot" style={{ background: kindColour(node.kind) }} />{KIND_ONE[node.kind]}{tag && <span className="v3-pill kg-tag">{tag}</span>}</span>
              <h1>{node.label} · {lower(KIND_ONE[node.kind])}</h1>
              {d && <p><Link to={d[0]} className="kg-link">{d[1]}</Link></p>}
              <h2 className="tp-h">What we know</h2>
              {node.facts.length ? <ul className="tp-facts">{node.facts.slice(0, allFacts ? undefined : 6).map((f, i) => <li key={i}>{f.text}<br /><span className="v3-mute">{f.source}{f.at ? `, ${f.at}` : ""}</span></li>)}</ul> : <p className="v3-mute">Nothing recorded yet.</p>}
              {node.facts.length > 6 && <button type="button" className="kg-link tp-morefacts" onClick={() => setAllFacts((x) => !x)}>{allFacts ? "Show fewer facts" : `+${node.facts.length - 6} more facts`}</button>}
              <p className="tp-impact" role="status">{impact(t.feeds)}</p>
            </header>
            <div className="tp-body">
              <section className="v3-card tp-map" aria-label="Focused map">
                <h2>Its neighbours</h2>
                <div className="tp-tools">{steps("upstream", up, setUp, t.up_steps)}{steps("downstream", down, setDown, t.down_steps)}</div>
                <FocusMap t={t} onOpen={(to) => nav(thingPath(to))} />
              </section>
              <div className="tp-lists">
                <Chain title="Everything it rests on" items={t.rests_on} empty="Nothing is recorded upstream of this." />
                <Chain title="Everything that depends on it" items={t.feeds} empty="Nothing is recorded downstream of this yet." />
              </div>
            </div>
          </>)}
      </main>
    </V3Frame>
  );
}

/** /v3/knowledge/thing/:id: one thing from the Knowledge map, its facts, its neighbours hop by hop and the whole chain each way. */
export default function ThingPage() {
  const { id = "" } = useParams();
  return <Thing key={id} id={id} />;
}
