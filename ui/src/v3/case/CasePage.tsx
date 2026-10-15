import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import V3Frame from "../Frame";
import { getCase } from "../api";
import { actOnCase, askAboutCase, type CaseAnswer, type CaseView } from "./caseApi";
import "./case.css";

const say = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong. Please try again.");
const when = (at: string) => {
  const d = new Date(at);
  return Number.isNaN(d.getTime()) ? at : d.toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
};
const money = (c: CaseView) => (c.amount != null ? `${c.currency ?? ""} ${c.amount.toLocaleString("en-GB")}`.trim() : "Not available yet");

/** One case: what happened, the evidence side by side, Harbor's suggested steps (an email is only drafted), a short talk box, history, close with a reason. */
export default function CasePage() {
  const { id = "" } = useParams();
  const [c, setC] = useState<CaseView | null>(null);
  const [err, setErr] = useState("");
  const [step, setStep] = useState<CaseAnswer | null>(null);
  const [body, setBody] = useState<string | null>(null); // the draft text while it is being edited
  const [note, setNote] = useState("");
  const [reason, setReason] = useState("");
  const [q, setQ] = useState("");
  const [talk, setTalk] = useState<{ me: string; harbor: string }[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    getCase(id).then((x) => live && setC(x as CaseView), (e: unknown) => live && setErr(say(e)));
    return () => { live = false; };
  }, [id]);

  const act = useCallback(async (answer: CaseAnswer, why?: string) => {
    setBusy(true); setErr("");
    try {
      setC(await actOnCase(id, answer, why));
      setStep(null); setBody(null); setNote(""); setReason("");
    } catch (e) { setErr(say(e)); } finally { setBusy(false); }
  }, [id]);

  const ask = async (e: FormEvent) => {
    e.preventDefault();
    const me = q.trim();
    if (!me) return;
    setBusy(true); setErr("");
    try {
      const r = await askAboutCase(id, me);
      setTalk((t) => [...t, { me, harbor: r.answer ?? r.summary }]);
      setQ("");
    } catch (x) { setErr(say(x)); } finally { setBusy(false); }
  };

  if (!c) return <V3Frame><main className="case-main">{err ? <p className="v3-err" role="alert">{err}</p> : <p className="v3-mute">Opening the case.</p>}</main></V3Frame>;
  const have = c.evidence.filter((x) => x.side !== "missing");
  const missing = c.evidence.filter((x) => x.side === "missing");
  const closed = c.closed ?? c.status === "closed";
  const closeBtn = (answer: CaseAnswer, label: string) =>
    <button type="button" disabled={busy || !reason.trim()} onClick={() => void act(answer, reason.trim())}>{label}</button>;

  return (
    <V3Frame>
      <section className="case-head" aria-labelledby="h-case">
        <div className="v3-head">
          <div>
            <span className="v3-kicker">Exception{c.number ? ` · ${c.number}` : ""}</span>
            <h1 id="h-case">{c.title}</h1>
          </div>
          {c.thread && <Link to={`/v3/thread/${encodeURIComponent(c.thread)}`}>From the thread</Link>}
        </div>
        <dl className="case-facts">
          <div><dt>Status</dt><dd><span className={`case-pill${closed ? " done" : ""}`}>{closed ? "Closed" : "Open"}</span></dd></div>
          <div><dt>Owner</dt><dd>{c.owner || "Not assigned yet"}</dd></div>
          <div><dt>Due</dt><dd className="num">{c.due || "Not set"}</dd></div>
          <div><dt>Amount at stake</dt><dd className="num">{money(c)}</dd></div>
        </dl>
      </section>
      {err && <p className="v3-err case-err" role="alert">{err}</p>}

      <main className="case-main">
        <div className="case-left">
          <section className="case-sec what" aria-labelledby="h-what"><h2 id="h-what">What happened</h2><p>{c.what}</p></section>

          <section aria-labelledby="h-ev" className="v3-col">
            <h2 id="h-ev">Evidence</h2>
            <div className="case-ev">
              <article aria-label="What we have">
                <small>We have it</small>
                {have.length ? have.map((x, i) => <div key={i}><b>{x.source}</b><br />{x.row}</div>) : <span className="v3-mute">Nothing recorded yet.</span>}
              </article>
              <article className="miss" aria-label="What is not there">
                <small>Not there</small>
                {missing.length ? missing.map((x, i) => <div key={i}>{x.row}</div>) : <span className="v3-mute">Nothing is missing that Harbor knows of.</span>}
              </article>
            </div>
          </section>

          {!closed && c.steps.length > 0 && (
            <section className="case-sec" aria-labelledby="h-next">
              <h2 id="h-next">Harbor's suggested next steps</h2>
              <div className="v3-row">
                {c.steps.map((s) => (
                  <button key={s.answer} type="button" className={step === s.answer ? "go" : ""} aria-pressed={step === s.answer}
                    onClick={() => setStep(s.answer as CaseAnswer)}>{s.label}</button>
                ))}
              </div>
              {step === "ask" && c.draft && (
                <>
                  <article className="case-draft" aria-label="Drafted email to the administrator">
                    <span className="v3-mute">This is a draft. Harbor does not send it; keep it on the case and send it yourself.</span>
                    <p><b>To:</b> {c.draft.to}</p>
                    <p><b>Subject:</b> {c.draft.subject}</p>
                    {body === null ? <p>{c.draft.body}</p>
                      : <textarea aria-label="Edit the draft" rows={6} value={body} onChange={(e) => setBody(e.target.value)} />}
                  </article>
                  <div className="v3-row">
                    <button type="button" className="go" disabled={busy} onClick={() => void act("ask", body ?? c.draft?.body)}>OK, keep this draft</button>
                    <button type="button" onClick={() => setBody(body === null ? c.draft?.body ?? "" : null)}>{body === null ? "Edit first" : "Stop editing"}</button>
                    <span className="v3-mute">Needs your OK.</span>
                  </div>
                </>
              )}
              {step === "timing" && (
                <div className="v3-row">
                  <button type="button" className="go" disabled={busy} onClick={() => void act("timing")}>OK, close as timing</button>
                  <span className="v3-mute">Closes the case: a timing difference that clears by itself.</span>
                </div>
              )}
              {step === "note" && (
                <div className="v3-row">
                  <input aria-label="Note" placeholder="What will be corrected?" value={note} onChange={(e) => setNote(e.target.value)} />
                  <button type="button" className="go" disabled={busy || !note.trim()} onClick={() => void act("note", note.trim())}>Save note</button>
                </div>
              )}
            </section>
          )}
        </div>

        <aside className="case-side">
          <section className="case-sec" aria-labelledby="h-ask">
            <h2 id="h-ask">Ask Harbor about this case</h2>
            <div className="case-chat">
              {talk.map((t, i) => <div key={i} className="case-chat"><p className="me">{t.me}</p><p>{t.harbor}</p></div>)}
            </div>
            <form className="v3-row" onSubmit={(e) => void ask(e)}>
              <input aria-label="Ask Harbor about this case" placeholder="Ask about this case…" value={q} onChange={(e) => setQ(e.target.value)} />
              <button type="submit" className="go" disabled={busy || !q.trim()}>Ask</button>
            </form>
          </section>

          <section className="case-sec" aria-labelledby="h-hist">
            <h2 id="h-hist">History</h2>
            <ol className="case-hist">{c.history.map((h, i) => <li key={i}><span className="num">{when(h.at)}</span> · {h.text}</li>)}</ol>
          </section>

          {!closed && (
            <section className="case-close" aria-labelledby="h-close">
              <h2 id="h-close">Close this case</h2>
              <label htmlFor="reason">Reason (required)</label>
              <input id="reason" required aria-required="true" placeholder="Say why this case is closing" value={reason} onChange={(e) => setReason(e.target.value)} />
              <div className="v3-row">{closeBtn("resolved", "Resolved")}{closeBtn("timing", "Timing")}{closeBtn("dismiss", "Not an exception")}</div>
              <small>Enter a reason to enable closing. Closed cases stay in History.</small>
            </section>
          )}
        </aside>
      </main>
    </V3Frame>
  );
}
