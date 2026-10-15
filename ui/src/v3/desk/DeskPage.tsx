import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useSession } from "../../useSession";
import { MicButton, combineText } from "../../v1/voice";
import V3Frame from "../Frame";
import Discard from "../thread/Discard";
import { when } from "../thread/ThreadPage";
import { decide, getDesk, getThread, say, startThread, type Card, type Desk, type Event, type Stage } from "../api";
import "./desk.css";

const STEP: Record<string, 1 | 2 | 3> = { confirm: 1, carry_on: 2, go_live: 3 };
const KIND: Record<Card["kind"], string> = { decision: "Decision", exception: "Exception", question: "Question" };
const DOTS = ["Brief", "Understanding", "Numbers", "Live"];
/** Index of the current dot for each stage; dots before it are reached. */
const REACHED: Record<Stage, number> = { drafting: 0, decision1: 0, working: 1, question: 1, decision2: 2, decision3: 2, live: 3, discarded: 0 };
/** Stages where the thread waits on a person rather than on Harbor. */
const WAITS = new Set<Stage>(["decision1", "decision2", "decision3", "question"]);
/** Reached = done, current = needs (waits on a person) or harbor (Harbor is working), not reached = info. */
const dot = (k: number, at: number, stage: Stage, needs: number) =>
  k < at || stage === "live" ? "done" : k > at ? "info" : WAITS.has(stage) || needs > 0 ? "needs" : "harbor";

type Feed = { at: string; text: string };

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

export default function DeskPage() {
  const nav = useNavigate();
  const { user } = useSession();
  const [desk, setDesk] = useState<Desk | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const [text, setText] = useState("");
  const [feed, setFeed] = useState<Feed[]>([]);

  const load = useCallback(() => {
    setFailed(false);
    getDesk().then((d) => {
      setDesk(d);
      // The overnight feed reads each thread's own events; a thread that will not load is skipped.
      Promise.all(d.threads.slice(0, 6).map((t) => getThread(t.id).then((x) => (Array.isArray(x.events) ? x.events : []), () => [] as Event[]))).then((all) =>
        setFeed(
          all.flat().filter((e) => e.kind === "harbor" || e.kind === "chips")
            .sort((a, b) => (a.at < b.at ? 1 : -1)).slice(0, 4)
            .map((e) => ({ at: e.at, text: e.kind === "chips" ? (e.chips ?? []).join(", ") : e.text ?? "" })),
        ),
      );
    }, () => setFailed(true));
  }, []);
  useEffect(load, [load]);

  /** A decision card's known answers go to decide; other cards answer in the thread; "open" opens it. */
  async function act(c: Card, answer: string) {
    const n = STEP[answer];
    if (c.kind === "decision" && !n) return nav(`/v3/build/${c.thread}`);
    setBusy(true);
    setProblem("");
    try {
      if (n) await decide(c.thread, n, answer);
      else await say(c.thread, answer);
      load();
    } catch {
      setProblem("That did not go through. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function start(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setProblem("");
    try {
      const t = await startThread(text.trim());
      nav(`/v3/build/${t.id}`);
    } catch {
      setProblem("Harbor could not start that thread. Try again.");
      setBusy(false);
    }
  }

  const body = () => {
    if (failed) {
      return <main className="v3-main"><p className="v3-err" role="alert">The Desk did not load. <button type="button" onClick={load}>Try again</button></p></main>;
    }
    if (!desk) return <main className="v3-main"><p className="v3-mute" role="status">Loading the Desk...</p></main>;
    if (!desk.needs.length && !desk.threads.length && !desk.note) {
      return (
        <main className="v3-main"><section className="v3-col">
          <h1>Nothing here yet</h1>
          <p className="v3-mute">This office is new. <Link to="/v3/welcome">Set up the office</Link> to bring in your first files and start a thread.</p>
        </section></main>
      );
    }
    const { needs, note, threads, files } = desk;
    const building = threads.filter((t) => t.stage !== "live");
    const live = threads.length - building.length;
    const first = (user?.display_name ?? "").trim().split(/\s+/)[0];
    const rest = ` you today. ${plural(building.length, "use case is", "use cases are")} being built${note ? ", and this morning's note is ready" : ""}.`;
    return (
      <main className="desk">
        <div className="desk-main">
          <section aria-labelledby="h-greet" className="v3-col">
            <h1 id="h-greet">{first ? `Good morning, ${first}` : "Good morning"}</h1>
            <p className="desk-sum">{needs.length ? <b>{plural(needs.length, "thing needs", "things need")}</b> : plural(0, "thing needs", "things need")}{rest}</p>
            {problem && <p className="v3-err" role="alert">{problem}</p>}
            <form onSubmit={start} className="desk-ask">
              <label htmlFor="ask" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden" }}>Ask Harbor or start something new</label>
              <input id="ask" value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask Harbor or start something new..." />
              <MicButton agent="Harbor" disabled={busy} onText={(t) => setText((b) => combineText(b, t))} />
              <button type="submit" className="go" disabled={busy || !text.trim()}>Start</button>
            </form>
          </section>

          <div className="desk-cols">
            <section aria-labelledby="h-action">
              <div className="v3-head"><h2 id="h-action">Act now</h2>{needs.length > 0 && <span className="v3-pill needs">{needs.length} open</span>}</div>
              {!needs.length && <p className="v3-mute">Nothing needs you right now.</p>}
              {needs.slice(0, 3).map((c, i) => (
                <article key={`${c.thread}-${i}`} className="v3-card need">
                  <span className="v3-kicker">{KIND[c.kind]}</span>
                  <b className="desk-title">{c.title}</b>
                  <p>{c.text}</p>
                  <div className="v3-row">
                    {c.actions.map((a, j) => (
                      <button key={a.answer + j} type="button" className={j === 0 ? "go" : ""} disabled={busy} onClick={() => act(c, a.answer)}>{a.label}</button>
                    ))}
                  </div>
                </article>
              ))}
              <p className="desk-more"><Link to="/v3/action">Go to Action</Link></p>
            </section>

            <section aria-labelledby="h-build">
              <div className="v3-head"><h2 id="h-build">Being built</h2>{building.length > 0 && <span className="v3-pill">{building.length} working</span>}</div>
              {!building.length && <p className="v3-mute">Nothing is being built right now.</p>}
              {building.map((t) => {
                const at = REACHED[t.stage];
                return (
                  <div key={t.id} className="v3-threadrow">
                    <Link to={`/v3/build/${t.id}`} className="v3-link">
                      <b>{t.title}{t.needs > 0 && <span className="v3-pill needs">{t.needs} to answer</span>}</b>
                      <span className="desk-dots" aria-label={`Stage: ${DOTS[at]}`}>
                        {DOTS.map((d, k) => <span key={d} className={k === at && t.stage !== "live" ? "now" : ""}><i className={`v3-dot ${dot(k, at, t.stage, t.needs)}`} />{d}</span>)}
                      </span>
                    </Link>
                    <Discard id={t.id} compact onDone={() => load()} />
                  </div>
                );
              })}
              <p className="desk-more"><Link to="/v3/build">Start a use case</Link> <Link to="/v3/build">Go to Build</Link></p>
            </section>

            <section aria-labelledby="h-ready">
              <div className="v3-head"><h2 id="h-ready">Ready to use</h2>{live > 0 && <span className="v3-pill done">{live} live</span>}</div>
              {note && live > 0 ? (
                <div className="v3-card">
                  <p>{note.text.split(/(?<=[.!?])\s/)[0]}</p>
                  <div className="v3-figs">
                    {note.figures.filter((f) => f.value && f.value !== "None").slice(0, 2).map((f) => (
                      <div key={f.label} className="v3-fig"><small>{f.label}</small><span className="num">{f.value}</span><small>{f.change}</small></div>
                    ))}
                  </div>
                </div>
              ) : <p className="v3-mute">Nothing is live yet. Use cases appear here once you sign them off.</p>}
              <p className="desk-more"><Link to="/v3/consume">Ask about the portfolio</Link> <Link to="/v3/consume">Go to Consume</Link></p>
            </section>
          </div>

          <p className="v3-mute desk-files">Files this month: {files.arrived} arrived, {files.recognised} recognised, {files.waiting} waiting. <Link to="/v3/build">See them</Link></p>
        </div>

        <aside className="desk-feed" aria-labelledby="h-feed">
          <h2 id="h-feed">Overnight</h2>
          {!feed.length ? <p className="v3-mute">Quiet so far.</p> : (
            <ul>{feed.map((f, i) => <li key={i}><i className="v3-dot harbor" aria-hidden="true" /><span><time>{when(f.at)}</time>{f.text.length > 110 ? `${f.text.slice(0, f.text.lastIndexOf(" ", 110))}…` : f.text}</span></li>)}</ul>
          )}
        </aside>
      </main>
    );
  };

  return <V3Frame>{body()}</V3Frame>;
}
