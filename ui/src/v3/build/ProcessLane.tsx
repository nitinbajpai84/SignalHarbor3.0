import { useEffect, useState } from "react";

import type { SowView } from "../../v1/i4/api";
import Swimlane from "../../v1/i6/Swimlane";

export type LaneMap = NonNullable<SowView["process"]>;

/** A drafted process drawn as the swim lane, with an "Open full size" view that fills the window (Escape or Close returns). */
export default function ProcessLane({ map, title }: { map: LaneMap; title: string }) {
  const [step, setStep] = useState<number | null>(null);
  const [full, setFull] = useState(false);
  const pick = (n: number) => setStep(step === n ? null : n);
  useEffect(() => {
    if (!full) return;
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") setFull(false); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [full]);
  return (
    <>
      <div className="v3-row" style={{ justifyContent: "flex-end" }}>
        <button type="button" onClick={() => setFull(true)}>Open full size</button>
      </div>
      <Swimlane map={map} selected={step} onSelect={pick} />
      {full && (
        <div role="dialog" aria-modal="true" aria-label={`${title}: the process`} className="v3 b3-lane-full">
          <div className="v3-row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
            <h2>{title}</h2>
            <button type="button" autoFocus onClick={() => setFull(false)}>Close</button>
          </div>
          <Swimlane map={map} selected={step} onSelect={pick} />
        </div>
      )}
    </>
  );
}
