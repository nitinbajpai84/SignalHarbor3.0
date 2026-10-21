import { useState } from "react";

import { admitDraft, editDraft, rejectDraft } from "../api";

/** What Harbor noticed, what the drafted signal would say, how often it would have fired, and Admit / Edit / Reject. */
export default function DraftCard({ id, noticed, title, message, preview, backtest, needs, onDone }: {
  id: string; noticed: string; title: string; message: string; preview?: string; backtest: string; needs: string[]; onDone: () => void;
}) {
  const [edit, setEdit] = useState(false);
  const [text, setText] = useState(message);
  const [name, setName] = useState(title);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");

  async function run(go: () => Promise<unknown>) {
    setBusy(true);
    setProblem("");
    try {
      await go();
      onDone();
    } catch (e) {
      setProblem(e instanceof Error && e.message ? e.message : "That did not go through. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="sg-card needs dr-card" aria-label={title}>
      <div className="v3-head"><span className="v3-kicker">Harbor noticed a pattern</span></div>
      <b className="act-title">{noticed}</b>
      <p className="v3-mute">{title}</p>
      {!edit && <p>{preview ?? message}</p>}
      <p className="dr-test">{backtest}</p>
      {needs.map((n) => <p key={n} className="dr-ask" role="status">{n}</p>)}
      {problem && <p className="v3-err" role="alert">{problem}</p>}
      {edit ? (
        <div className="sg-note">
          <label>What it is called<input value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label>What the card says<textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} /></label>
          <div className="v3-row">
            <button type="button" className="go" disabled={busy || !name.trim() || !text.trim()}
              onClick={() => void run(async () => { await editDraft(id, { title: name, message: text }); setEdit(false); })}>Save</button>
            <button type="button" disabled={busy} onClick={() => { setEdit(false); setText(message); setName(title); }}>Cancel</button>
          </div>
        </div>
      ) : (
        <div className="v3-row">
          <button type="button" className="go" disabled={busy} onClick={() => void run(() => admitDraft(id))}>Admit</button>
          <button type="button" disabled={busy} onClick={() => setEdit(true)}>Edit</button>
          <button type="button" disabled={busy} onClick={() => void run(() => rejectDraft(id))}>Reject</button>
        </div>
      )}
    </article>
  );
}
