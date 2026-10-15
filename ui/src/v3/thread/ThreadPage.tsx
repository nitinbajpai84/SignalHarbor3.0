import { useCallback, useEffect, useRef, useState, type PointerEvent as RPointerEvent, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { decide, editBrief, sendForSignature, getThread, say, type Event, type Thread, type ThreadRecord } from "../api";
import { EditLine } from "../build/IntentGraph";
import "../build/build.css";
import V3Frame from "../Frame";
import Discard from "./Discard";
import { SignNote, signAction } from "./SignOff";
import { MicButton, combineText } from "../../v1/voice";

const POLL_MS = 3000;

function level(c: number | string): string {
  return typeof c === "number" ? (c >= 0.8 ? "high" : c >= 0.5 ? "medium" : "low") : c;
}

/** The working steps are the chips Harbor has shown so far; the last one is still running. */
export function workingSteps(events: Event[]): string[] {
  return events.flatMap((e) => (e.kind === "chips" ? e.chips ?? [] : []));
}

/** "14 Oct, 06:00" in the reader's own time; the raw value when it is not a date. */
export function when(at?: string): string {
  const d = at ? new Date(at) : null;
  return d && !Number.isNaN(d.getTime())
    ? d.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
    : at ?? "";
}

/** Who started this, who confirmed and signed it, when, which version: what an auditor asks for, with the signed document. */
function RecordCard({ r, startedBy, startedAt }: { r?: ThreadRecord | null; startedBy?: string | null; startedAt?: string }) {
  return (
    <div className={`v3-card v3-record${r?.signed_by ? " signed" : ""}`}>
      <span className="v3-kicker">The record</span>
      <dl>
        <dt>Raised by</dt><dd>{r?.started_by ?? startedBy ?? "You"}{(r?.started_at ?? startedAt) && <> · {when(r?.started_at ?? startedAt)}</>}</dd>
        {r?.sent_at && <><dt>Sent to the signer</dt><dd>{when(r.sent_at)}</dd></>}
        {r?.signed_by ? (
          <><dt>Confirmed and signed by</dt><dd><span className="v3-pill done">Signed</span> {r.signed_by}{r.role && ` (${({ raiser: "raised it", sponsor: "sponsor", company_admin: "office admin" } as Record<string, string>)[r.role] ?? r.role})`} · {when(r.signed_at)}</dd>
            <dt>Version</dt><dd>{r.version ?? 1}</dd></>
        ) : (
          <><dt>Signed</dt><dd className="v3-mute">Not yet. Your Confirm on Decision 1 signs the intent in your name, with the time.</dd></>
        )}
      </dl>
      {r?.document && <a href={r.document}>Download the signed intent document (Word)</a>}
    </div>
  );
}

/** One line of the conversation: the person in navy, Harbor in brass, a question in amber, a finished decision in green. */
export function Row({ ev }: { ev: Event }) {
  const who = ev.kind === "person" ? "me" : ev.kind === "question" ? "needs" : ev.kind === "decision_done" ? "done" : "harbor";
  const mark = ev.kind === "person" ? (ev.by ?? "You").slice(0, 1) : ev.kind === "question" ? "?" : ev.kind === "decision_done" ? "\u2713" : "H";
  return (
    <li className={`v3-ev b3-ev ${who}`}>
      <div className="v3-rail">
        {ev.kind === "chips" ? <span className="v3-dot harbor" /> : <span className={`v3-av ${who === "me" ? "person" : who}`}>{mark}</span>}
      </div>
      <div className="v3-body">
        {ev.kind !== "chips" && <small className="v3-mute">{ev.kind === "person" ? ev.by ?? "You" : "Harbor"} · {when(ev.at)}</small>}
        {ev.kind === "chips" ? (
          <div className="v3-chips">{(ev.chips ?? []).map((c0, i) => <span key={i}>{c0}</span>)}</div>
        ) : (
          ev.text && <p className={`v3-bubble b3-bubble ${who}`}>{ev.text}</p>
        )}
      </div>
    </li>
  );
}

const WIDTH_KEY = "v3.thread.talkWidth";
const clampW = (w: number) => Math.min(Math.max(w, 320), Math.max(320, window.innerWidth - 480));

/** The handle between the conversation and the brief: drag it, or focus it and use the arrow keys. The width is remembered per browser. */
function useSplit(): [number | null, ReactNode] {
  const [w, setW] = useState<number | null>(() => {
    try { const v = Number(localStorage.getItem(WIDTH_KEY)); return v > 0 ? v : null; } catch { return null; }
  });
  const keep = (v: number) => { const c = clampW(v); setW(c); try { localStorage.setItem(WIDTH_KEY, String(c)); } catch { /* the width just is not remembered */ } };
  const startDrag = (e: RPointerEvent<HTMLDivElement>) => {
    const talk = (e.currentTarget.previousElementSibling as HTMLElement | null);
    const left = talk?.getBoundingClientRect().left ?? 0;
    const move = (ev: PointerEvent) => keep(ev.clientX - left);
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); document.body.style.userSelect = ""; };
    document.body.style.userSelect = "none";
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  const handle = (
    <div
      className="v3-split"
      role="separator"
      aria-orientation="vertical"
      aria-label="Drag to change the width of the conversation and the brief"
      aria-valuenow={w ?? undefined}
      tabIndex={0}
      title="Drag to resize"
      onPointerDown={startDrag}
      onDoubleClick={() => { setW(null); try { localStorage.removeItem(WIDTH_KEY); } catch { /* nothing kept */ } }}
      onKeyDown={(e) => {
        const cur = w ?? (e.currentTarget.previousElementSibling as HTMLElement | null)?.getBoundingClientRect().width ?? 560;
        if (e.key === "ArrowLeft") { e.preventDefault(); keep(cur - 40); }
        if (e.key === "ArrowRight") { e.preventDefault(); keep(cur + 40); }
      }}
    />
  );
  return [w, handle];
}

export default function ThreadPage() {
  const { id = "" } = useParams();
  const [t, setT] = useState<Thread | null>(null);
  const [err, setErr] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [picked, setPicked] = useState<Record<string, string>>({});
  const composer = useRef<HTMLTextAreaElement>(null);
  const [talkW, splitter] = useSplit();

  const load = useCallback(
    () => getThread(id).then((r) => { setT(r); setErr(null); }).catch((e: Error) => setErr(e)),
    [id],
  );
  useEffect(() => { void load(); }, [load]);

  const stage = t?.stage;
  useEffect(() => {
    if (stage !== "working" && stage !== "drafting") return;
    const h = setInterval(() => { void load(); }, POLL_MS);
    return () => clearInterval(h);
  }, [stage, load]);

  const run = (p: Promise<Thread>) => {
    setBusy(true);
    return p.then((r) => { setT(r); setErr(null); }).catch((e: Error) => setErr(e)).finally(() => setBusy(false));
  };

  if (!t) {
    const gone = err instanceof ApiError && err.status === 404;
    return (
      <V3Frame>
        <div className="v3-main">
          {err ? (
            <div className="v3-card">
              <p>{gone ? "I could not find this thread. It may have been removed." : err.message}</p>
              <div className="v3-row">
                {!gone && <button onClick={() => void load()}>Try again</button>}
                <Link to="/v3/desk">Back to the Desk</Link>
              </div>
            </div>
          ) : (
            <p className="v3-mute" role="status">Loading...</p>
          )}
        </div>
      </V3Frame>
    );
  }

  const d = t.decision;
  const qs = d?.questions ?? [];
  const value = (q: { id: string; assumed?: string }) => picked[q.id] ?? q.assumed;
  const answers = Object.fromEntries(qs.flatMap((q) => { const v = value(q); return v ? [[q.id, v]] : []; }));
  const open = qs.filter((q) => !value(q)).length;
  const steps = workingSteps(t.events);
  const lastQuestion = [...t.events].reverse().find((e) => e.kind === "question")?.text;

  let panel: ReactNode = null;
  const updating = t.stage === "drafting" && !!d?.brief;  // a reply is being worked in: the brief stays on screen, marked as updating
  if (t.stage === "drafting" && !updating) {
    panel = (
      <div className="v3-card" role="status">
        <p>Harbor is reading what you wrote...</p>
        <small className="v3-mute">This usually takes a moment.</small>
      </div>
    );
  } else if ((t.stage === "decision1" || updating) && d?.brief) {
    const b = d.brief;
    panel = (
      <div className="v3-dec">
        <span className="v3-kicker">Decision 1 · Is this what you want?</span>
        {updating && <p className="v3-updating" role="status">Updating the brief with what you just said. Changed lines will be marked.</p>}
        {b.doc?.length ? (
          b.doc.map((g) => (
            <section key={g.title} className="v3-bgroup">
              <h3>{g.title}</h3>
              <dl>{g.lines.map((l) => (
                <EditLine key={`${l.section}.${l.index}.${l.field}`} line={l} busy={busy} onSave={(v) => run(editBrief(id, l, v))} />
              ))}</dl>
            </section>
          ))
        ) : (
          <dl>
            <dt>The question</dt><dd>{b.question}</dd>
            <dt>Files</dt><dd>{b.files.join(" · ")}</dd>
            <dt>Read by</dt><dd>{b.read_by}</dd>
            <dt>Refresh</dt><dd>{b.refresh}</dd>
            <dt>Raise a case when</dt><dd>{b.cases_when}</dd>
          </dl>
        )}
        {d.gaps?.length ? <p className="v3-gap">Still needed before you confirm: {d.gaps.join("; ")}.</p> : null}
        <SignNote s={t.signoff} />
        <div className="v3-row">
          {signAction(t.signoff, "Confirm", busy || updating, () => void run(decide(id, 1, "confirm")), () => void run(sendForSignature(id)))}
          <button onClick={() => composer.current?.focus()}>Change something</button>
        </div>
        <small className="v3-mute">or just say it, for example "use 90 days"</small>
      </div>
    );
  } else if (t.stage === "working") {
    panel = (
      <div className="v3-card">
        <span className="v3-kicker b3-harborkick">Harbor is working</span>
        <ol aria-label="Working steps" className="b3-steps">
          {steps.map((s0, i) => (
            <li key={i} className={i === steps.length - 1 ? "harbor" : "done"}>{s0} <small className="v3-mute">{i === steps.length - 1 ? "Now" : "Done"}</small></li>
          ))}
        </ol>
        <p className="v3-mute">Nothing needed from you. Harbor will tell you on the Desk.</p>
        <div className="v3-row">
          <button disabled={busy} onClick={() => void run(say(id, "Stop"))}>Stop</button>
          <Link to={`/v3/trust/workbench?thread=${encodeURIComponent(id)}`}>See the technical detail</Link>
        </div>
      </div>
    );
  } else if (t.stage === "decision2" && d) {
    panel = (
      <div className="v3-dec">
        <span className="v3-kicker">Decision 2 · {d.title || "Here is what I understood"}</span>
        <ul style={{ listStyle: "none", margin: 0, padding: 0, minWidth: 0 }}>
          {(d.files ?? []).map((f) => (
            <li key={f.name} style={{ borderTop: "1px solid var(--line)", padding: "10px 0", minWidth: 0, overflowWrap: "anywhere" }}>
              <div><span style={{ fontWeight: 600 }}>{f.name}</span> <small className="v3-mute">→ {f.goes_to} ({f.state})</small></div>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, fontSize: 14 }}>
                <span>read as {f.read_as}</span>
                <span className={`v3-pill ${level(f.confidence) === "high" ? "done" : "needs"}`}>{level(f.confidence)}</span>
              </div>
            </li>
          ))}
        </ul>
        {qs.length > 0 && <b>{qs.length === 1 ? "One thing I am not sure about" : `${qs.length} things I am not sure about`}</b>}
        {qs.map((q) => (
          <div key={q.id} className="v3-col" style={{ gap: 8 }}>
            <span>{q.text}</span>
            <div className="v3-row">
              {q.options.map((o) => (
                <button key={o} className={value(q) === o ? "go" : undefined} aria-pressed={value(q) === o} onClick={() => setPicked({ ...picked, [q.id]: o })}>{o}</button>
              ))}
            </div>
            {q.assumed && <small className="v3-mute">I have assumed {q.assumed}; change it if I am wrong.</small>}
          </div>
        ))}
        {d.summary && <p className="v3-mute">{d.summary}</p>}
        <div className="v3-row">
          <button className="go" disabled={busy || open > 0} onClick={() => void run(decide(id, 2, "carry_on", answers))}>This is right, carry on</button>
          <button onClick={() => composer.current?.focus()}>Something is off</button>
          {open > 0 && <small className="v3-mute">{open} answer{open > 1 ? "s" : ""} needed</small>}
        </div>
      </div>
    );
  } else if (t.stage === "decision3" && d) {
    panel = (
      <div className="v3-dec open3">
        <span className="v3-kicker">Decision 3 · {d.title || "Numbers match. Go live?"}</span>
        <table className="b3-checks">
          <thead><tr style={{ textAlign: "left" }}><th>Figure</th><th>Value</th><th>Result</th></tr></thead>
          <tbody>
            {(d.checks ?? []).map((c) => (
              <tr key={c.label} className={c.ok ? undefined : "bad"}>
                <td>{c.label}{c.note && <small className="v3-mute" style={{ display: "block" }}>{c.note}</small>}</td>
                <td className="num">{c.value}</td>
                <td><span className={`v3-pill ${c.ok ? "done" : "problem"}`}>{c.ok ? "Match" : "Needs a look"}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
        {d.summary && <p className="v3-mute">{d.summary}</p>}
        {d.sop && <p><a href={d.sop.download.docx}>Download the procedure (Word)</a> · <a href={d.sop.download.md}>Markdown</a></p>}
        <div className="v3-row">
          <button className="go" disabled={busy} onClick={() => void run(decide(id, 3, "go_live"))}>Go live</button>
          <button disabled={busy} onClick={() => void run(decide(id, 3, "not_yet"))}>Not yet</button>
        </div>
      </div>
    );
  } else if (t.stage === "live") {
    panel = (
      <div className="v3-card b3-live">
        <span className="v3-pill done">Live</span>
        <p>{t.process ? `${t.process.title}: ${t.process.steps} steps, kept here as a document.` : t.next_run ? `Next run: ${t.next_run}` : "Runs on its own when the next files arrive."}</p>
        {t.process && <p><a href={t.process.download.docx}>Download the procedure (Word)</a> · <a href={t.process.download.md}>Markdown</a></p>}
        <div className="v3-row"><Link to="/v3/board">Board</Link><Link to="/v3/files">Files</Link></div>
      </div>
    );
  } else if (t.stage === "question") {
    panel = (
      <div className="v3-card need">
        <span className="v3-kicker">A question for you</span>
        <p>{lastQuestion ?? "Harbor needs something from you."}</p>
        <div className="v3-row">
          <button className="go" disabled={busy} onClick={() => void run(decide(id, d?.n ?? 1, "retry"))}>Retry</button>
        </div>
      </div>
    );
  }

  const send = () => {
    const s = text.trim();
    if (s) void run(say(id, s).then((r) => { setText(""); return r; }));
  };

  return (
    <V3Frame back={<Link to="/v3/desk" className="b3-back">&larr; Desk</Link>}>
      <div className="v3-main b3">
        <section className="v3-talk" style={talkW ? { flex: `0 0 ${talkW}px`, maxWidth: "none" } : undefined}>
          <div className="v3-row b3-titlerow">
            <h1>{t.title}</h1>
            {t.stage !== "live" && t.stage !== "discarded" && <Discard id={id} onDone={(r) => setT(r)} />}
          </div>
          {t.stage === "discarded" && <p className="v3-updating" role="status">This thread was discarded. It is kept for the record. <Link to="/v3/desk">Start a new one from the Desk</Link>.</p>}
          <ul className="v3-tl">{t.events.map((e, i) => <Row key={i} ev={e} />)}</ul>
          {err && <p className="v3-err" role="alert">{err.message}</p>}
          <div className="v3-compose">
            <textarea
              ref={composer}
              aria-label="Say something to Harbor"
              rows={2}
              placeholder="Say something to Harbor"
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            />
            <MicButton agent="Harbor" disabled={busy} onText={(said) => setText((t0) => combineText(t0, said))} />
            <button className="go" disabled={busy || !text.trim()} onClick={send}>Send</button>
          </div>
        </section>
        {splitter}
        <aside className="v3-side" aria-label="Where this thread stands">
          {panel}
          <RecordCard r={t.record} startedBy={t.started_by} startedAt={t.events[0]?.at} />
        </aside>
      </div>
    </V3Frame>
  );
}
