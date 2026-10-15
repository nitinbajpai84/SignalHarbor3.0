import { useState } from "react";

import { apiSend } from "../api/client";
import { Button } from "../design";
import { ACTION_LABEL, P, type Action, type Proving } from "./provingCopy";
import { WordPill, fmtDate, msg } from "./WeeklyReport";
import "./proving.css";

// Spec 58 Screen C: the review. The organiser picks a way forward, the sponsor confirms (or the organiser alone where there is no sponsor).
const ORDER: Action[] = ["keep", "more_time", "send_back", "stop"];

export default function ProvingReview({ intentId, proving, onBack, onChanged }: { intentId: string; proving: Proving; onBack: () => void; onChanged: () => void }) {
  const rv = proving.review;
  const sent = rv?.sent ? rv : null;
  const [action, setAction] = useState<Action | "">(rv?.proposed ?? "");
  const [date, setDate] = useState("");
  const [reason, setReason] = useState("");
  const [learning, setLearning] = useState(rv?.learning ?? "");
  const [back, setBack] = useState(false);
  const [backWhy, setBackWhy] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const sponsor = proving.sponsor;
  const done = proving.state === "proved" || proving.state === "returned" || proving.state === "stopped";
  const base = `/api/intents/${intentId}/proving/review`;

  const ready = action === "keep" || (action === "more_time" && !!date && !!reason.trim()) || (action === "send_back" && !!learning.trim()) || (action === "stop" && !!reason.trim());
  async function run(f: () => Promise<unknown>) {
    setBusy(true); setErr("");
    try { await f(); onChanged(); } catch (x) { setErr(msg(x)); } finally { setBusy(false); }
  }
  const choose = () => run(async () => {
    await apiSend("POST", base, { action, date: action === "more_time" ? date : null, reason: reason.trim() || null, learning: action === "send_back" ? learning.trim() : null });
  });

  return (
    <section className="pv" aria-label={P.review.title}>
      <div className="pv__row"><Button onClick={onBack}>{P.back}</Button><h2>{P.review.title}</h2></div>
      <div className="pv__cols">
        <div className="pv__main">
          <div className="pv__card ds-card">
            <h3>{P.review.summary}</h3>
            {rv && rv.verdicts.length > 0 ? (
              <>
                <ul className="pv__list">{rv.verdicts.map((v, i) => <li key={i}><WordPill w={v} /></li>)}</ul>
                <p style={{ margin: 0 }}>{rv.summary}</p>
              </>
            ) : <p className="pv__soft">{P.review.none}</p>}
            <p className="pv__soft">Drafted by North, a suggestion for you to decide.</p>
          </div>
        </div>
        <div className="pv__aside">
          {done ? <p className="pv__card ds-card" role="status">{proving.state === "proved" ? P.chip.proved : proving.state === "returned" ? P.chip.returned : P.chip.stopped}</p>
            : sent && proving.can.confirm_review ? (
              <div className="pv__card ds-card">
                <p style={{ margin: 0 }}>{P.review.chosen(sent.by ?? "The organiser")}</p>
                <p style={{ margin: 0 }}><strong>{sent.action ? ACTION_LABEL[sent.action] : ""}</strong>{sent.review_date ? `, until ${fmtDate(sent.review_date)}` : ""}</p>
                {sent.reason && <p className="pv__soft">{sent.reason}</p>}
                {sent.learning && <p className="pv__soft">{sent.learning}</p>}
                {back && (
                  <label className="pv__field">{P.review.returnReason}<textarea value={backWhy} onChange={(e) => setBackWhy(e.target.value)} /></label>
                )}
                {err && <p className="pv__err" role="alert">{err}</p>}
                <div className="pv__bar">
                  {!back && <Button variant="primary" disabled={busy} onClick={() => void run(() => apiSend("POST", `${base}/confirm`, {}))}>{P.review.confirm}</Button>}
                  {!back ? <Button onClick={() => setBack(true)}>{P.review.returnTo(proving.organiser ?? "the organiser")}</Button>
                    : <Button variant="primary" disabled={busy || !backWhy.trim()} onClick={() => void run(() => apiSend("POST", `${base}/confirm`, { return: true, reason: backWhy.trim() }))}>{P.review.returnTo(proving.organiser ?? "the organiser")}</Button>}
                </div>
              </div>
            ) : sent ? <p className="pv__card ds-card" role="status">{P.review.sentTo(sponsor ?? "the sponsor")}</p>
              : proving.can.review ? (
                <form className="pv__card ds-card" aria-label={P.review.pick} onSubmit={(e) => { e.preventDefault(); if (ready) void choose(); }}>
                  <h3>{P.review.pick}</h3>
                  {rv?.returned && <p className="pv__soft">{P.review.returnedBy(rv.returned.by, rv.returned.reason)}</p>}
                  <div className="pv__radio" role="radiogroup" aria-label={P.review.pick}>
                    {ORDER.map((a) => (
                      <div key={a} className="pv__radio">
                        <label><input type="radio" name="action" checked={action === a} onChange={() => setAction(a)} /> {ACTION_LABEL[a]}{rv?.proposed === a ? <span className="pv__soft"> ({P.review.proposed})</span> : null}</label>
                        {action === a && a === "more_time" && (<><label className="pv__field">{P.review.newDate}<input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label><label className="pv__field">{P.review.reason}<textarea value={reason} onChange={(e) => setReason(e.target.value)} /></label></>)}
                        {action === a && a === "send_back" && <label className="pv__field">{P.review.learning}<span className="pv__soft">{P.review.learningHint}</span><textarea value={learning} onChange={(e) => setLearning(e.target.value)} /></label>}
                        {action === a && a === "stop" && <label className="pv__field">{P.review.reason}<textarea value={reason} onChange={(e) => setReason(e.target.value)} /></label>}
                      </div>
                    ))}
                  </div>
                  {!ready && <p className="pv__soft">{P.review.needs}</p>}
                  {err && <p className="pv__err" role="alert">{err}</p>}
                  <div className="pv__bar pv__bar--sticky"><Button variant="primary" type="submit" disabled={!ready || busy}>{sponsor ? P.review.send(sponsor) : P.review.confirm}</Button></div>
                </form>
              ) : <p className="pv__card ds-card" role="status">{P.review.notYet}</p>}
        </div>
      </div>
    </section>
  );
}
