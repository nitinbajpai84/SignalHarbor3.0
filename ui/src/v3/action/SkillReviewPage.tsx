import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import V3Frame from "../Frame";
import { useSession } from "../../useSession";
import { admitSkill, editSkill, getSkill, rejectSkill, trySkill, when, type ListField, type SkillDetail, type TextField } from "./actionApi";
import "./action.css";

/** One line of the skill with its own edit: click the pencil, change the words, save. */
function EditLine({ label, value, onSave, busy }: { label: string; value: string; onSave: (v: string) => Promise<void>; busy: boolean }) {
  const [editing, setEditing] = useState(false);
  const [v, setV] = useState(value);
  useEffect(() => { if (!editing) setV(value); }, [value, editing]);
  return editing ? (
    <div className="rev-line">
      <textarea aria-label={`Change ${label}`} rows={2} value={v} onChange={(e) => setV(e.target.value)} autoFocus />
      <span className="v3-row">
        <button type="button" className="go" disabled={busy || !v.trim()} onClick={() => void onSave(v.trim()).then(() => setEditing(false), () => undefined)}>Save</button>
        <button type="button" onClick={() => { setV(value); setEditing(false); }}>Cancel</button>
      </span>
    </div>
  ) : (
    <div className="rev-line">
      <span>{value}</span>
      <button type="button" className="v3-pencil" aria-label={`Edit ${label}`} title="Edit" onClick={() => setEditing(true)}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" /></svg>
      </button>
    </div>
  );
}

const TEXT: [TextField, string][] = [["goal", "Goal"], ["when", "When to use"], ["inputs", "What it needs"], ["output", "What it gives"]];
const LISTS: [ListField, string][] = [["steps", "Steps"], ["checks", "Checks"], ["never", "Never does"]];

export default function SkillReviewPage() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const { user } = useSession();
  const [s, setS] = useState<SkillDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");

  const load = useCallback(() => {
    setFailed(false);
    getSkill(id).then(setS, () => setFailed(true));
  }, [id]);
  useEffect(load, [load]);

  /** Run a call and show the skill it returns. Rejects after saying so, so an editor can stay open. */
  async function run(p: Promise<SkillDetail>): Promise<SkillDetail> {
    setBusy(true);
    setProblem("");
    try {
      const r = await p;
      setS(r);
      return r;
    } catch (e) {
      setProblem("That did not go through. Try again.");
      throw e;
    } finally {
      setBusy(false);
    }
  }
  const leave = (p: Promise<SkillDetail>, to?: string) => run(p).then(() => { if (to) nav(to); }, () => undefined);

  const back = <Link to="/v3/action">&larr; Action</Link>;
  if (failed) return <V3Frame back={back}><p className="v3-err act-empty" role="alert">This skill did not load. <button type="button" onClick={load}>Try again</button></p></V3Frame>;
  if (!s) return <V3Frame back={back}><p className="v3-mute act-empty" role="status">Loading the skill...</p></V3Frame>;

  const waiting = s.status === "waiting";
  const tests = s.tests ?? [];
  const name = user?.display_name ?? "you";
  const saveText = (f: TextField) => (v: string) => run(editSkill(s.id, f, v)).then(() => undefined);
  const saveLine = (f: ListField, i: number) => (v: string) => run(editSkill(s.id, f, s[f].map((x, j) => (j === i ? v : x)))).then(() => undefined);

  return (
    <V3Frame back={back}>
      <main className="rev-main">
        <aside className="rev-left" aria-label="Why Harbor wrote it">
          <span className="act-eyebrow">Skill to review</span>
          <h1>{waiting ? "Harbor wrote a new skill: review it" : s.name}</h1>
          <div className="act-dark">
            <span className="act-h3">Why Harbor wrote it</span>
            <p>{s.why ?? "Harbor did not say why."}</p>
          </div>
          <h2 style={{ fontSize: 18 }}>The evidence</h2>
          {s.evidence?.length ? (
            <ul className="rev-ev">{s.evidence.map((e, i) => <li key={i}><span className="num v3-mute">{when(e.at)}</span>{e.text}</li>)}</ul>
          ) : <p className="v3-mute">No evidence was attached.</p>}
          <div className="v3-card">
            <span className="act-h3">What changes if you admit it</span>
            <p>{s.goal}</p>
            <p className="v3-mute">Harbor wrote this skill and tested it on known answers. It is not used on any file until you admit it.</p>
          </div>
        </aside>

        <section className="rev-doc" aria-label="The skill">
          <span className="act-eyebrow">This office · version {s.version}{s.last_changed ? ` · drafted by ${s.last_changed.by} ${when(s.last_changed.at)}` : ""}</span>
          <h1>{s.name}</h1>
          <p className="v3-mute">{waiting ? "Each line is editable. Click the pencil to change it, or just tell Harbor." : "This skill is not waiting, so it can no longer be edited here."}</p>
          {problem && <p className="v3-err" role="alert">{problem}</p>}
          {TEXT.map(([f, label]) => (
            <div className="rev-sec" key={f}>
              <h3>{label}</h3>
              {waiting ? <EditLine label={label} value={s[f]} busy={busy} onSave={saveText(f)} /> : <p>{s[f]}</p>}
            </div>
          ))}
          {LISTS.map(([f, label]) => (
            <div className="rev-sec" key={f}>
              <h3>{label}</h3>
              {s[f].length === 0 && <p className="v3-mute">None.</p>}
              {s[f].map((l, i) => waiting
                ? <EditLine key={`${f}${i}`} label={`${label} ${i + 1}`} value={l} busy={busy} onSave={saveLine(f, i)} />
                : <p key={`${f}${i}`}>{l}</p>)}
            </div>
          ))}

          <div className="rev-sec">
            <h3>Tested on known answers</h3>
            {!tests.length ? <p className="v3-mute">No tests have run yet.</p> : (
              <table className="rev-tests">
                <thead><tr><th>Notice</th><th>Expected</th><th>Harbor</th><th>Match</th></tr></thead>
                <tbody>{tests.map((t, i) => (
                  <tr key={i}><td>{t.input}</td><td className="num">{t.expected}</td><td className="num">{t.got}</td><td className={t.ok ? "good" : "bad"}>{t.ok ? "Yes" : "No"}</td></tr>
                ))}</tbody>
              </table>
            )}
          </div>

          {waiting && (
            <div className="rev-sec">
              <div className="v3-row">
                <button type="button" className="go" disabled={busy} onClick={() => void leave(admitSkill(s.id), "/v3/action")}>Admit (signs as {name}, version {s.version + 1})</button>
                <button type="button" disabled={busy} onClick={() => void leave(trySkill(s.id))}>Try it again</button>
                <button type="button" className="danger" disabled={busy} onClick={() => setRejecting(true)}>Reject</button>
              </div>
              {rejecting && (
                <div className="v3-row" role="group" aria-label="Reject this skill" style={{ marginTop: 10 }}>
                  <input aria-label="Reason (required)" placeholder="Why (required)" value={reason} onChange={(e) => setReason(e.target.value)} />
                  <button type="button" className="danger" disabled={busy || !reason.trim()} onClick={() => void leave(rejectSkill(s.id, reason.trim()), "/v3/action")}>Reject the skill</button>
                  <button type="button" onClick={() => setRejecting(false)}>Keep it</button>
                </div>
              )}
              <p className="v3-mute" style={{ marginTop: 8 }}>Admitting is recorded in Runs and proof.</p>
            </div>
          )}
        </section>
      </main>
    </V3Frame>
  );
}
