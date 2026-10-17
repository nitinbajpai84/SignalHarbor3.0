import { listDrafts, listFired, listSignals, type FiredSignal, type SignalRow } from "../api";
import DraftCard from "../action/DraftCard";
import V3Frame from "../Frame";
import { Failed, Waiting, useRead } from "../board/common";
import { fmtWhen, plainName, roleName } from "../plain";
import "../action/action.css";

/** What a signal watches, in the office's words. */
function watches(t: SignalRow["trigger"]): string {
  const what = t.kind ? plainName(t.kind).toLowerCase() : "";
  switch (t.on) {
    case "file_arrived": return `When a ${what || "file"} arrives`;
    case "action_done": return "After the step before it is done";
    case "date_passed": return "When a date goes by";
    case "schedule": return "Every day";
    case "figure_changed": return "When a figure changes";
    default: return "After each run";
  }
}
const OUTCOME: Record<FiredSignal["status"], string> = { open: "Waiting for a person", acted: "Done", dismissed: "Marked as not right" };

const Row = ({ s }: { s: SignalRow }) => {
  const { fired, acted, dismissed } = s.stats;
  const pct = (n: number) => (fired ? `${Math.round((n / fired) * 100)}%` : "0%");
  return (
    <li>
      <div><b>{s.title}</b>{s.error && <div className="v3-err">I cannot run this one yet.</div>}</div>
      <span>{watches(s.trigger)}</span>
      <span>{s.role_title || roleName(s.route_to)}</span>
      <div>
        <small>Fired {fired}, acted on {acted}, marked not right {dismissed}</small>
        <div className="sgl-bar" role="img" aria-label={`Acted on ${acted} of ${fired}, not right ${dismissed}`}><i className="a" style={{ width: pct(acted) }} /><i className="d" style={{ width: pct(dismissed) }} /></div>
      </div>
      <span className={`v3-pill ${s.suggestion ? "harbor" : "done"}`}>{s.suggestion ? "Suggested" : "Your office"}</span>
    </li>
  );
};

/** /v3/knowledge/signals: what Harbor watches for, how often it was right, and what fired lately. */
export default function SignalsPage() {
  const [lib, again] = useRead(listSignals);
  const [recent, againRecent] = useRead(() => listFired());
  const [drafts, againDrafts] = useRead(() => listDrafts("waiting"));
  return (
    <V3Frame>
      <main className="sgl-page">
        <div>
          <span className="v3-mute">Knowledge · What Harbor watches for</span>
          <h1>What Harbor watches for</h1>
          <p className="v3-mute">Each one is a thing worth catching, the person it goes to and the one thing they do. Suggested ones came with your industry; change or switch off any of them.</p>
        </div>
        {lib.state === "loading" && <Waiting what="Reading what Harbor watches for" />}
        {lib.state === "error" && <Failed message={lib.message} again={again} />}
        {lib.state === "ready" && !lib.data.length && <p className="v3-mute">Nothing is being watched yet.</p>}
        {lib.state === "ready" && lib.data.length > 0 && <ul className="sgl-list">{lib.data.map((s) => <Row key={s.id} s={s} />)}</ul>}
        {drafts.state === "ready" && drafts.data.length > 0 && (
          <section aria-labelledby="h-suggested" className="dr-section">
            <h2 id="h-suggested">Suggested by Harbor</h2>
            <p className="v3-mute">Harbor saw these done by hand more than once. Each one says how often it would have caught something in the last six months.</p>
            {drafts.data.map((d) => (
              <DraftCard key={d.id} id={d.id} noticed={d.noticed} title={d.signal.title} message={d.signal.message} backtest={d.backtest.line} needs={d.needs}
                onDone={() => { againDrafts(); again(); }} />
            ))}
          </section>
        )}
        <h2>Recently fired</h2>
        {recent.state === "loading" && <Waiting what="Reading what fired lately" />}
        {recent.state === "error" && <Failed message={recent.message} again={againRecent} />}
        {recent.state === "ready" && !recent.data.length && <p className="v3-mute">Nothing has fired yet.</p>}
        {recent.state === "ready" && recent.data.length > 0 && (
          <ul className="sgl-list sgl-recent">{recent.data.slice(0, 20).map((r) => (
            <li key={r.id}>
              <b>{r.title}</b><span>{r.subject}</span><span className="v3-mute">{fmtWhen(r.at)}</span>
              <span className={`v3-pill ${r.status === "acted" ? "done" : r.status === "open" ? "needs" : ""}`}>{OUTCOME[r.status]}{r.by ? `, ${r.by}` : ""}</span>
            </li>))}
          </ul>
        )}
      </main>
    </V3Frame>
  );
}
