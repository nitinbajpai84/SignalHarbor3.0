import { useState, type FormEvent } from "react";
import { MicButton, combineText } from "../../v1/voice";
import { Link, useNavigate } from "react-router-dom";

import V3Frame from "../Frame";
import { getConnections, getPeople, getSetup, startThread } from "../api";
import { Waiting, packExamples, packOf, useLoad } from "./shared";
import "./setup.css";

const ROLE = { decides: "Decides", does: "Works", reads: "Reads" } as const;

async function loadWelcome() {
  const [people, conns, setup] = await Promise.all([getPeople(), getConnections(), getSetup()]);
  return { people: people.people, connections: conns.connections, pack: packOf(setup), examples: await packExamples(setup) };
}

/** First sign-in: people, where files come from, and the first question. */
export default function WelcomePage() {
  const nav = useNavigate();
  const { data, failed, load } = useLoad(loadWelcome);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");

  async function start(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setProblem("");
    try {
      nav(`/v3/thread/${(await startThread(text.trim())).id}`);
    } catch {
      setProblem("Harbor could not start that thread. Try again.");
      setBusy(false);
    }
  }

  if (!data) return <V3Frame><main className="v3-main"><Waiting failed={failed} what="Your office" retry={load} /></main></V3Frame>;
  const { people, connections, pack, examples } = data;
  const steps = [
    { n: 1, label: "Your people", done: people.length > 0 },
    { n: 2, label: "Where your files come from", done: connections.some((c) => c.state === "ok") },
    { n: 3, label: "Your first question", done: false },
  ];

  return (
    <V3Frame>
      <main className="v3-main s3 s3-stack">
        <header className="v3-col" style={{ maxWidth: 760 }}>
          <span className="v3-kicker">First sign-in · three steps</span>
          <h1>Set up your office in three steps</h1>
          <p className="v3-mute">Tell Harbor who decides and who does the work, where the files come from, and what you want answered first.</p>
        </header>
        <ol className="s3-steps" aria-label="Steps">
          {steps.map((s) => {
            const m = s.done ? "done" : s === steps.find((x) => !x.done) ? "needs" : "info";
            return (
              <li key={s.n} className="v3-card">
                <span className={`v3-badge s3-${m}`}>{s.done ? "\u2713" : s.n}</span>
                <span><b>{s.label}</b><br /><span className={`v3-pill ${m}`}>{s.done ? "Done" : "Not done yet"}</span></span>
              </li>
            );
          })}
        </ol>

        <div className="s3-cards">
          <section className="v3-card" aria-labelledby="h-people">
            <span className="v3-kicker">Step 1</span>
            <h2 id="h-people">Your people</h2>
            <p className="v3-mute">Who decides and who does the work.</p>
            {people.length ? (
              <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 8 }}>
                {people.map((p) => (
                  <li key={p.name} className="v3-row" style={{ justifyContent: "space-between" }}>
                    <span>{p.name}</span><span className="v3-chips"><span>{ROLE[p.role]}</span></span>
                  </li>
                ))}
              </ul>
            ) : <p className="v3-mute">No one has been added yet.</p>}
            <Link to="/v3/trust/people">Add a person to the office</Link>
          </section>

          <section className="v3-card" aria-labelledby="h-sources">
            <span className="v3-kicker">Step 2</span>
            <h2 id="h-sources">Where your files come from</h2>
            <p className="v3-mute">Pick one or more ways in. Files are recognised as they arrive.</p>
            {connections.length ? (
              <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 8 }}>
                {connections.map((c) => (
                  <li key={c.id} className="v3-row" style={{ justifyContent: "space-between" }}>
                    <span>{c.name}</span>
                    <span className={`v3-pill ${c.state === "ok" ? "done" : c.state === "failing" ? "problem" : "info"}`}>{c.state === "ok" ? "Connected" : c.state === "failing" ? "Not working" : "Coming"}</span>
                  </li>
                ))}
              </ul>
            ) : <p className="v3-mute">Nothing is connected yet.</p>}
            <span className="v3-row"><Link to="/v3/files">Drop or upload files</Link><Link to="/v3/trust/connections">Manage connections</Link></span>
          </section>

          <section className="v3-card" aria-labelledby="h-first">
            <span className="v3-kicker">Step 3</span>
            <h2 id="h-first">Pick your first question</h2>
            <p className="v3-mute">Harbor opens a thread with it. You can change or add questions later.</p>
            {!pack ? (
              <p className="v3-mute">No industry pack is chosen yet, so there are no suggestions. <Link to="/v3/setup">Choose one</Link>, or write your own below.</p>
            ) : examples.length ? (
              <>
                <p className="v3-mute">Suggested from the {pack.label} pack</p>
                {examples.map((q) => (
                  <button key={q} type="button" className="dashed" aria-pressed={text === q} onClick={() => setText(q)}>{q}</button>
                ))}
              </>
            ) : <p className="v3-mute">The {pack.label} pack has no suggested questions yet. Write your own below.</p>}
            <form onSubmit={start} className="v3-col">
              <label htmlFor="first-q" className="v3-mute">Your question</label>
              <textarea id="first-q" rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="Say what you want to know, in your own words." />
              {problem && <p className="v3-err" role="alert">{problem}</p>}
              <div className="v3-row" style={{ justifyContent: "space-between" }}>
                <MicButton agent="Harbor" disabled={busy} onText={(said) => setText((t0) => combineText(t0, said))} />
                <button type="submit" className="go" disabled={busy || !text.trim()}>Start</button>
              </div>
            </form>
          </section>
        </div>
        <p className="v3-mute">Your files, figures and questions stay in your office's own environment. Nothing leaves it unless you send it.</p>
      </main>
    </V3Frame>
  );
}
