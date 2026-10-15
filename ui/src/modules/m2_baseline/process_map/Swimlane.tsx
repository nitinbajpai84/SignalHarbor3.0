import type { KeyboardEvent } from "react";

import Icon from "../../../components/Icon";
import type { KpiMap, MapStep, TrackingId } from "../api";
import { mapCopy as t } from "../copy";

// Ported from the earlier prototype's screens/process-map.js (stepCard, swimlaneGrid): the same markup and n2- classes,
// styled by the legacy screens-e2.css. Lanes down the left, steps across in order, manual steps in copper, the rest white.

export type StatusLabels = Record<TrackingId, string>;

/** The step's small description line: who it came from or who last acted on it. */
export function stepSource(s: MapStep): string {
  if (s.ask && s.mark === "to_confirm") return t.askToConfirm(s.ask);
  if (s.mark === "guessed") return t.fromPack;
  if (s.from === "technical") return t.fromTechnical;
  if (s.from.startsWith("added by")) return t.addedBy(s.by);
  if (s.state === "validated") return t.checkedBy(s.by);
  if (s.state === "edited") return t.editedBy(s.by);
  return s.owner ? t.said(s.owner) : t.fromAnswer;
}

/** The monospace line: the step's tracking status, and whether anyone confirmed it. */
export function stepFigure(s: MapStep, labels: StatusLabels): string {
  const status = s.tracking ? labels[s.tracking] : t.trackingUnknown;
  return `${status} · ${s.mark === "stated" ? t.confirmed : s.mark === "guessed" ? t.suggestion : t.toConfirmTag}`;
}

interface Props {
  kpi: KpiMap;
  labels: StatusLabels;
  selected: string | null;
  onSelect: (id: string) => void;
}

export default function Swimlane({ kpi, labels, selected, onSelect }: Props) {
  const steps = kpi.steps;
  const cols = steps.length;
  const lanes = kpi.lanes;
  const press = (id: string) => (e: KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect(id);
    }
  };
  return (
    <div className="n2-swimlane-wrap">
      <div
        className={`n2-swimlane ${cols > 6 ? "compact" : ""}`.trim()}
        style={{ gridTemplateColumns: `120px repeat(${cols}, minmax(0, 1fr))` }}
        role="group"
        aria-label={t.panelTitle}
      >
        {lanes.map((lane, r) => (
          <div key={`l-${lane}`} style={{ display: "contents" }}>
            <div className="n2-lane-label" style={{ gridRow: r + 2 }}>
              {lane}
            </div>
            {steps.map((_, c) => (
              <div key={c} className="n2-lane-cell" style={{ gridRow: r + 2, gridColumn: c + 2 }} />
            ))}
          </div>
        ))}
        {steps.map((_, c) => (
          <div key={`h-${c}`} className="n2-col-head" style={{ gridColumn: c + 2 }}>
            {t.step(c + 1)}
          </div>
        ))}
        {steps.map((s, c) => (
          <div key={s.id} className="n2-lane-slot" style={{ gridRow: lanes.indexOf(s.lane) + 2, gridColumn: c + 2 }}>
            <div
              className={`n2-step${s.manual ? " manual" : ""}`}
              role="button"
              tabIndex={0}
              aria-pressed={selected === s.id}
              aria-label={`${t.step(c + 1)}: ${s.text}`}
              onClick={() => onSelect(s.id)}
              onKeyDown={press(s.id)}
              style={{
                cursor: "pointer",
                ...(s.confirmed ? {} : { borderStyle: "dashed" }), // nobody confirmed it: dashed
                ...(selected === s.id ? { outline: "2px solid var(--teal)", outlineOffset: 1 } : {}),
              }}
            >
              {s.manual ? (
                <div className="n2-step-flag">
                  <Icon name="close" size={11} />
                  {t.manualTag}
                </div>
              ) : null}
              <div className="n2-step-title">{s.text}</div>
              <div className="n2-step-body">{stepSource(s)}</div>
              <div className="n2-step-kpi">{stepFigure(s, labels)}</div>
            </div>
          </div>
        ))}
      </div>
      <div className="n2-legend">
        <span className="n2-legend-item">
          <span className="n2-legend-swatch manual" />
          {t.legendManual}
        </span>
        <span className="n2-legend-item">
          <span className="n2-legend-swatch" />
          {t.legendSystem}
        </span>
        <span className="n2-legend-item">
          <span className="n2-legend-swatch" style={{ borderStyle: "dashed" }} />
          {t.legendToConfirm}
        </span>
      </div>
    </div>
  );
}
