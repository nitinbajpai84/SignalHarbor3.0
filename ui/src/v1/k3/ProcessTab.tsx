import { useState } from "react";

import ScreenState from "../../components/ScreenState";
import { useLoad } from "../../components/useLoad";
import { Chip, Pill } from "../../design";
import Swimlane from "../i6/Swimlane";
import { getProcesses } from "./api";
import { day } from "./dates";

// Every signed intent's swim lane, drawn by the same component the Intent centre uses. Read-only.
export default function ProcessTab({ focus }: { focus: string | null }) {
  const { state, data, message, retry } = useLoad(getProcesses, "k3-processes", (d) => d.processes.length === 0);
  const [chosen, setChosen] = useState<string | null>(null);
  const [step, setStep] = useState<number | null>(null);
  const list = data?.processes ?? [];
  const cur = list.find((p) => p.iid === (chosen ?? focus)) ?? list[0];
  return (
    <ScreenState state={state} message={state === "empty" ? "No process has been signed yet. A swim lane appears here when an intent of work with a process is signed." : message} onRetry={retry}>
      {cur ? (
        <>
          <div role="tablist" aria-label="Signed processes" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
            {list.map((p) => <Chip key={p.iid} tone={p.iid === cur.iid ? "active" : "default"} onClick={() => { setChosen(p.iid); setStep(null); }}>{p.title}</Chip>)}
          </div>
          <p className="ds-muted">Owner: {cur.owner ?? "Not named yet"}. Signed {day(cur.signed_on)}. <Pill tone="signed">Signed</Pill></p>
          {cur.locked
            ? <p role="status" className="ds-muted">You can see that this process exists. Its steps are for the project team.</p>
            : <Swimlane map={cur.process} selected={step} onSelect={setStep} />}
        </>
      ) : null}
    </ScreenState>
  );
}
