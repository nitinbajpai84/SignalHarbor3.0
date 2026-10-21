import { useState } from "react";

import { resolveReview, type ReviewItem } from "../api";

/** "Check what I read": the field, Harbor's reading, the page and the quoted line, and Confirm or Correct. */
export default function ReviewCard({ item, onDone }: { item: ReviewItem; onDone: () => void }) {
  const [fix, setFix] = useState(false);
  const [text, setText] = useState(item.reading);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");

  async function run(value?: string) {
    setBusy(true);
    setProblem("");
    try {
      await resolveReview(item.id, value);
      onDone();
    } catch (e) {
      setProblem(e instanceof Error && e.message ? e.message : "That did not go through. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="sg-card needs dr-card" aria-label={`Check ${item.field}`}>
      <div className="v3-head"><span className="v3-kicker">Check what I read</span></div>
      <b className="act-title">{item.field}</b>
      <p>I read <b>{item.reading}{item.currency ? ` ${item.currency}` : ""}</b>, and I am not sure ({item.confidence} confidence).</p>
      <p className="v3-mute">{item.document ? `${item.document}, ` : ""}{item.page ? `page ${item.page}` : "page not known"}{item.line ? `, line ${item.line}` : ""}</p>
      {item.quote && <blockquote className="dr-test">{item.quote}</blockquote>}
      {problem && <p className="v3-err" role="alert">{problem}</p>}
      {fix ? (
        <div className="sg-note">
          <label>The right value<input value={text} onChange={(e) => setText(e.target.value)} /></label>
          <div className="v3-row">
            <button type="button" className="go" disabled={busy || !text.trim()} onClick={() => void run(text)}>Save the correction</button>
            <button type="button" disabled={busy} onClick={() => setFix(false)}>Cancel</button>
          </div>
        </div>
      ) : (
        <div className="v3-row">
          <button type="button" className="go" disabled={busy} onClick={() => void run()}>Confirm</button>
          <button type="button" disabled={busy} onClick={() => setFix(true)}>Correct</button>
        </div>
      )}
    </article>
  );
}
