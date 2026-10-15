import { useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

import { Button } from "../../../design";
import type { MapSource, ZoneId } from "../api";
import { truthText as t } from "./copy";

// Artboard 4's source map: impact up the side, readiness across, the line at zero on each axis (D-036), four zones.
// A person who may act drags a dot (or moves it with the arrow keys) and says why; the move goes to the existing override route.

const W = 560, H = 300, P = 10;
const PW = W - 2 * P, PH = H - 2 * P;
const MX = P + PW / 2, MY = P + PH / 2;
const clamp = (v: number) => Math.max(-1, Math.min(1, v));
const px = (readiness: number) => P + ((clamp(readiness) + 1) / 2) * PW;
const py = (impact: number) => P + ((1 - clamp(impact)) / 2) * PH;
const round = (v: number) => Math.round(clamp(v) * 100) / 100;
const zoneOf = (impact: number, readiness: number): ZoneId => (impact >= 0 ? (readiness >= 0 ? "p1" : "unknown") : readiness >= 0 ? "p2" : "identify");

const BOX: Record<ZoneId, { x: number; y: number; tone: string }> = {
  unknown: { x: P, y: P, tone: "var(--ds-amber)" },
  p1: { x: MX, y: P, tone: "var(--ds-teal-bright)" },
  identify: { x: P, y: MY, tone: "var(--ds-ink-faint)" },
  p2: { x: MX, y: MY, tone: "var(--ds-ink-muted)" },
};

interface Spot { impact: number; readiness: number }

/** Where a dot's label runs along x: from the dot to the right, or to the left near the right edge (about 6 px a letter at size 11). */
function span(name: string, cx: number): [number, number] {
  const w = name.length * 6 + 16;
  return cx > W - 170 ? [cx - w, cx + 6] : [cx - 6, cx + w];
}
// the four zone names sit at the top left of their boxes: a label never lands on one
const ZONE_LABELS = (Object.keys(BOX) as ZoneId[]).map((z) => ({ x0: BOX[z].x, x1: BOX[z].x + 130, y: BOX[z].y + 12 }));

/** Dot centres; a dot whose label would touch an earlier label or a zone name steps down, then up, inside the plot. */
function place(sources: MapSource[], moved: Record<string, Spot>): Map<string, { cx: number; cy: number }> {
  const out = new Map<string, { cx: number; cy: number; x0: number; x1: number }>();
  for (const s of sources) {
    const at = moved[s.id] ?? s;
    const cx = Math.min(W - P - 8, Math.max(P + 8, px(at.readiness)));
    const [x0, x1] = span(s.name, cx);
    const lo = P + 8, hi = H - P - 8, want = Math.min(hi, Math.max(lo, py(at.impact)));
    const hit = (o: { x0: number; x1: number; y: number }, y: number) => o.x0 < x1 && x0 < o.x1 && Math.abs(o.y - y) < 14;
    // ponytail: step away from the wanted height, down then up, until the label is clear; a force layout if maps grow past a few dozen sources
    const clear = (y: number) => y >= lo && y <= hi && ![...out.values()].some((o) => hit({ ...o, y: o.cy }, y)) && !ZONE_LABELS.some((z) => hit(z, y));
    let cy = want;
    for (let k = 1; k < 40 && !clear(cy); k++) cy = want + (k % 2 ? 1 : -1) * Math.ceil(k / 2) * 14;
    out.set(s.id, { cx, cy, x0, x1 });
  }
  return out;
}

export default function SourceQuadrant({ sources, canMove, onMove }: {
  sources: MapSource[]; canMove: boolean; onMove: (id: string, spot: Spot, reason: string) => Promise<void>;
}) {
  const svg = useRef<SVGSVGElement>(null);
  const [drag, setDrag] = useState<string | null>(null);
  const [moved, setMoved] = useState<Record<string, Spot>>({});
  const [pending, setPending] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);
  const spots = place(sources, moved);

  function spotAt(e: PointerEvent): Spot | null {
    const r = svg.current?.getBoundingClientRect();
    if (!r || !r.width || !r.height) return null;
    const x = ((e.clientX - r.left) * W) / r.width, y = ((e.clientY - r.top) * H) / r.height;
    return { readiness: round(((x - P) / PW) * 2 - 1), impact: round(1 - ((y - P) / PH) * 2) };
  }
  const put = (id: string, s: Spot) => { setMoved((m) => ({ ...m, [id]: s })); setPending(id); setProblem(""); };
  function key(s: MapSource) {
    return (e: KeyboardEvent) => {
      const step = ({ ArrowUp: [0.1, 0], ArrowDown: [-0.1, 0], ArrowLeft: [0, -0.1], ArrowRight: [0, 0.1] } as Record<string, [number, number]>)[e.key];
      if (!canMove || s.restricted || !step) return;
      e.preventDefault();
      const at = moved[s.id] ?? s;
      put(s.id, { impact: round(at.impact + step[0]), readiness: round(at.readiness + step[1]) });
    };
  }
  function cancel() {
    if (pending) setMoved(({ [pending]: _, ...rest }) => rest);
    setPending(null);
    setReason("");
    setProblem("");
  }
  async function save() {
    const spot = pending ? moved[pending] : undefined;
    if (!pending || !spot) return;
    if (!reason.trim()) { setProblem(t.moveNeedReason); return; }
    setBusy(true);
    try {
      await onMove(pending, spot, reason.trim());
      setPending(null);
      setReason("");
    } catch {
      setProblem(t.moveFailed);
    } finally {
      setBusy(false);
    }
  }
  const p = pending ? sources.find((s) => s.id === pending) : undefined;
  const target = pending ? moved[pending] : undefined;
  return (
    <div>
      {/* ponytail: on a phone the map keeps a readable width and scrolls sideways rather than shrinking its labels */}
      <div style={{ overflowX: "auto" }}>
      <svg ref={svg} viewBox={`0 0 ${W} ${H}`} role="group" aria-label={t.mapLabel} style={{ width: "100%", minWidth: 480, height: "auto" }}
        onPointerMove={(e) => { if (drag) { const s = spotAt(e); if (s) setMoved((m) => ({ ...m, [drag]: s })); } }}
        onPointerUp={() => { if (drag) { setPending(drag); setDrag(null); } }}>
        {(Object.keys(BOX) as ZoneId[]).map((z) => (
          <g key={z}>
            <rect x={BOX[z].x} y={BOX[z].y} width={PW / 2} height={PH / 2} fill={BOX[z].tone} fillOpacity={z === "p1" || z === "unknown" ? 0.07 : 0} />
            <text x={BOX[z].x + 10} y={BOX[z].y + 16} fontSize="10" letterSpacing="1" fontWeight="600" fill={BOX[z].tone}>{t.zones[z]}</text>
          </g>
        ))}
        <line x1={MX} x2={MX} y1={P} y2={H - P} stroke="var(--ds-line-2)" strokeDasharray="3 3" />
        <line x1={P} x2={W - P} y1={MY} y2={MY} stroke="var(--ds-line-2)" strokeDasharray="3 3" />
        {sources.map((s) => {
          const { cx, cy } = spots.get(s.id)!;
          const at = moved[s.id] ?? s;
          const zone = moved[s.id] ? zoneOf(at.impact, at.readiness) : s.zone;
          const r = 4 + Math.min(Math.max(s.measures_fed, 1), 4);
          const end = cx > W - 170;
          const movable = canMove && !s.restricted;
          return (
            <g key={s.id} tabIndex={0} role="img" aria-label={`${s.name}: ${t.zones[zone]}`} data-zone={zone}
              style={{ cursor: movable ? "grab" : "default", touchAction: movable ? "none" : undefined }} onKeyDown={key(s)}
              onPointerDown={(e) => { if (!movable) return; e.preventDefault(); (e.currentTarget as Element).setPointerCapture?.(e.pointerId); setDrag(s.id); setProblem(""); }}>
              <title>{`${s.name}. ${t.zones[zone]}`}</title>
              <circle cx={cx} cy={cy} r={r} fill={s.restricted || zone === "identify" ? "none" : BOX[zone].tone}
                stroke={BOX[zone].tone} strokeDasharray={s.restricted || zone === "identify" ? "2 2" : undefined} strokeWidth={1.5} />
              {s.override ? <circle cx={cx} cy={cy} r={r + 4} fill="none" stroke="var(--ds-ink-muted)" strokeDasharray="2 3" /> : null}
              <text x={end ? cx - r - 6 : cx + r + 6} y={cy + 4} textAnchor={end ? "end" : "start"} fontSize="11" fill="var(--ds-ink-soft)">{s.name}</text>
            </g>
          );
        })}
      </svg>
      </div>
      {p && target ? (
        <div className="ds-signature" role="group" aria-label={t.moveReason}>
          <span className="ds-signature__text">{t.moveTo(p.name, t.zones[zoneOf(target.impact, target.readiness)])}</span>
          <input aria-label={t.moveReason} placeholder={t.moveReason} value={reason} onChange={(e) => setReason(e.target.value)} />
          <Button variant="primary" disabled={busy} onClick={() => void save()}>{t.moveSave}</Button>
          <Button onClick={cancel}>{t.moveCancel}</Button>
          {problem ? <p role="alert" className="ds-warn">{problem}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
