import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Failed, useRead } from "../../board/common";
import { getLogical, getPhysical, type Logical, type LogicalObject, type Physical } from "./api";

/** Where each business object sits in the picture: [column, row]. An object the pack adds later is placed in the next free cell. */
export const LAYOUT: Record<string, [number, number]> = {
  family_member: [0, 0], ownership: [1, 0], entity: [2, 0], bank_account: [3, 0],
  commitment: [0, 1], position: [1, 1], portfolio: [2, 1], nav_snapshot: [3, 1],
  instrument: [0, 2], transaction: [2, 2], cash_movement: [3, 2],
  valuation: [0, 3], document: [1, 3], market_observation: [2, 3],
};
const W = 196, H = 74, GX = 84, GY = 50, PAD = 14;

export function place(objects: LogicalObject[]): Record<string, [number, number]> {
  const out: Record<string, [number, number]> = {};
  const used = new Set<string>();
  for (const o of objects) { const c = LAYOUT[o.id]; if (c) { out[o.id] = c; used.add(c.join()); } }
  let i = 0;
  for (const o of objects) {
    if (out[o.id]) continue;
    while (used.has([i % 4, 3 + Math.floor(i / 4)].join())) i += 1;
    const c: [number, number] = [i % 4, 3 + Math.floor(i / 4)];
    out[o.id] = c;
    used.add(c.join());
  }
  return out;
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
/** Where the line from one box's centre to another's leaves the first box. */
function edgePoint(a: { x: number; y: number }, b: { x: number; y: number }) {
  const [ax, ay, bx, by] = [a.x + W / 2, a.y + H / 2, b.x + W / 2, b.y + H / 2];
  const dx = bx - ax, dy = by - ay;
  const t = Math.min(dx ? (W / 2 + 3) / Math.abs(dx) : Infinity, dy ? (H / 2 + 3) / Math.abs(dy) : Infinity);
  return [ax + dx * t, ay + dy * t] as const;
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
  const rows = Math.max(...Object.values(at).map((c) => c[1]), 0) + 1;
  const pos = (id: string) => rect(at[id] ?? [0, 0]);
  const width = PAD * 2 + 4 * W + 3 * GX, height = PAD * 2 + rows * H + (rows - 1) * GY;
  const cur = m.objects.find((o) => o.id === sel) ?? m.objects.find((o) => o.id === "entity") ?? m.objects[0];
  if (!m.objects.length) return <div className="v3-card"><p>This office has no industry model yet.</p></div>;
  const edges = m.objects.flatMap((o) => o.relations.map((r) => ({ from: o.id, to: r.to, label: r.label }))).filter((e) => at[e.from] && at[e.to]);
  return (
    <div className="ks-body km-body">
      <div className="km-pic">
        <p className="kd-intro">In the office{"’"}s words, no table names. Click a box to see its properties and which KPIs read it; switch to Physical to see the tables behind it.</p>
        <svg viewBox={`0 0 ${width} ${height}`} className="km-svg" role="group" aria-label="Business objects and how they relate">
          <defs><marker id="km-arrow" orient="auto" markerWidth="6" markerHeight="6" refX="3" refY="3"><path d="M0 0 L6 3 L0 6 Z" className="km-head-fill" /></marker></defs>
          {edges.map((e) => {
            const [a, b] = [pos(e.from), pos(e.to)];
            const [x1, y1] = edgePoint(a, b), [x2, y2] = edgePoint(b, a);
            const hot = cur && (e.from === cur.id || e.to === cur.id);
            return (
              <g key={`${e.from}>${e.to}`} className={hot ? "km-edge hot" : "km-edge"}>
                <line x1={x1} y1={y1} x2={x2} y2={y2} markerEnd="url(#km-arrow)" />
                <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 + 4} textAnchor="middle">{e.label}</text>
              </g>
            );
          })}
          {m.objects.map((o) => {
            const p = pos(o.id);
            const on = cur?.id === o.id;
            return (
              <g key={o.id} className={on ? "km-box on" : "km-box"} role="button" tabIndex={0} aria-pressed={on} aria-label={`${o.label}: ${o.about}`}
                onClick={() => onSel(o.id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSel(o.id); } }}>
                <rect x={p.x} y={p.y} width={W} height={H} rx="10" />
                <text x={p.x + 12} y={p.y + 24} className="km-name">{o.label}</text>
                {o.count != null && <text x={p.x + W - 12} y={p.y + 24} textAnchor="end" className="km-count">{o.count.toLocaleString("en-GB")}</text>}
                {wrap(o.about, 30).map((l, i) => <text key={i} x={p.x + 12} y={p.y + 44 + i * 14} className="km-about">{l}</text>)}
              </g>
            );
          })}
        </svg>
        <p className="kd-intro">Every record keeps its receipt to the file it came from. Office rules govern limits and approvals.</p>
      </div>
      {cur && <ObjectPanel o={cur} />}
    </div>
  );
}

function ObjectPanel({ o }: { o: LogicalObject }) {
  return (
    <aside className="ks-detail" aria-label="Detail">
      <p className="ks-kicker">Selected {"·"} Business object</p>
      <h2>{o.label}</h2>
      <p className="ks-line">{o.about}</p>
      <p className="ks-line"><b>Rows today:</b> {o.count != null ? o.count.toLocaleString("en-GB") : "not counted"}</p>
      <p className="ks-line"><b>Kept as:</b> {o.table}</p>
      {o.relations.length > 0 && <p className="ks-line"><b>Connects to:</b> {o.relations.map((r) => `${r.label} ${r.to_label.toLowerCase()}`).join("; ")}</p>}
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
