import { useEffect, useState } from "react";

import { Pill } from "../../design";
import type { Chat } from "./api";

// Copied from 2.0 ui/src/modules/m2_baseline/process_map/Swimlane.tsx (the as-is swimlane: same markup and n2- classes, styled by
// the global legacy screens-e2.css). Reshaped for the SOW's process: lanes are who does the step (else the system), columns the
// steps in order, manual steps tinted and flagged; columns keep a minimum width so the card scrolls sideways, never the page.

export const MANUAL = /manual|spreadsheet|excel|by hand/i;
type Map = Chat["process_map"];

function useNarrow() {
  const q = "(max-width: 759px)";
  const [n, setN] = useState(() => typeof window.matchMedia === "function" && window.matchMedia(q).matches);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const m = window.matchMedia(q), f = () => setN(m.matches);
    m.addEventListener("change", f); return () => m.removeEventListener("change", f);
  }, []);
  return n;
}

export default function Swimlane({ map, selected, onSelect }: { map: Map; selected: number | null; onSelect: (n: number) => void }) {
  const steps = map.steps;
  const narrow = useNarrow();
  const isManual = (s: Map["steps"][number]) => (s as { manual?: boolean }).manual === true || MANUAL.test(`${s.name} ${s.does}`);

  if (narrow) return (
    <ol aria-label="Process map" style={{ margin: 0, paddingLeft: 22, display: "grid", gap: 6 }}>
      {steps.map((s, c) => (
        <li key={s.n ?? c}>
          <button type="button" aria-pressed={selected === s.n} aria-label={`Step ${c + 1}: ${s.name}`} onClick={() => onSelect(s.n)}
            style={{ font: "inherit", textAlign: "left", background: "none", border: 0, padding: 0, cursor: "pointer", display: "block", width: "100%", ...(selected === s.n ? { outline: "2px solid var(--teal)", outlineOffset: 1 } : {}) }}>
            <span className="ds-muted">{s.who || s.system || "Not stated"} · </span>
            <strong>{s.name}</strong> {isManual(s) ? <Pill tone="late">Manual</Pill> : null}
            {/* UC9-02: on a phone the step keeps its system, what is done and the hand-over, as on the wide swim lane */}
            <span className="ds-muted" style={{ display: "block" }}>{s.system || "System not stated"}{s.does ? `. ${s.does}` : ""}</span>
            {map.handovers.filter((h) => h.from_step === s.n).map((h, j) => <span key={j} className="ds-muted" style={{ display: "block" }}>To step {h.to_step}: {h.what}</span>)}
          </button>
        </li>
      ))}
    </ol>
  );
  const laneOf = (s: Map["steps"][number]) => s.who || s.system || "Not stated";
  const lanes = [...new Set(steps.map(laneOf))];
  return (
    <div className="n2-swimlane-wrap">
      <p className="ds-muted" style={{ margin: "0 0 4px" }}>Scroll sideways to see all {steps.length} steps.</p>
      <div className={`n2-swimlane ${steps.length > 6 ? "compact" : ""}`.trim()} role="group" aria-label="Process map"
        style={{ gridTemplateColumns: `110px repeat(${steps.length}, minmax(150px, 1fr))`, minWidth: 110 + steps.length * 156 }}>
        {lanes.map((lane, r) => (
          <div key={`l-${lane}`} style={{ display: "contents" }}>
            <div className="n2-lane-label" style={{ gridRow: r + 2 }}>{lane}</div>
            {steps.map((_, c) => <div key={c} className="n2-lane-cell" style={{ gridRow: r + 2, gridColumn: c + 2 }} />)}
          </div>
        ))}
        {steps.map((_, c) => <div key={`h-${c}`} className="n2-col-head" style={{ gridColumn: c + 2 }}>Step {c + 1}</div>)}
        {steps.map((s, c) => {
          const manual = isManual(s);
          return (
            <div key={s.n ?? c} className="n2-lane-slot" style={{ gridRow: lanes.indexOf(laneOf(s)) + 2, gridColumn: c + 2 }}>
              <button type="button" className={`n2-step${manual ? " manual" : ""}`} aria-pressed={selected === s.n} onClick={() => onSelect(s.n)}
                aria-label={`Step ${c + 1}: ${s.name}`}
                style={{ cursor: "pointer", textAlign: "left", font: "inherit", width: "100%", ...(selected === s.n ? { outline: "2px solid var(--teal)", outlineOffset: 1 } : {}) }}>
                {manual ? <Pill tone="late">Manual</Pill> : null}
                <div className="n2-step-title">{s.name}</div>
                {s.does ? <div className="n2-step-body">{s.does}</div> : null}
                <div className="n2-step-kpi">{s.system || "System not stated"}</div>
                {map.handovers.filter((h) => h.from_step === s.n).map((h, j) => (
                  <div key={j} className="n2-step-body">To step {h.to_step}: {h.what}</div>
                ))}
              </button>
            </div>
          );
        })}
      </div>
      <div className="n2-legend">
        <span className="n2-legend-item"><span className="n2-legend-swatch manual" />Manual step</span>
        <span className="n2-legend-item"><span className="n2-legend-swatch" />Not flagged for automation</span>
      </div>
    </div>
  );
}
