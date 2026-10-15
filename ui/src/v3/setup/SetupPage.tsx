import { useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../api/client";
import V3Frame from "../Frame";
import { getSetup, listPacks, setSetup, type Pack } from "../api";
import { Waiting, packOf, useLoad } from "./shared";
import "./setup.css";

async function loadSetup() {
  const [setup, packs] = await Promise.all([getSetup(), listPacks().then((r) => r.packs, (): Pack[] => [])]);
  return { setup, packs };
}

/** Day one: the real setup steps, the industry pack choice, then the first question. */
export default function SetupPage() {
  const { data, failed, load, setData } = useLoad(loadSetup);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");

  async function choose(id: string) {
    setBusy(true);
    setProblem("");
    try {
      const setup = await setSetup(id);
      setData((d) => (d ? { ...d, setup } : d));
    } catch (e) {
      setProblem(e instanceof ApiError && e.status === 409 ? e.message : "That did not go through. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!data) return <V3Frame><main className="v3-main"><Waiting failed={failed} what="Setup" retry={load} /></main></V3Frame>;
  const { setup, packs } = data;
  const pack = packOf(setup);
  const steps = setup.steps;
  const done = steps.filter((s) => s.done).length;
  const waiting = steps.findIndex((s) => !s.done);
  const current = packs.find((p) => p.id === pack?.id);

  return (
    <V3Frame>
      <main className="v3-main s3">
        <section className="v3-col s3-wide" aria-labelledby="h-setup">
          <h1 id="h-setup">Day one setup</h1>
          {steps.length ? <p className="v3-mute num">{done} of {steps.length} done</p> : null}
          {problem && <p className="v3-err" role="alert">{problem}</p>}
          {!steps.length ? <p className="v3-mute">There are no setup steps yet.</p> : (
            <ol className="v3-tl">
              {steps.map((s, i) => {
                const m = s.done ? "done" : i === waiting ? "needs" : "info";
                return (
                <li key={s.id} className="v3-ev">
                  <div className="v3-rail"><span className={`v3-badge s3-${m}`}>{s.done ? "\u2713" : i + 1}</span></div>
                  <div className="v3-body">
                    <b>{s.label}</b>
                    <span className="s3-status"><span className={`v3-pill ${m}`}>{s.done ? "Done" : i === waiting ? "Needs you" : "Not started"}</span>{s.detail && <span className="v3-mute">{s.detail}</span>}</span>
                    {s.id === "pack" && !pack && (
                      packs.length ? (
                        <div className="v3-row" role="group" aria-label="Industry packs">
                          {packs.map((p) => <button key={p.id} type="button" disabled={busy} onClick={() => void choose(p.id)}>{p.label}</button>)}
                        </div>
                      ) : <p className="v3-mute">No industry packs are available to choose from yet.</p>
                    )}
                  </div>
                </li>
                );
              })}
            </ol>
          )}
          <div className="v3-row">
            <Link to="/v3/start" className="s3-go">Continue to the first question</Link>
            {waiting >= 0 && <span className="v3-mute">Step {waiting + 1} is waiting on you.</span>}
          </div>
        </section>

        <aside className="v3-side" aria-labelledby="h-get">
          <div className="v3-card">
            <h2 id="h-get">What you get on day one from the industry model</h2>
            {pack ? (
              <>
                <p className="v3-mute">{pack.label}. All of this is a suggestion; you decide what stays.</p>
                {current ? (
                  <div className="v3-figs">
                    <div className="v3-fig"><small>Business objects</small><span className="num">{current.objects}</span></div>
                    <div className="v3-fig"><small>Suggested questions</small><span className="num">{current.questions}</span></div>
                  </div>
                ) : <p className="v3-mute">The model's contents are not available yet.</p>}
                <Link to="/v3/trust/model">See the model</Link>
              </>
            ) : <p className="v3-mute">Choose an industry pack to start from its model.</p>}
          </div>
          <div className="v3-dark">
            <b>Month two onward</b>
            <p>Nothing to set up. Files arrive, Harbor runs, only exceptions reach you.</p>
          </div>
        </aside>
      </main>
    </V3Frame>
  );
}
