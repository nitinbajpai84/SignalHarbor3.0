import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getOnboarding, tickStep, type Onboarding as Ob, type OnboardingStep } from "../api";
import V3Frame from "../Frame";
import "./build.css";

const LABEL: Record<OnboardingStep["status"], [string, string]> = { done: ["done", "Done"], doing: ["harbor", "Harbor is on it"], waiting: ["info", "Waiting"], attention: ["problem", "Needs a look"] };
const when = (at: string) => new Date(at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export default function Onboarding() {
  const [ob, setOb] = useState<Ob | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  const load = useCallback(() => { getOnboarding().then((r) => { setOb(r); setErr(""); }).catch((e: Error) => setErr(e.message)); }, []);
  useEffect(() => { load(); }, [load]);
  const tick = (s: OnboardingStep) => {
    setBusy(s.id); setErr("");
    tickStep(s.id, s.status !== "done").then(setOb).catch((e: Error) => setErr(e.message)).finally(() => setBusy(""));
  };
  return (
    <V3Frame back={<Link to="/v3/build" className="b3-back">&larr; Use cases</Link>}>
      <main className="b3-board b3">
        <div>
          <h1>Onboarding</h1>
          <p className="v3-mute">Ten steps from the first conversation to go-live. Harbor does what it can and shows what it did; the rest wait for a person, who ticks them.</p>
        </div>
        {err && <p className="v3-err" role="alert">{err} <button onClick={load}>Try again</button></p>}
        {ob === null && !err && <p className="v3-mute" role="status">Loading the checklist...</p>}
        {ob && (
          <>
            <section className="b3-card g-score" aria-label="Onboarding health">
              <div className="g-num" aria-label={`Health score ${ob.score} out of 100`}>{ob.score}<small>/100</small></div>
              <ul className="g-parts">
                {ob.parts.map((p) => <li key={p.label}><b>{p.label}</b> <span className="v3-mute">{p.points} of {p.weight} · {p.detail}</span></li>)}
              </ul>
            </section>
            <ol className="g-steps">
              {ob.steps.map((s, i) => {
                const [cls, word] = LABEL[s.status];
                return (
                  <li key={s.id} className="b3-card">
                    <div className="v3-row g-head"><b>{i + 1}. {s.step}</b><span className={`v3-pill ${cls}`}>{word}</span></div>
                    <p className="v3-mute">Owner: {s.owner}</p>
                    {s.harbor && <p>Harbor: {s.harbor}</p>}
                    {s.detail && <p className="v3-mute">{s.detail}</p>}
                    {s.ticked_by && s.ticked_at && <p className="v3-mute">Ticked by {s.ticked_by}, {when(s.ticked_at)}</p>}
                    {s.manual && (
                      <div className="v3-row"><button disabled={busy === s.id} onClick={() => tick(s)}>{s.status === "done" ? "Untick" : "Tick as done"}</button></div>
                    )}
                  </li>
                );
              })}
            </ol>
          </>
        )}
      </main>
    </V3Frame>
  );
}
