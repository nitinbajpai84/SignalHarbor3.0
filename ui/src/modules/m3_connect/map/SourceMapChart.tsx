import { useMemo, useState, type KeyboardEvent } from "react";

import type { MapSource, SourceKind, ZoneId } from "../api";
import { mapCopy as t } from "./copy";

// A small SVG scatter, written for this screen (the earlier repo has no scatter: reuse check, section 6). Colours are the existing tokens,
// never literals. The line sits at zero on each axis (D-036): readiness runs left to right, impact bottom to top.

const W = 640;
const H = 440;
const PAD = { l: 44, r: 16, t: 28, b: 44 };
const PW = W - PAD.l - PAD.r;
const PH = H - PAD.t - PAD.b;
const x = (r: number) => PAD.l + ((Math.max(-1, Math.min(1, r)) + 1) / 2) * PW;
const y = (i: number) => PAD.t + ((1 - Math.max(-1, Math.min(1, i))) / 2) * PH;
const MID = { x: x(0), y: y(0) };

export const ZONE_FILL: Record<ZoneId, string> = { p1: "var(--gbg)", p2: "var(--teal-tint)", identify: "var(--nbg)", unknown: "var(--abg)" };
export const KIND_FILL: Record<SourceKind, string> = {
  spreadsheet: "var(--teal)",
  email: "var(--suggest)",
  "outside feed": "var(--retention)",
  system: "var(--navy)",
  hidden: "var(--grey)",
};
const ZONE_BOX: Record<ZoneId, { x: number; y: number; w: number; h: number; ax: number; ay: number }> = {
  unknown: { x: PAD.l, y: PAD.t, w: MID.x - PAD.l, h: MID.y - PAD.t, ax: PAD.l + 8, ay: PAD.t + 18 },
  p1: { x: MID.x, y: PAD.t, w: W - PAD.r - MID.x, h: MID.y - PAD.t, ax: MID.x + 8, ay: PAD.t + 18 },
  identify: { x: PAD.l, y: MID.y, w: MID.x - PAD.l, h: H - PAD.b - MID.y, ax: PAD.l + 8, ay: H - PAD.b - 10 },
  p2: { x: MID.x, y: MID.y, w: W - PAD.r - MID.x, h: H - PAD.b - MID.y, ax: MID.x + 8, ay: H - PAD.b - 10 },
};
export const radius = (n: number) => 7 + Math.min(Math.max(n, 1), 8) * 2;

const LABELLED = 5; // the largest dots always carry their name; the rest show it on hover or focus

/** Nudges overlapping dots apart so each stays clickable. A dot never crosses the axis lines, so its zone does not change. */
export function spread(sources: MapSource[]): Map<string, { cx: number; cy: number }> {
  const pts = sources.map((s) => {
    const r = radius(s.measures_fed);
    const cx = x(s.readiness);
    const cy = y(s.impact);
    return { id: s.id, r, cx, cy, right: cx >= MID.x, below: cy >= MID.y };
  });
  const clamp = (p: (typeof pts)[number]) => {
    const [x0, x1] = p.right ? [MID.x + p.r, W - PAD.r - p.r] : [PAD.l + p.r, MID.x - p.r];
    const [y0, y1] = p.below ? [MID.y + p.r, H - PAD.b - p.r] : [PAD.t + p.r, MID.y - p.r];
    p.cx = Math.min(x1, Math.max(x0, p.cx));
    p.cy = Math.min(y1, Math.max(y0, p.cy));
  };
  pts.forEach(clamp);
  // ponytail: simple pairwise push, 60 passes; fine for dozens of dots, use a force layout for hundreds.
  for (let pass = 0; pass < 60; pass++) {
    let moved = false;
    pts.forEach((a, i) => {
      for (const b of pts.slice(i + 1)) {
        let dx = b.cx - a.cx;
        let dy = b.cy - a.cy;
        let d = Math.hypot(dx, dy);
        const need = a.r + b.r + 3;
        if (d >= need) continue;
        if (d < 0.01) {
          const ang = ((i + pts.indexOf(b)) * 2.4) % (2 * Math.PI); // a fixed angle, so the layout is the same on every draw
          dx = Math.cos(ang);
          dy = Math.sin(ang);
          d = 1;
        }
        const push = (need - d) / 2 + 0.5;
        a.cx -= (dx / d) * push;
        a.cy -= (dy / d) * push;
        b.cx += (dx / d) * push;
        b.cy += (dy / d) * push;
        moved = true;
      }
      clamp(a);
    });
    pts.forEach(clamp);
    if (!moved) break;
  }
  return new Map(pts.map((p) => [p.id, { cx: p.cx, cy: p.cy }]));
}

interface Props {
  sources: MapSource[];
  selected: string | null;
  onSelect: (id: string) => void;
}

export default function SourceMapChart({ sources, selected, onSelect }: Props) {
  const [hot, setHot] = useState<string | null>(null);
  const spots = useMemo(() => spread(sources), [sources]);
  const biggest = useMemo(
    () => new Set([...sources].sort((a, b) => b.measures_fed - a.measures_fed).slice(0, LABELLED).map((s) => s.id)),
    [sources],
  );
  const press = (id: string) => (e: KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect(id);
    }
  };
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="group" aria-label={t.chartLabel} style={{ width: "100%", height: "auto", maxWidth: W }}>
      {(Object.keys(ZONE_BOX) as ZoneId[]).map((z) => (
        <g key={z}>
          <rect {...pick(ZONE_BOX[z])} style={{ fill: ZONE_FILL[z], stroke: "var(--line)" }} />
          <text x={ZONE_BOX[z].ax} y={ZONE_BOX[z].ay} fontSize="12" fontWeight="700" style={{ fill: "var(--ink2)" }}>
            {t.zones[z]}
          </text>
        </g>
      ))}
      <line x1={MID.x} x2={MID.x} y1={PAD.t} y2={H - PAD.b} strokeWidth="1.5" style={{ stroke: "var(--ink2)" }} />
      <line x1={PAD.l} x2={W - PAD.r} y1={MID.y} y2={MID.y} strokeWidth="1.5" style={{ stroke: "var(--ink2)" }} />
      <text x={W / 2} y={H - 10} textAnchor="middle" fontSize="12" style={{ fill: "var(--ink2)" }}>
        {t.axisReadiness}
      </text>
      <text transform={`translate(14 ${H / 2}) rotate(-90)`} textAnchor="middle" fontSize="12" style={{ fill: "var(--ink2)" }}>
        {t.axisImpact}
      </text>
      {sources.map((s) => {
        const r = radius(s.measures_fed);
        const { cx, cy } = spots.get(s.id) ?? { cx: x(s.readiness), cy: y(s.impact) };
        const named = biggest.has(s.id) || hot === s.id || selected === s.id;
        return (
          <g key={s.id} role="button" tabIndex={0} aria-label={t.open(s.name)} aria-pressed={selected === s.id} style={{ cursor: "pointer" }}
            onClick={() => onSelect(s.id)} onKeyDown={press(s.id)}
            onMouseEnter={() => setHot(s.id)} onMouseLeave={() => setHot(null)} onFocus={() => setHot(s.id)} onBlur={() => setHot(null)}>
            <title>{`${s.name}. ${t.zones[s.zone]}`}</title>
            <circle cx={cx} cy={cy} r={r} style={{ fill: KIND_FILL[s.kind], stroke: selected === s.id ? "var(--ink)" : "var(--card)" }}
              strokeWidth={selected === s.id ? 3 : 1.5} />
            {s.override ? <circle cx={cx} cy={cy} r={r + 4} fill="none" strokeWidth="1.5" strokeDasharray="3 3" style={{ stroke: "var(--ink)" }} /> : null}
            {s.restricted ? (
              <g transform={`translate(${cx - 6} ${cy - 7})`} aria-hidden="true">
                <rect x="1" y="6" width="10" height="8" rx="1.5" style={{ fill: "var(--card)" }} />
                <path d="M3 6V4a3 3 0 0 1 6 0v2" fill="none" strokeWidth="1.6" style={{ stroke: "var(--card)" }} />
              </g>
            ) : null}
            {named ? (
              <text x={cx} y={cy + r + 12} textAnchor="middle" fontSize="11" data-label="" style={{ fill: "var(--ink)", pointerEvents: "none" }}>
                {s.name}
              </text>
            ) : null}
          </g>
        );
      })}
    </svg>
  );
}

/** The marks on a source, in words: colour and shape never say it alone. */
export function markLines(s: MapSource): string[] {
  const m = s.marks;
  return [m.restricted ? t.marks.restricted : "", m.blocked_upstream ? t.marks.blocked_upstream : "", m.licence ? t.marks.licence : "",
    m.owners_disagree ? t.marks.owners_disagree : "", m.effort ? t.marks.effort(m.effort) : ""].filter(Boolean);
}

function pick(b: { x: number; y: number; w: number; h: number }) {
  return { x: b.x, y: b.y, width: b.w, height: b.h };
}
