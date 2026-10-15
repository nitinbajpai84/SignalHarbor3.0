import type { ReactNode } from "react";

// E: six richer widget views, plain SVG/CSS (no dependency), colours from the design-system variables so dark theme follows. The data shape of each is
// fixed by b7_studio._view_tile (column aliases): the spec only names the view, so nothing here looks columns up.
type Row = Record<string, unknown>;
const num = (v: unknown) => (typeof v === "number" ? v : typeof v === "string" && v.trim() !== "" && !Number.isNaN(Number(v)) ? Number(v) : null);
const fmt = (n: number) => n.toLocaleString("en-GB", { maximumFractionDigits: 2 });
const text = (v: unknown) => (v === null || v === undefined ? "" : String(v));
const INK = "var(--ds-ink, currentColor)", MUTED = "var(--ds-ink-muted, #888)", LINE = "var(--ds-line-2, #8884)", TEAL = "var(--ds-teal-bright, #2aa)", AMBER = "var(--ds-amber, #d90)", SURF = "var(--ds-surface, #8881)";
const none = <p className="ds-muted">Not available yet</p>;
const nums = (rows: Row[], f: string) => rows.map((r) => num(r[f])).filter((v): v is number => v !== null);
const svg = (label: string, w: number, h: number, body: ReactNode) => <svg role="img" aria-label={label} viewBox={`0 0 ${w} ${h}`} width="100%" style={{ display: "block" }}>{body}</svg>;

/** 103,405,000 -> 103.4m: a headline must fit its box; the exact figure is in the label. */
const short = (v: number) => { const a = Math.abs(v); return a >= 1e9 ? `${(v / 1e9).toFixed(1)}bn` : a >= 1e6 ? `${(v / 1e6).toFixed(1)}m` : a >= 1e4 ? `${(v / 1e3).toFixed(0)}k` : fmt(v); };

/** bullet: rows {name, value, target}; a bar for the value, a tick for the target, teal when the target is met. */
export function Bullet({ rows, label }: { rows: Row[]; label: string }) {
  const r = rows.map((x) => ({ n: text(x.name), v: num(x.value), t: num(x.target) })).filter((x) => x.v !== null);
  if (!r.length) return none;
  // a return can be negative: the scale runs from the lowest to the highest value, with a zero line when zero is inside it
  const all = r.flatMap((x) => [x.v as number, ...(x.t === null ? [] : [x.t])]);
  const lo = Math.min(0, ...all), hi = Math.max(0, ...all), span = hi - lo || 1;
  const pct = all.every((v) => Math.abs(v) < 1.5);  // returns stored as fractions read as percentages
  const show = (v: number) => (pct ? `${(v * 100).toFixed(1)}%` : fmt(v));
  const L = 120, W = 240, row = 34, X = (v: number) => L + ((v - lo) / span) * W;
  return (
    <svg role="group" aria-label={label} viewBox={`0 0 ${L + W + 70} ${r.length * row + 8}`} width="100%" style={{ display: "block" }}>
      {lo < 0 ? <line x1={X(0)} x2={X(0)} y1={0} y2={r.length * row + 8} stroke={INK} strokeOpacity={0.4} /> : null}
      {r.map((x, i) => {
        const y = i * row + 6, v = x.v as number, met = x.t !== null && v >= x.t;
        return (
          <g key={i} role="img" aria-label={`${x.n}: ${show(v)}${x.t === null ? "" : ` against ${show(x.t)}`}`}>
            <text x={L - 8} y={y + 15} fontSize={13} fill={INK} textAnchor="end">{x.n.slice(0, 16)}</text>
            <rect x={L} y={y} width={W} height={22} fill={SURF} />
            <rect x={Math.min(X(0), X(v))} y={y + 6} width={Math.abs(X(v) - X(0))} height={10} fill={met || x.t === null ? TEAL : AMBER} />
            {x.t === null ? null : <line x1={X(x.t)} x2={X(x.t)} y1={y + 1} y2={y + 21} stroke={INK} strokeWidth={3} />}
            <text x={L + W + 6} y={y + 15} fontSize={12} fill={INK}>{show(v)}</text>
          </g>);
      })}
    </svg>);
}

/** waterfall: rows {label, value[, kind]}; kind start|end|total is an absolute bar, anything else a signed step. No end row: a Total is added. */
export function Waterfall({ rows, label }: { rows: Row[]; label: string }) {
  const steps: { n: string; from: number; to: number; abs: boolean }[] = [];
  let run = 0, hasEnd = false;
  for (const r of rows) {
    const v = num(r.value); if (v === null) continue;
    const abs = ["start", "end", "total"].includes(text(r.kind));
    hasEnd ||= text(r.kind) === "end" || text(r.kind) === "total";
    const to = abs ? v : run + v; steps.push({ n: text(r.label), from: abs ? 0 : run, to, abs }); run = to;
  }
  if (!steps.length) return none;
  if (!hasEnd) steps.push({ n: "Total", from: 0, to: run, abs: true });
  const lo = Math.min(0, ...steps.flatMap((s) => [s.from, s.to])), hi = Math.max(0, ...steps.flatMap((s) => [s.from, s.to])), H = 160, bw = 48;
  const y = (v: number) => 8 + ((hi - v) / (hi - lo || 1)) * H;
  return (
    <svg role="group" aria-label={label} viewBox={`0 0 ${steps.length * bw + 8} ${H + 36}`} width="100%" style={{ display: "block" }}>
      <line x1={0} x2={steps.length * bw + 8} y1={y(0)} y2={y(0)} stroke={LINE} />
      {steps.map((s, i) => (
        <g key={i} role="img" aria-label={`${s.n}: ${s.abs ? "" : s.to >= s.from ? "up " : "down "}${fmt(s.abs ? s.to : Math.abs(s.to - s.from))}`}>
          <rect x={i * bw + 6} width={bw - 12} y={y(Math.max(s.from, s.to))} height={Math.max(Math.abs(y(s.from) - y(s.to)), 1)} fill={s.abs ? INK : s.to >= s.from ? TEAL : AMBER} opacity={s.abs ? 0.55 : 1} />
          <text x={i * bw + bw / 2} y={H + 24} fontSize={10} textAnchor="middle" fill={MUTED}>{s.n.slice(0, 8)}</text>
        </g>))}
    </svg>);
}

const path = (pts: [number, number][]) => pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join("");

/** small_multiples: rows {x, grp, value}; one small line per grp, every panel on the same y scale. */
export function SmallMultiples({ rows, label }: { rows: Row[]; label: string }) {
  const by = new Map<string, { x: string; v: number }[]>();
  for (const r of rows) { const v = num(r.value); if (v !== null) by.set(text(r.grp), [...(by.get(text(r.grp)) ?? []), { x: text(r.x), v }]); }
  if (!by.size) return none;
  const all = [...by.values()].flat().map((p) => p.v), lo = Math.min(...all), hi = Math.max(...all), W = 140, H = 60;
  return (
    <div role="group" aria-label={label} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 8 }}>
      {[...by].map(([g, pts]) => {
        const sorted = [...pts].sort((a, b) => a.x.localeCompare(b.x));
        const d = path(sorted.map((p, i): [number, number] => [sorted.length < 2 ? W / 2 : (i / (sorted.length - 1)) * W, 4 + (1 - (p.v - lo) / (hi - lo || 1)) * (H - 8)]));
        return (
          <figure key={g} style={{ margin: 0 }}>
            <figcaption style={{ fontSize: 12, color: MUTED }}>{g} <strong style={{ color: INK }}>{fmt(sorted[sorted.length - 1]!.v)}</strong></figcaption>
            {svg(`${g}: ${sorted.map((p) => fmt(p.v)).join(", ")}`, W, H, <path d={d} fill="none" stroke={TEAL} strokeWidth={2} />)}
          </figure>);
      })}
    </div>);
}

/** calendar: rows {day, value}; the month of the newest day as a Monday-first grid, cell shade = that day's amount. */
export function Calendar({ rows, label }: { rows: Row[]; label: string }) {
  const days = new Map<string, number>();
  for (const r of rows) { const v = num(r.value), d = text(r.day).slice(0, 10); if (v !== null && /^\d{4}-\d{2}-\d{2}$/.test(d)) days.set(d, (days.get(d) ?? 0) + v); }
  if (!days.size) return none;
  const last = [...days.keys()].sort().pop() as string, [y = 0, m = 1] = last.split("-").map(Number);
  const n = new Date(Date.UTC(y, m, 0)).getUTCDate(), lead = (new Date(Date.UTC(y, m - 1, 1)).getUTCDay() + 6) % 7, max = Math.max(...days.values(), 1);
  const title = new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });
  return (
    <div role="group" aria-label={`${label}: ${title}`}>
      <div style={{ fontSize: 12, color: MUTED, marginBottom: 4 }}>{title}</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 2, fontSize: 11 }}>
        {["M", "T", "W", "T", "F", "S", "S"].map((d, i) => <span key={i} aria-hidden style={{ color: MUTED, textAlign: "center" }}>{d}</span>)}
        {Array.from({ length: lead }, (_, i) => <span key={"b" + i} />)}
        {Array.from({ length: n }, (_, i) => {
          const key = `${y}-${String(m).padStart(2, "0")}-${String(i + 1).padStart(2, "0")}`, v = days.get(key);
          return <span key={key} title={`${key}: ${v === undefined ? "none" : fmt(v)}`} aria-label={`${i + 1} ${title}: ${v === undefined ? "nothing" : fmt(v)}`} role="img"
            style={{ textAlign: "center", padding: "4px 0", borderRadius: 3, color: INK, background: v === undefined || v <= 0 ? SURF : `color-mix(in srgb, ${TEAL} ${Math.round(15 + 70 * (v / max))}%, transparent)` }}>{i + 1}</span>;
        })}
      </div>
    </div>);
}

type Box = { n: string; v: number; x: number; y: number; w: number; h: number };
/** Split the list in two halves of near-equal value along the longer side, recursively: a short, stable layout (no squarify). */
function lay(items: { n: string; v: number }[], x: number, y: number, w: number, h: number): Box[] {
  if (items.length === 1) return [{ ...items[0]!, x, y, w, h }];
  const total = items.reduce((a, b) => a + b.v, 0);
  let k = 1, acc = items[0]!.v;
  while (k < items.length - 1 && acc + items[k]!.v <= total / 2) acc += items[k++]!.v;
  const f = acc / total;
  return w >= h ? [...lay(items.slice(0, k), x, y, w * f, h), ...lay(items.slice(k), x + w * f, y, w * (1 - f), h)]
    : [...lay(items.slice(0, k), x, y, w, h * f), ...lay(items.slice(k), x, y + h * f, w, h * (1 - f))];
}

/** treemap: rows {label, value}; box area = value, biggest first, zero and negative values left out. */
export function Treemap({ rows, label }: { rows: Row[]; label: string }) {
  const items = rows.map((r) => ({ n: text(r.label), v: num(r.value) ?? 0 })).filter((r) => r.v > 0).sort((a, b) => b.v - a.v);
  if (!items.length) return none;
  const total = items.reduce((a, b) => a + b.v, 0), W = 400, H = 220;
  return (
    <svg role="group" aria-label={label} viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block" }}>
      {lay(items, 0, 0, W, H).map((b, i) => (
        <g key={i} role="img" aria-label={`${b.n}: ${fmt(b.v)} (${((b.v / total) * 100).toFixed(1)}%)`}>
          <rect x={b.x + 1} y={b.y + 1} width={Math.max(b.w - 2, 0)} height={Math.max(b.h - 2, 0)} fill={TEAL} opacity={0.25 + 0.6 * (b.v / items[0]!.v)} />
          {b.w > 60 && b.h > 28 ? <text x={b.x + 6} y={b.y + 16} fontSize={11} fill={INK}>{b.n.slice(0, Math.floor(b.w / 7))}</text> : null}
        </g>))}
    </svg>);
}

/** kpi_strip: rows oldest first, first column the period, every other number column a headline: newest value, change on the one before, sparkline. */
export function KpiStrip({ rows, label }: { rows: Row[]; label: string }) {
  const [period, ...cols] = Object.keys(rows[0] ?? {});
  const heads = cols.slice(0, 4).map((c) => ({ c, v: nums(rows, c) })).filter((k) => k.v.length);
  if (!period || !heads.length) return none;
  return (
    <div role="group" aria-label={label} style={{ display: "grid", gridTemplateColumns: `repeat(${heads.length}, minmax(0, 1fr))`, gap: 12 }}>
      {heads.map(({ c, v }) => {
        const now = v[v.length - 1]!, diff = v.length > 1 ? now - v[v.length - 2]! : null, lo = Math.min(...v), hi = Math.max(...v);
        const d = path(v.map((p, i): [number, number] => [v.length < 2 ? 40 : (i / (v.length - 1)) * 80, 2 + (1 - (p - lo) / (hi - lo || 1)) * 22]));
        const name = c.replace(/_/g, " ").replace(/^./, (s) => s.toUpperCase());
        return (
          <div key={c} role="img" aria-label={`${name}: ${fmt(now)}${diff === null ? "" : `, ${diff >= 0 ? "up" : "down"} ${fmt(Math.abs(diff))}`}`}>
            <div style={{ fontSize: 12, color: MUTED }}>{name}</div>
            <div style={{ fontSize: 24, fontWeight: 600, lineHeight: 1.1 }}>{short(now)}</div>
            {diff === null ? null : <div style={{ fontSize: 12, color: diff >= 0 ? TEAL : AMBER }}>{diff >= 0 ? "Up" : "Down"} {short(Math.abs(diff))}{now - diff ? ` (${((diff / Math.abs(now - diff)) * 100).toFixed(1)}%)` : ""}</div>}
            {svg("", 80, 26, <path d={d} fill="none" stroke={TEAL} strokeWidth={1.5} />)}
          </div>);
      })}
    </div>);
}

export const VIEWS: Record<string, (p: { rows: Row[]; label: string }) => ReactNode> = {
  bullet: Bullet, waterfall: Waterfall, small_multiples: SmallMultiples, calendar: Calendar, treemap: Treemap, kpi_strip: KpiStrip,
};
