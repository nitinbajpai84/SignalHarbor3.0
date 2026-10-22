import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent as RPointerEvent, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { MicButton, combineText } from "../../v1/voice";
import {
  decide, editBrief, getThread, listThreads, say, sendForSignature, startThread,
  type BriefLine, type FileRow, type Stage, type Thread, type ThreadRecord, type ThreadSummary,
} from "../api";
import AssumptionsCard from "../thread/AssumptionsCard";
import FigureChecks from "../thread/FigureChecks";
import QuestionBlock from "../thread/QuestionBlock";
import V3Frame from "../Frame";
import Discard from "../thread/Discard";
import { OpenQuestions, SignNote, confirmWhy, gapLine, openComposer, signAction } from "../thread/SignOff";
import { Row } from "../thread/ThreadPage";
import RoleSuggest from "../desk/RoleSuggest";
import DropBand from "./DropBand";
import IntentGraph, { BriefList } from "./IntentGraph";
import { getSow, type SowView } from "../../v1/i4/api";
import Swimlane from "../../v1/i6/Swimlane";
import "./build.css";

const POLL_MS = 3000;
/** Thread.now arrives while Harbor drafts or works (spec, 15 Oct). */
type BuildThread = Thread & { now?: { skill: string; name: string; text: string } | null };

const STEPS = ["Brief", "Understanding", "Numbers", "Live"] as const;
const stepOf = (t: BuildThread): number =>
  t.stage === "live" ? 3 : t.stage === "decision3" ? 2 : t.stage === "working" || t.stage === "decision2" ? 1
    : t.stage === "question" ? Math.max(0, (t.decision?.n ?? 1) - 1) : 0;

const when = (at?: string) => {
  const d = at ? new Date(at) : null;
  return d && !Number.isNaN(d.getTime()) ? d.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : at ?? "";
};
const level = (c: number | string) => (typeof c === "number" ? (c >= 0.8 ? "high" : c >= 0.5 ? "medium" : "low") : c);
const WAITS: Stage[] = ["decision1", "decision2", "decision3", "question"];

/** Reached = done; the current stage is needs when it waits for you, harbor while Harbor works; not reached = info. */
export function stepClass(t: { stage: Stage }, i: number, step: number): "done" | "needs" | "harbor" | "info" {
  if (t.stage === "live" || i < step) return "done";
  if (i > step) return "info";
  return WAITS.includes(t.stage) ? "needs" : "harbor";
}

/** True below 720px wide; false where there is no matchMedia (tests). */
function usePhone(): boolean {
  const q = "(max-width: 719px)";
  const [on, setOn] = useState(() => typeof window !== "undefined" && !!window.matchMedia?.(q).matches);
  useEffect(() => {
    const m = window.matchMedia?.(q);
    if (!m) return;
    const f = () => setOn(m.matches);
    m.addEventListener("change", f);
    return () => m.removeEventListener("change", f);
  }, []);
  return on;
}

// ---- the board: /v3/build -----------------------------------------------------------------------------------------------------

const BOARD: { title: string; stages: Stage[] }[] = [
  { title: "Brief", stages: ["drafting", "decision1"] },
  { title: "Understanding", stages: ["working", "decision2", "question"] },
  { title: "Numbers", stages: ["decision3"] },
  { title: "Live", stages: ["live"] },
];

function Start() {
  const nav = useNavigate();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const go = () => {
    const s = text.trim();
    if (!s) return;
    setBusy(true);
    startThread(s).then((t) => nav(`/v3/build/${encodeURIComponent(t.id)}`)).catch((e: Error) => { setErr(e.message); setBusy(false); });
  };
  return (
    <section aria-label="Start a use case">
      <h2>Start a use case</h2>
      <div className="b3-start">
        <textarea
          aria-label="Say what you want to know"
          rows={2}
          placeholder="Say what you want to know, in your own words"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); go(); } }}
        />
        <MicButton agent="Harbor" disabled={busy} onText={(said) => setText((t0) => combineText(t0, said))} />
        <button className="go" disabled={busy || !text.trim()} onClick={go}>Start</button>
      </div>
      {err && <p className="v3-err" role="alert">{err}</p>}
    </section>
  );
}

function Board() {
  const [rows, setRows] = useState<ThreadSummary[] | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => { listThreads().then((r) => { setRows(r.threads); setErr(""); }).catch((e: Error) => setErr(e.message)); }, []);
  useEffect(() => { load(); }, [load]);
  return (
    <V3Frame>
      <main className="b3-board b3">
        <div>
          <h1>Use cases</h1>
          <p className="v3-mute">Every use case Harbor is building or has live. Three decisions each, then only exceptions.</p>
          <p className="v3-mute"><Link to="/v3/build/audit">Audit log</Link> (office administrator)</p>
          <p className="v3-mute"><Link to="/v3/build/api-keys">API keys</Link>: let your own tools read this office's figures and signals.</p>
        </div>
        <p className="v3-row"><Link to="/v3/build/connections">Connections</Link><Link to="/v3/build/onboarding">Onboarding</Link><Link to="/v3/trust/model">See the data model</Link></p>
        <RoleSuggest />
        <Start />
        {err && (
          <p className="v3-err" role="alert">{err} <button onClick={load}>Try again</button></p>
        )}
        {rows === null && !err && <p className="v3-mute" role="status">Loading use cases...</p>}
        {rows !== null && rows.filter((r) => r.stage !== "discarded").length === 0 && <p className="v3-mute">No use case yet. Start one above.</p>}
        {rows !== null && (
          <div className="b3-cols">
            {BOARD.map((c) => {
              const mine = rows.filter((r) => c.stages.includes(r.stage));
              return (
                <section key={c.title} className="b3-col" aria-label={c.title}>
                  <h2>{c.title} <span className="b3-count">{mine.length}</span></h2>
                  {mine.map((r) => {
                    const m = r.needs > 0 ? "needs" : r.stage === "live" ? "info" : "harbor";
                    return (
                      <article key={r.id} className={`b3-card ${m}`}>
                        <b>{r.title}</b>
                        <span className={`v3-pill ${m}`}>
                          {r.needs > 0 ? "Waiting for you" : r.stage === "working" ? "Harbor is working" : r.stage === "live" ? (r.next_run ? `Next run ${r.next_run}` : "Runs on its own") : "Harbor is on it"}
                        </span>
                        <Link to={`/v3/build/${encodeURIComponent(r.id)}`}>Open thread &rarr;</Link>
                      </article>
                    );
                  })}
                  {mine.length === 0 && <small className="v3-mute">None</small>}
                </section>
              );
            })}
          </div>
        )}
      </main>
    </V3Frame>
  );
}

// ---- one use case: /v3/build/:id ----------------------------------------------------------------------------------------------

function RecordCard({ r, startedBy, startedAt }: { r?: ThreadRecord | null; startedBy?: string | null; startedAt?: string }) {
  return (
    <div className={`v3-card v3-record${r?.signed_by ? " signed" : ""}`}>
      <span className="v3-kicker">The record</span>
      <dl>
        <dt>Raised by</dt><dd>{r?.started_by ?? startedBy ?? "You"}{(r?.started_at ?? startedAt) && <> · {when(r?.started_at ?? startedAt)}</>}</dd>
        {r?.sent_at && <><dt>Sent to the signer</dt><dd>{when(r.sent_at)}</dd></>}
        {r?.signed_by ? (
          <><dt>Confirmed and signed by</dt><dd><span className="v3-pill done">Signed</span> {r.signed_by} · {when(r.signed_at)}</dd><dt>Version</dt><dd>{r.version ?? 1}</dd></>
        ) : (
          <><dt>Signed</dt><dd className="v3-mute">Not yet. Your Confirm on the brief signs the intent in your name, with the time.</dd></>
        )}
      </dl>
      {r?.document && <a href={r.document}>Download the signed intent document (Word)</a>}
    </div>
  );
}

const WIDTH_KEY = "v3.build.talkWidth";
const clampW = (w: number) => Math.min(Math.max(w, 320), Math.max(320, window.innerWidth - 480));

/** The handle between the conversation and the graph: drag it, or focus it and use the arrow keys. The width is remembered per browser. */
function useSplit(): [number | null, ReactNode] {
  const [w, setW] = useState<number | null>(() => {
    try { const v = Number(localStorage.getItem(WIDTH_KEY)); return v > 0 ? v : null; } catch { return null; }
  });
  const keep = (v: number) => { const c = clampW(v); setW(c); try { localStorage.setItem(WIDTH_KEY, String(c)); } catch { /* the width just is not remembered */ } };
  const startDrag = (e: RPointerEvent<HTMLDivElement>) => {
    const left = (e.currentTarget.previousElementSibling as HTMLElement | null)?.getBoundingClientRect().left ?? 0;
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
      aria-label="Drag to change the width of the conversation and the graph"
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

function Case({ id }: { id: string }) {
  const [t, setT] = useState<BuildThread | null>(null);
  const [err, setErr] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [picked, setPicked] = useState<Record<string, string>>({});
  const composer = useRef<HTMLTextAreaElement>(null);
  const [talkW, splitter] = useSplit();
  const phone = usePhone();
  const [tab, setTab] = useState<"talk" | "brief" | "files">("talk");
  const [files, setFiles] = useState<FileRow[]>([]);
  const arrived = useMemo(() => new Set(files.flatMap((f) => (f.source ? [f.source.trim().toLowerCase()] : []))), [files]);

  const load = useCallback(() => getThread(id).then((r) => { setT(r); setErr(null); }).catch((e: Error) => setErr(e)), [id]);
  useEffect(() => { void load(); }, [load]);
  const stage = t?.stage;
  useEffect(() => {
    if (stage !== "working" && stage !== "drafting") return;
    const h = setInterval(() => { void load(); }, POLL_MS);
    return () => clearInterval(h);
  }, [stage, load]);

  // The brief's process as North drafted it (the signed intent's own map), drawn as the 2.0 swim lane. Refetched as the stage moves on.
  const [lane, setLane] = useState<SowView["process"] | null>(null);
  const [laneStep, setLaneStep] = useState<number | null>(null);
  const iid = t?.iid;
  useEffect(() => {
    if (!iid) return;
    getSow(iid).then((s) => setLane(s.process ?? null)).catch(() => setLane(null));  // not open to this person, or no brief yet: no lane
  }, [iid, stage]);

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
              <p>{gone ? "I could not find this use case. It may have been removed." : err.message}</p>
              <div className="v3-row">{!gone && <button onClick={() => void load()}>Try again</button>}<Link to="/v3/build">Back to the use cases</Link></div>
            </div>
          ) : <p className="v3-mute" role="status">Loading...</p>}
        </div>
      </V3Frame>
    );
  }

  const d = t.decision;
  const doc = (d?.brief ?? t.brief)?.doc;  // after Decision 1 the confirmed brief stays drawn
  const qs = d?.questions ?? [];
  const value = (q: { id: string; assumed?: string }) => picked[q.id] ?? q.assumed;
  const answers = Object.fromEntries(qs.flatMap((q) => { const v = value(q); return v ? [[q.id, v]] : []; }));
  const open = qs.filter((q) => !value(q)).length;
  const updating = t.stage === "drafting" && !!d?.brief;
  const lastQuestion = [...t.events].reverse().find((e) => e.kind === "question")?.text;
  const step = stepOf(t);
  const save = (l: BriefLine, v: string) => run(editBrief(id, l, v));

  let act: ReactNode = null;
  if (t.stage === "drafting" && !updating) {
    act = <p className="v3-mute" role="status">Harbor is reading what you wrote...</p>;
  } else if (t.stage === "decision1" || updating) {
    act = (
      <div className="v3-dec">
        {updating && <p className="v3-updating" role="status">Harbor is updating the brief. Changed boxes glow.</p>}
        {gapLine(d?.gaps, updating, t.signoff) && <p className="v3-gap">{gapLine(d?.gaps, updating, t.signoff)}</p>}
        <OpenQuestions gaps={d?.gaps} updating={updating} box={() => composer.current} />
        <SignNote s={t.signoff} />
        <div className="v3-row">
          {signAction(t.signoff, "Confirm the brief", busy || updating || !doc?.length, () => void run(decide(id, 1, "confirm")), () => void run(sendForSignature(id)))}
          <button onClick={() => openComposer(composer.current)}>Change something</button>
        </div>
        {confirmWhy(updating, !!err, !doc?.length) && <p className="v3-why" role="status">{confirmWhy(updating, !!err, !doc?.length)}</p>}
      </div>
    );
  } else if (t.stage === "working") {
    act = (
      <div className="v3-row">
        <button disabled={busy} onClick={() => void run(say(id, "Stop"))}>Stop</button>
        <Link to={`/v3/trust/workbench?thread=${encodeURIComponent(id)}`}>See the technical detail</Link>
      </div>
    );
  } else if (t.stage === "decision2" && d) {
    act = (
      <div className="v3-dec">
        <span className="v3-kicker">Decision 2 · {d.title || "Here is what I understood"}</span>
        <ul style={{ listStyle: "none", margin: 0, padding: 0, minWidth: 0 }}>
          {(d.files ?? []).map((f) => (
            <li key={f.name} style={{ borderTop: "1px solid var(--line)", padding: "10px 0", minWidth: 0, overflowWrap: "anywhere" }}>
              <div><span style={{ fontWeight: 600 }}>{f.name}</span> <small className="v3-mute">&rarr; {f.goes_to} ({f.state})</small></div>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, fontSize: 14 }}>
                <span>read as {f.read_as}</span>
                <span className={`v3-pill ${level(f.confidence) === "high" ? "done" : "needs"}`}>{level(f.confidence)}</span>
              </div>
            </li>
          ))}
        </ul>
        {qs.length > 0 && <b>{qs.length === 1 ? "One thing I am not sure about" : `${qs.length} things I am not sure about`}</b>}
        {qs.map((q) => <QuestionBlock key={q.id} q={q} value={value(q)} onPick={(o) => setPicked({ ...picked, [q.id]: o })} onElse={() => openComposer(composer.current, "Say what is off")} />)}
        <AssumptionsCard assumptions={d.assumptions} />
        {d.summary && <p className="v3-mute">{d.summary}</p>}
        <div className="v3-row">
          <button className="go" disabled={busy || open > 0} onClick={() => void run(decide(id, 2, "carry_on", answers))}>This is right, carry on</button>
          <button onClick={() => openComposer(composer.current, "Say what is off")}>Something is off</button>
          {open > 0 && <small className="v3-mute">{open} answer{open > 1 ? "s" : ""} needed</small>}
        </div>
      </div>
    );
  } else if (t.stage === "decision3" && d) {
    act = (
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
        <FigureChecks figures={t.figures} />
        {d.summary && <p className="v3-mute">{d.summary}</p>}
        <div className="v3-row">
          <button className="go" disabled={busy} onClick={() => void run(decide(id, 3, "go_live"))}>Go live</button>
          <button disabled={busy} onClick={() => void run(decide(id, 3, "not_yet"))}>Not yet</button>
        </div>
      </div>
    );
  } else if (t.stage === "live") {
    act = (
      <div className="v3-card b3-live">
        <span className="v3-pill done">Live</span>
        <p>{t.next_run ? `Next run: ${t.next_run}` : "Runs on its own when the next files arrive."}</p>
        <div className="v3-row"><Link to="/v3/board">Board</Link><Link to="/v3/files">Files</Link></div>
      </div>
    );
  } else if (t.stage === "question") {
    act = (
      <div className="v3-card need">
        <span className="v3-kicker">A question for you</span>
        <p>{lastQuestion ?? "Harbor needs something from you."}</p>
        <div className="v3-row"><button className="go" disabled={busy} onClick={() => void run(decide(id, d?.n ?? 1, "retry"))}>Retry</button></div>
      </div>
    );
  }

  if (act && err) act = <>{act}<p className="v3-err" role="alert">{err.message}</p></>;  // next to the buttons that failed

  const send = () => {
    const s0 = text.trim();
    if (s0) void run(say(id, s0).then((r) => { setText(""); return r; }));
  };

  const progress = (
    <ol className="b3-prog" aria-label="Progress">
      {STEPS.map((s0, i) => <li key={s0}><span className={stepClass(t, i, step)} aria-current={i === step && t.stage !== "live" ? "step" : undefined}>{i + 1} {s0}</span></li>)}
    </ol>
  );
  const nowLine = t.now?.text && <p className="b3-now" role="status"><b>Harbor is doing:</b> {t.now.text}</p>;
  const talk = (
    <section className="v3-talk" style={talkW && !phone ? { flex: `0 0 ${talkW}px`, maxWidth: "none" } : undefined}>
      <div className="v3-row b3-titlerow">
        <h1>{t.title}</h1>
        {t.stage !== "live" && t.stage !== "discarded" && <Discard id={id} onDone={(r) => setT(r)} />}
      </div>
      {phone && <>{progress}{nowLine}{act}</>}
      {t.stage === "discarded" && <p className="v3-updating" role="status">This use case was discarded. It is kept for the record. <Link to="/v3/build">Back to the use cases</Link>.</p>}
      <ul className="v3-tl">{t.events.map((e, i) => <Row key={i} ev={e} />)}</ul>
      {err && !act && <p className="v3-err" role="alert">{err.message}</p>}
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
  );
  const record = <RecordCard r={t.record} startedBy={t.started_by} startedAt={t.events[0]?.at} />;
  const band = <DropBand id={id} doc={doc} onFiles={setFiles} />;

  if (phone) {
    const TABS = [["talk", "Talk"], ["brief", "Brief"], ["files", "Files"]] as const;
    return (
      <V3Frame back={<Link to="/v3/build" className="b3-back">&larr; Use cases</Link>}>
        <div className="b3 b3-phone">
          <div className="b3-tabs" role="tablist" aria-label="This use case">
            {TABS.map(([k, label]) => (
              <button key={k} role="tab" type="button" aria-selected={tab === k} onClick={() => setTab(k)}>{label}</button>
            ))}
          </div>
          {tab === "talk" && talk}
          {tab === "brief" && (
            <section className="b3-phonepane" aria-label="The brief">
              {progress}
              <BriefList doc={doc} busy={busy} onSave={save} />
              {record}
            </section>
          )}
          <div hidden={tab !== "files"}>{band}</div>
        </div>
      </V3Frame>
    );
  }

  return (
    <V3Frame back={<Link to="/v3/build" className="b3-back">&larr; Use cases</Link>}>
      <div className="v3-main b3">
        {talk}
        {splitter}
        <aside className="v3-side" aria-label="The intent, drawn as you talk">
          {progress}
          {nowLine}
          {act}
          <IntentGraph doc={doc} busy={busy} onSave={save} arrived={arrived} live={t.stage === "live"} />
          {lane?.steps?.length ? (
            <section className="v3-card b3-lane" aria-label="The process">
              <h3>The process</h3>
              <p className="v3-mute">Who does each step and in which system, as North drafted it. Manual steps are flagged.</p>
              <Swimlane map={lane} selected={laneStep} onSelect={(n) => setLaneStep(laneStep === n ? null : n)} />
            </section>
          ) : null}
          {record}
        </aside>
      </div>
      {band}
    </V3Frame>
  );
}

export default function BuildPage() {
  const { id } = useParams();
  return id ? <Case key={id} id={id} /> : <Board />;
}
