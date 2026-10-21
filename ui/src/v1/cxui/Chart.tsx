import embed from "vega-embed";
import { useEffect, useRef, useState } from "react";

import type { TileData } from "./api";
import { VIEWS } from "./ChartKinds";
import { fmt1, fmtValue, pct1 } from "./fmt";

// C2: one tile's chart. The program sends a Vega-Lite spec and the rows; the spec is data, never code we run (no actions menu,
// vega's safe expression interpreter). DS1: three widget views are drawn here, not by Vega: a figure (one number and how it moved),
// a table and a status list; the spec says which in usermeta.view.
type Row = Record<string, unknown>;
const head = (c: string) => c.replace(/_/g, " ").replace(/^./, (m) => m.toUpperCase());
const num = (v: unknown) => (typeof v === "number" ? v : typeof v === "string" && v.trim() !== "" && !Number.isNaN(Number(v)) ? Number(v) : null);
const fmt = fmt1;
const show = (v: unknown) => (v === null || v === undefined || v === "" ? "Not available yet" : fmtValue(v));

/** A return, rate or yield stored as a fraction (0.0103): shown as a percentage, and its move in percentage points, never a percent of a percent. */
const RATE = /\b(return|rate|yield|margin|ratio|growth|share|percent)/i;
export const asRate = (n: number) => pct1(n * 100); // dashboards show one decimal everywhere

/** A Vega-Lite spec whose rate-like quantitative fields hold fractions: axis, legend and tooltip show them as percent (0.28 as 28.00%). */
type Enc = Record<string, Record<string, unknown>>;

/** A tile is small, so the chart follows the chart books (Wong, Few): bars with long category names lie flat (names read left to right and the bars
 *  use the width), the legend is one slim row on top, value axes use short numbers (2.3M), and an axis title that only repeats the field is dropped.
 *  The person's own settings (an explicit axis or legend in the spec) win. */
export function polish(spec: Record<string, unknown>, rows: Row[]): Record<string, unknown> {
  const mark = spec.mark as string | { type?: string } | undefined;
  const kind = typeof mark === "string" ? mark : mark?.type;
  const enc = { ...((spec.encoding ?? {}) as Enc) };
  if (!enc.x || !enc.y) return spec;
  const names = (f: unknown) => rows.map((r) => String(r[f as string] ?? ""));
  const longest = (f: unknown) => Math.max(0, ...names(f).map((s) => s.length));
  const many = (f: unknown) => new Set(names(f)).size;
  let x = { ...enc.x }, y = { ...enc.y };
  if (kind === "bar" && x.type === "nominal" && y.type === "quantitative" && (longest(x.field) > 6 || many(x.field) > 6)) {
    [x, y] = [y, x];  // horizontal bars
    if (enc.xOffset) { enc.yOffset = enc.xOffset; delete enc.xOffset; }
    y.sort = "-x";
  }
  const quiet = { title: null };
  const valueAxis = { format: "~s", tickCount: 4, labelFlush: true };
  const catAxis = { labelAngle: 0, labelLimit: 160, labelPadding: 4 };
  x.axis = { ...(x.type === "quantitative" ? valueAxis : x.type === "temporal" ? { labelAngle: 0, format: "%b %y", tickCount: 6 } : catAxis), ...quiet, ...((enc.x.axis as object) ?? {}) };
  y.axis = { ...(y.type === "quantitative" ? valueAxis : catAxis), ...quiet, ...((enc.y.axis as object) ?? {}) };
  enc.x = x; enc.y = y;
  if (enc.color) enc.color = { ...enc.color, legend: { orient: "top", direction: "horizontal", title: null, labelFontSize: 11, symbolSize: 60, columnPadding: 16, ...((enc.color.legend as object) ?? {}) } };
  return { ...spec, encoding: enc };
}

export function rateSpec(spec: Record<string, unknown>, rows: Row[]): Record<string, unknown> {
  const enc = (spec.encoding ?? {}) as Record<string, Record<string, unknown>>;
  const isRate = (d: Record<string, unknown>) => {
    const f = d?.field as string | undefined;
    const vals = f ? rows.map((r) => num(r[f])).filter((v): v is number => v !== null) : [];
    return d?.type === "quantitative" && !!f && RATE.test(f.replace(/_/g, " ")) && vals.length > 0 && vals.every((v) => Math.abs(v) <= 1);
  };
  const fields = Object.entries(enc).filter(([k, d]) => d?.field && k !== "tooltip");
  if (!fields.some(([, d]) => isRate(d))) return spec;
  const out: Record<string, Record<string, unknown>> = {};
  for (const [k, d] of fields) {
    if (!isRate(d)) { out[k] = d; continue; }
    out[k] = { ...d, ...(k === "x" || k === "y" ? { axis: { ...(d.axis as object), format: ".2%" } } : { legend: { ...(d.legend as object), format: ".2%" } }) };
  }
  const tooltip = fields.map(([, d]) => ({ field: d.field, type: d.type, ...(isRate(d) ? { format: ".2%" } : {}) }));
  return { ...spec, encoding: { ...enc, ...out, tooltip } };
}

export function Figure({ rows, label, field = "value" }: { rows: Row[]; label: string; field?: string }) {
  const now = num(rows[0]?.[field]), before = num(rows[1]?.[field]);
  if (now === null) return <p className="ds-muted" role="img" aria-label={label}>Not available yet</p>;
  const rate = RATE.test(label) && Math.abs(now) <= 1 && (before === null || Math.abs(before) <= 1);
  const diff = before === null ? null : now - before;
  const pct = diff === null || before === 0 ? null : (diff / Math.abs(before as number)) * 100;
  const shown = rate ? asRate(now) : fmt(now);
  const moved = diff === null ? "" : rate
    ? `${diff > 0 ? "Up" : "Down"} ${fmt1(Math.abs(diff) * 100)} points`
    : `${diff > 0 ? "Up" : "Down"} ${fmt(Math.abs(diff))}${pct === null ? "" : ` (${pct1(Math.abs(pct))})`}`;
  return (
    <div role="img" aria-label={`${label}: ${shown}`}>
      <div style={{ fontSize: 36, fontWeight: 600, lineHeight: 1.1 }}>{shown}</div>
      {diff === null ? null : <div className="ds-muted">{diff === 0 ? "No change" : moved} on the period before</div>}
    </div>
  );
}

function Table({ rows, columns, label }: { rows: Row[]; columns?: string[]; label: string }) {
  const cols = columns ?? Object.keys(rows[0] ?? {});
  if (!rows.length) return <p className="ds-muted">Not available yet</p>;
  return (
    <div style={{ overflowX: "auto" }}>
      <table aria-label={label} style={{ borderCollapse: "collapse", width: "100%", fontSize: 13 }}>
        <thead><tr>{cols.map((c) => <th key={c} scope="col" style={{ textAlign: "left", padding: "2px 8px" }}>{head(c)}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i}>{cols.map((c) => <td key={c} style={{ padding: "2px 8px" }}>{show(r[c])}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

function Status({ rows, columns, label }: { rows: Row[]; columns?: string[]; label: string }) {
  const [a = "", b] = columns ?? Object.keys(rows[0] ?? {});
  if (!rows.length) return <p className="ds-muted">Not available yet</p>;
  return <ul aria-label={label} style={{ listStyle: "none", padding: 0, margin: 0 }}>{rows.map((r, i) => <li key={i} style={{ display: "flex", justifyContent: "space-between", gap: 8, padding: "2px 0" }}><span>{show(r[a])}</span>{b ? <strong>{show(r[b])}</strong> : null}</li>)}</ul>;
}

/** Axis, legend and grid colours from the page theme, so a chart sits on the card instead of a white box. */
function themed(): Record<string, unknown> {
  const css = typeof document === "undefined" ? null : getComputedStyle(document.documentElement);
  const v = (name: string, fb: string) => (css?.getPropertyValue(name).trim() || fb);
  const ink = v("--ds-ink", "#1f2a37"), soft = v("--ds-ink-soft", "#5b6b7a"), line = v("--ds-line-2", "#d0d7de");
  return { background: "transparent", padding: { left: 10, right: 8, top: 4, bottom: 4 }, view: { stroke: null }, font: "inherit",
    axis: { labelColor: soft, titleColor: soft, domainColor: line, tickColor: line, gridColor: line, gridOpacity: 0.5, labelFontSize: 11, titleFontSize: 11 },
    legend: { labelColor: soft, titleColor: soft, orient: "bottom" }, title: { color: ink },
    range: { category: ["#2BB3A3", "#E0A34A", "#7FA7D9", "#C7839C", "#9DB87A", "#B8A1E3"] } };
}

export default function Chart({ data, label, fill = false }: { data: TileData; label: string; fill?: boolean }) {
  const box = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  useEffect(() => {  // a widget box that is dragged bigger or smaller redraws its chart to fit
    const el = box.current;
    if (!fill || !el || typeof ResizeObserver === "undefined") return;
    let t: ReturnType<typeof setTimeout> | undefined;
    const ro = new ResizeObserver(([e]) => { clearTimeout(t); t = setTimeout(() => setSize({ w: Math.floor(e!.contentRect.width), h: Math.floor(e!.contentRect.height) }), 80); });
    ro.observe(el);
    return () => { clearTimeout(t); ro.disconnect(); };
  }, [fill]);
  // FIX1: a one-number tile drawn as a Vega text mark (Lumen's "number") is a figure too, so every figure kind shares one formatter
  const mark = data.spec.mark as string | { type?: string } | undefined;
  const enc = (data.spec.encoding ?? {}) as { text?: { field?: unknown }; x?: unknown; y?: unknown };
  const textField = (typeof mark === "string" ? mark : mark?.type) === "text" && !enc.x && !enc.y ? enc.text?.field : undefined;
  const view = (data.spec.usermeta as { view?: string } | undefined)?.view ?? (typeof textField === "string" ? "figure" : undefined);
  useEffect(() => {
    const el = box.current;
    if (!el || view) return;
    const base = data.rows ? { ...polish(rateSpec(data.spec, data.rows), data.rows), data: { values: data.rows } } : data.spec;
    if (fill && !size && typeof ResizeObserver !== "undefined") return;  // wait for the box size, then draw once to fit it
    const spec = { ...base, config: { ...themed(), ...((base as { config?: object }).config ?? {}) },
      ...(fill && size ? { width: Math.max(size.w, 160), height: Math.max(size.h, 220), autosize: { type: "fit", contains: "padding" } } : {}) };
    let vega: { finalize: () => void } | undefined;
    let live = true;
    embed(el, spec as never, { actions: false, renderer: "svg", ast: true }).then(
      (r) => { if (live) vega = r.view; else r.view.finalize(); },
      () => setFailed(true),
    );
    return () => { live = false; vega?.finalize(); };
  }, [data, view, fill, size]);
  const rows = data.rows ?? [];
  if (view === "figure") return <Figure rows={rows} label={label} field={typeof textField === "string" ? textField : "value"} />;
  if (view === "table") return <Table rows={rows} columns={data.columns} label={label} />;
  const Kind = view ? VIEWS[view] : undefined; // E: bullet, waterfall, small_multiples, calendar, treemap, kpi_strip (ChartKinds.tsx)
  if (Kind) return <Kind rows={rows} label={label} />;
  if (view === "status") return <Status rows={rows} columns={data.columns} label={label} />;
  if (failed) return <p role="alert">This chart could not be drawn. The numbers are still in the gold table.</p>;
  return <div ref={box} role="img" aria-label={label} style={fill ? { flex: "1 1 auto", minHeight: 240, width: "100%", overflow: "hidden" } : undefined} />;
}
