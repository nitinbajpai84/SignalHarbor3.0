import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Failed, useRead } from "../../board/common";
import { getLogical, getPhysical, type Logical, type LogicalObject, type Physical } from "./api";

/** Where each business object sits in the picture: [column, row]. Only neighbours (side by side or one above the other) get a line; a relation
 * between boxes further apart is listed under "Also connects to" in the side panel, so no line ever crosses a box. An object the pack adds later
 * is placed in the next free cell. Laid out so the most relations are between neighbours (12 of the family office's 17). */
export const LAYOUT: Record<string, [number, number]> = {
  family_member: [0, 0], ownership: [1, 0], entity: [2, 0], bank_account: [3, 0],
  cash_movement: [0, 1], position: [1, 1], portfolio: [2, 1], nav_snapshot: [3, 1],
  commitment: [0, 2], instrument: [1, 2], transaction: [2, 2],
  market_observation: [0, 3], valuation: [1, 3], document: [2, 3],
};
const COLS = 4, W = 210, H = 78, GX = 116, GY = 64, PAD = 8;

export function place(objects: LogicalObject[]): Record<string, [number, number]> {
  const out: Record<string, [number, number]> = {};
  const used = new Set<string>();
  for (const o of objects) { const c = LAYOUT[o.id]; if (c && !used.has(c.join())) { out[o.id] = c; used.add(c.join()); } }
  let i = 0;
  for (const o of objects) {
    if (out[o.id]) continue;
    while (used.has([i % COLS, Math.floor(i / COLS)].join())) i += 1;
    const c: [number, number] = [i % COLS, Math.floor(i / COLS)];
    out[o.id] = c;
    used.add(c.join());
  }
  return out;
}
/** Side by side or one above the other. */
export const neighbours = (a?: [number, number], b?: [number, number]) => !!a && !!b && Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]) === 1;

export interface Rel { from: string; to: string; label: string }
/** The relations drawn (between neighbours) and the rest, which the side panel lists. */
export function split(objects: LogicalObject[], at: Record<string, [number, number]>): { drawn: Rel[]; listed: Rel[] } {
  const all = objects.flatMap((o) => o.relations.map((r) => ({ from: o.id, to: r.to, label: r.label }))).filter((e) => at[e.from] && at[e.to]);
  return { drawn: all.filter((e) => neighbours(at[e.from], at[e.to])), listed: all.filter((e) => !neighbours(at[e.from], at[e.to])) };
}
const wrap = (text: string, n: number): string[] => {
  const lines: string[] = [];
  for (const w of text.split(" ")) {
    const last = lines[lines.length - 1];
    if (last !== undefined && `${last} ${w}`.length <= n) lines[lines.length - 1] = `${last} ${w}`; else lines.push(w);
  }
  return lines.slice(0, 2);
};
const rect = (c: [number, number]) => ({ x: PAD + c[0] * (W + GX), y: PAD + c[1] * (H + GY) });

/** A straight connector in the gap between two neighbours, with its label in that gap: above the line across a column gap, beside it down a row gap. */
function Connector({ a, b, label, hot }: { a: [number, number]; b: [number, number]; label: string; hot: boolean }) {
  const [pa, pb] = [rect(a), rect(b)];
  let line: [number, number, number, number], tx: number, ty: number, anchor: "middle" | "start";
  if (a[1] === b[1]) {  // same row: across the column gap
    const y = pa.y + H / 2, right = b[0] > a[0];
    line = right ? [pa.x + W + 3, y, pb.x - 3, y] : [pa.x - 3, y, pb.x + W + 3, y];
    [tx, ty, anchor] = [(line[0] + line[2]) / 2, y - 7, "middle"];
  } else {  // same column: down the row gap
    const x = pa.x + W / 2, down = b[1] > a[1];
    line = down ? [x, pa.y + H + 3, x, pb.y - 3] : [x, pa.y - 3, x, pb.y + H + 3];
    [tx, ty, anchor] = [x + 8, (line[1] + line[3]) / 2 + 4, "start"];
  }
  return (
    <g className={hot ? "km-edge hot" : "km-edge"}>
      <line x1={line[0]} y1={line[1]} x2={line[2]} y2={line[3]} markerEnd="url(#km-arrow)" />
      <text x={tx} y={ty} textAnchor={anchor}>{label}</text>
    </g>
  );
}

export default function Model({ view, onView, kpi, onKpi }: { view: "logical" | "physical"; onView: (v: "logical" | "physical") => void; kpi: string | null; onKpi: (id: string | null) => void }) {
  return (
    <section className="km" aria-label="Data model">
      <div className="km-head">
        <h2>{view === "logical" ? "Data model · Logical: the business things and how they relate" : "Data model · Physical: bronze, silver, gold"}</h2>
        <div className="kg-pills" role="group" aria-label="Model view">
          {(["logical", "physical"] as const).map((v) => <button key={v} type="button" aria-pressed={view === v} onClick={() => onView(v)}>{v === "logical" ? "Logical" : "Physical"}</button>)}
        </div>
      </div>
      {view === "logical" ? <LogicalView /> : <PhysicalView kpi={kpi} onKpi={onKpi} />}
    </section>
  );
}

function LogicalView() {
  const [got, again] = useRead(getLogical);
  const [sel, setSel] = useState<string | null>(null);
  if (got.state === "loading") return <p className="v3-mute" role="status">Reading the data model</p>;
  if (got.state === "error") return <Failed message={got.message} again={again} />;
  return <Picture m={got.data} sel={sel} onSel={setSel} />;
}

function Picture({ m, sel, onSel }: { m: Logical; sel: string | null; onSel: (id: string) => void }) {
  const at = place(m.objects);
  const cells = Object.values(at);
  const cols = Math.max(...cells.map((c) => c[0]), 0) + 1, rows = Math.max(...cells.map((c) => c[1]), 0) + 1;
  const width = PAD * 2 + cols * W + (cols - 1) * GX, height = PAD * 2 + rows * H + (rows - 1) * GY;
  const cur = m.objects.find((o) => o.id === sel) ?? m.objects.find((o) => o.id === "entity") ?? m.objects[0];
  if (!m.objects.length) return <div className="v3-card"><p>This office has no industry model yet.</p></div>;
  const { drawn, listed } = split(m.objects, at);
  const cell = (id: string): [number, number] => at[id] ?? [0, 0];
  const label = (id: string) => m.objects.find((o) => o.id === id)?.label ?? id;
  const also = cur ? listed.filter((e) => e.from === cur.id || e.to === cur.id).map((e) => `${label(e.from === cur.id ? e.to : e.from)} (${e.from === cur.id ? e.label : `${e.label} it`})`) : [];
  return (
    <div className="ks-body km-body">
      <div className="km-pic">
        <p className="kd-intro">In the office{"’"}s words, no table names. Click a box to see its properties and which KPIs read it; switch to Physical to see the tables behind it.</p>
        <svg viewBox={`0 0 ${width} ${height}`} className="km-svg" role="group" aria-label="Business objects and how they relate">
          <defs><marker id="km-arrow" orient="auto" markerWidth="6" markerHeight="6" refX="5" refY="3"><path d="M0 0 L6 3 L0 6 Z" className="km-head-fill" /></marker></defs>
          {drawn.map((e) => <Connector key={`${e.from}>${e.to}`} a={cell(e.from)} b={cell(e.to)} label={e.label} hot={!!cur && (e.from === cur.id || e.to === cur.id)} />)}
          {m.objects.map((o) => {
            const p = rect(cell(o.id));
            const on = cur?.id === o.id;
            return (
              <g key={o.id} className={on ? "km-box on" : "km-box"} role="button" tabIndex={0} aria-pressed={on} aria-label={`${o.label}: ${o.about}`}
                onClick={() => onSel(o.id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSel(o.id); } }}>
                <rect x={p.x} y={p.y} width={W} height={H} rx="10" />
                <text x={p.x + 12} y={p.y + 24} className="km-name">{o.label}</text>
                {o.count != null && <text x={p.x + W - 12} y={p.y + 24} textAnchor="end" className="km-count">{o.count.toLocaleString("en-GB")}</text>}
                {wrap(o.about, 32).map((l, i) => <text key={i} x={p.x + 12} y={p.y + 46 + i * 15} className="km-about">{l}</text>)}
              </g>
            );
          })}
        </svg>
        <p className="kd-intro">Lines join neighbours only; a box{"’"}s other relations are listed beside the picture when you click it. Every record keeps its receipt to the file it came from. Office rules govern limits and approvals.</p>
      </div>
      {cur && <ObjectPanel o={cur} also={also} />}
    </div>
  );
}

function ObjectPanel({ o, also }: { o: LogicalObject; also: string[] }) {
  return (
    <aside className="ks-detail" aria-label="Detail">
      <p className="ks-kicker">Selected {"·"} Business object</p>
      <h2>{o.label}</h2>
      <p className="ks-line">{o.about}</p>
      <p className="ks-line"><b>Rows today:</b> {o.count != null ? o.count.toLocaleString("en-GB") : "not counted"}</p>
      <p className="ks-line"><b>Kept as:</b> {o.table}</p>
      {o.relations.length > 0 && <p className="ks-line"><b>Connects to:</b> {o.relations.map((r) => `${r.label} ${r.to_label.toLowerCase()}`).join("; ")}</p>}
      {also.length > 0 && <p className="ks-line"><b>Also connects to:</b> {also.join("; ")}</p>}
      <p className="ks-line"><b>Properties:</b></p>
      <ul className="ks-props">{o.properties.map((p) => <li key={p.label}>{p.label}{p.derived ? <span className="v3-mute"> {"·"} worked out: {p.derived}</span> : null}</li>)}</ul>
      <p className="ks-line"><b>KPIs that read it:</b>{o.kpis.length === 0 ? " none yet" : ""}</p>
      {o.kpis.length > 0 && <ul className="ks-props">{o.kpis.map((k) => <li key={k.id}><Link to={`/v3/knowledge/figures/${encodeURIComponent(k.id)}`}>{k.name}</Link><span className="v3-mute"> {"·"} {k.usecases.map((u) => u.title).join(", ")}</span></li>)}</ul>}
    </aside>
  );
}

function usePhysical(kpi: string | null) {
  const [data, setData] = useState<Physical | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true;
    setErr(null);
    getPhysical(kpi ?? undefined).then((d) => { if (live) setData(d); }, (e: unknown) => { if (live) setErr(e instanceof Error && e.message ? e.message : "Something went wrong. Please try again."); });
    return () => { live = false; };
  }, [kpi, n]);
  return { data, err, again: () => setN((x) => x + 1) };
}

const LANE_CAP = 9;

function PhysicalView({ kpi, onKpi }: { kpi: string | null; onKpi: (id: string | null) => void }) {
  const { data: p, err, again } = usePhysical(kpi);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  if (err && !p) return <Failed message={err} again={again} />;
  if (!p) return <p className="v3-mute" role="status">Reading the tables</p>;
  const lit = p.path ? { gold: new Set(p.path.gold), silver: new Set(p.path.silver), bronze: new Set(p.path.bronze) } : null;
  const lane = (key: "bronze" | "silver" | "gold", title: string, sub: string, items: { id: string; label: string; n: string }[]) => {
    const hot = lit ? items.filter((i) => lit[key].has(i.id)) : [];
    const ordered = lit ? [...hot, ...items.filter((i) => !lit[key].has(i.id))] : items;
    const shown = open[key] ? ordered : ordered.slice(0, Math.max(LANE_CAP, hot.length));
    return (
      <div className="kp-lane" role="group" aria-label={title}>
        <p className={`ks-label ${key}`}>{title}</p>
        <p className="v3-mute">{sub}</p>
        {shown.map((i) => <span key={i.id} className={`ks-chip ${key}${lit && !lit[key].has(i.id) ? " dim" : ""}${lit && lit[key].has(i.id) ? " on" : ""}`}><b>{i.label}</b>{i.n ? ` · ${i.n}` : ""}</span>)}
        {ordered.length > shown.length || open[key] ? <button type="button" className="ks-more" onClick={() => setOpen({ ...open, [key]: !open[key] })}>{open[key] ? "Show fewer" : `+ ${ordered.length - shown.length} more`}</button> : null}
      </div>
    );
  };
  const num = (n: number | null) => (n == null ? "" : n.toLocaleString("en-GB"));
  const pk = p.picked;
  return (
    <>
      <div className="km-pick">
        <label>Pick a KPI to light up only its path{" "}
          <select aria-label="KPI" value={kpi ?? ""} onChange={(e) => onKpi(e.target.value || null)}>
            <option value="">All KPIs</option>
            {p.kpis.items.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
          </select>
        </label>
        {err && <span className="v3-err">{err}</span>}
        <span className="v3-mute">Left to right is how data moves. Row counts are live.</span>
      </div>
      <div className="kp-lanes">
        {lane("bronze", "Bronze · as received", `${num(p.bronze.total)} files, each with its receipt`, p.bronze.items.map((b) => ({ id: b.id, label: b.label, n: `${b.rows}${b.kinds ? ` · ${b.kinds}` : ""}` })))}
        <span className="kp-arrow" aria-hidden="true">{"›"}</span>
        {lane("silver", "Silver · the office’s clean model", `${p.silver.total} tables, shared by every use case`, p.silver.items.map((s) => ({ id: s.id, label: s.label, n: num(s.rows) })))}
        <span className="kp-arrow" aria-hidden="true">{"›"}</span>
        {lane("gold", "Gold · ready for a KPI", `${p.gold.total} tables, each built by a recipe or a design`, p.gold.items.map((g) => ({ id: g.id, label: g.label, n: `${num(g.rows)} · ${g.usecase}` })))}
        <span className="kp-arrow" aria-hidden="true">{"›"}</span>
        <div className="kp-lane" role="group" aria-label="KPIs and use">
          <p className="ks-label">KPIs and use</p>
          <p className="v3-mute">{p.kpis.total} KPIs with receipts</p>
          {p.kpis.items.map((k) => <button key={k.id} type="button" className={`ks-chip kpi${pk && pk.id !== k.id ? " dim" : ""}${pk?.id === k.id ? " on" : ""}`} aria-pressed={pk?.id === k.id} onClick={() => onKpi(pk?.id === k.id ? null : k.id)}><b>{k.name}</b></button>)}
          {pk && (
            <div className="kp-use">
              <p><b>Read by:</b> {pk.usecases.map((u) => `${u.title} · ${u.who}`).join("; ")}</p>
              {pk.used_by.length > 0 && <p><b>Shown on:</b> {pk.used_by.map((u) => (u.kind === "signal" ? `signal “${u.sub}”` : u.label.toLowerCase())).join(", ")}</p>}
              <Link to={`/v3/knowledge/figures/${encodeURIComponent(pk.id)}`}>Open the figure page</Link>
            </div>
          )}
        </div>
      </div>
      <p className="km-foot"><b>Bronze</b> never changes once received {"·"} <b>Silver</b> is one model for the whole office; changes need a person to admit them {"·"} <b>Gold</b> belongs to the KPIs that read it {"·"} <Link to="/v3/trust/ontology">What Harbor knows</Link></p>
    </>
  );
}
