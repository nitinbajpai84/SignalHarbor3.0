import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { MicButton, combineText } from "../../v1/voice";
import V3Frame from "../Frame";
import { getSetup, startThread } from "../api";
import { Waiting, packExamples, packOf, useLoad } from "./shared";
import "./setup.css";

async function loadSuggestions() {
  const setup = await getSetup();
  return { pack: packOf(setup), examples: await packExamples(setup) };
}

const THREE = [
  ["The brief.", "Is this what you want to know, and who reads it?"],
  ["The understanding.", "Is this how I read your files? Two or three things to confirm, no more."],
  ["The numbers.", "Do they match the figures you already trust? If yes, you say go live."],
] as const;

/** A new thread: say it, speak it, or start from a pack suggestion. */
export default function StartPage() {
  const nav = useNavigate();
  const { data, failed, load } = useLoad(loadSuggestions);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");

  async function send(q: string) {
    if (!q.trim()) return;
    setBusy(true);
    setProblem("");
    try {
      nav(`/v3/thread/${(await startThread(q.trim())).id}`);
    } catch {
      setProblem("Harbor could not start that thread. Try again.");
      setBusy(false);
    }
  }
  const submit = (e: FormEvent) => { e.preventDefault(); void send(text); };

  return (
    <V3Frame>
      <main className="v3-main s3">
        <section className="v3-col s3-wide" aria-labelledby="h-start">
          <span className="v3-kicker">New thread · step 1 of 3, the brief</span>
          <h1 id="h-start">What do you want to know, and who needs it?</h1>
          <form onSubmit={submit} className="v3-card">
            <label htmlFor="brief" className="v3-mute">Say it in your own words</label>
            <textarea id="brief" rows={4} value={text} onChange={(e) => setText(e.target.value)} />
            <div className="v3-row" style={{ justifyContent: "space-between" }}>
              <span className="v3-row">
                <MicButton agent="Harbor" disabled={busy} onText={(said) => setText((t) => combineText(t, said))} />
                <Link to="/v3/files">Attach sample files</Link>
              </span>
              <button type="submit" className="go" disabled={busy || !text.trim()}>Send to Harbor</button>
            </div>
            {problem && <p className="v3-err" role="alert">{problem}</p>}
          </form>

          <h2 className="s3-label">Or start from a ready question</h2>
          {!data ? <Waiting failed={failed} what="Suggestions" retry={load} />
            : !data.pack ? <p className="v3-mute">No industry pack is chosen yet, so there are no ready questions. <Link to="/v3/setup">Choose one</Link>.</p>
            : !data.examples.length ? <p className="v3-mute">The {data.pack.label} pack has no ready questions yet.</p>
            : (
              <>
                <p className="v3-mute">Suggestions from the {data.pack.label} pack. Pick one and Harbor starts from it; you still confirm the three things.</p>
                <div className="s3-ready">
                  {data.examples.map((q) => (
                    <button key={q} type="button" className="dashed" disabled={busy} onClick={() => void send(q)}>{q}</button>
                  ))}
                </div>
              </>
            )}
        </section>

        <aside className="v3-side" aria-labelledby="h-three">
          <div className="v3-dark">
            <h2 id="h-three">Harbor will ask you only three things for each question</h2>
            <ol style={{ margin: 0, paddingLeft: 20 }}>
              {THREE.map(([b, t]) => <li key={b}><p><b>{b}</b> {t}</p></li>)}
            </ol>
            <p><b>Then only exceptions.</b> A late file, an unmatched row or a figure that cannot be tied comes to you as one card on the Desk. Nothing else does.</p>
          </div>
        </aside>
      </main>
    </V3Frame>
  );
}
