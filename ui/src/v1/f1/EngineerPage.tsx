import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, Refused } from "../../api/client";
import MessageBubble from "../../components/MessageBubble";
import { Button, PageFrame, Pill } from "../../design";
import { useSession } from "../../useSession";
import { Composer, SpeakButton, useReadAloud } from "../voice";
import Workbench, { type Doc } from "../workbench/Workbench";
import ProjectTag from "../p1/ProjectTag";
import { answer, downloadFlagged, signPack, flag, getEngineer, getRuns, kindOf, readBase64, runLoad, type Engineer, type Point, type Runs } from "./api";
import ModeLine from "../router/ModeLine";
import { useProposals } from "../workbench/proposals";

// F1: /centre/build/:iid/engineer. L1: the conversation with Span is docked on the right of the workbench; on the left a strip of three
// documents: Data catalogue (what Span has read), ETL mapping (open points walked one at a time, flagging for a real engineer) and
// Testing approach (B4's contracts, checks and last runs, "Run the load", Span's note per run).

const KIND: Record<Point["kind"], string> = { mapping: "Mapping row", formula: "Formula", check: "Failed check", document: "Document", deviation: "Needs approval" };
const when = (at: string) => {
  const d = new Date(at);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
};
const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");
const CSS = `
.f1-point{border-top:1px solid var(--line, #ddd);padding:8px 0}
.f1-point pre{white-space:pre-wrap;overflow-x:auto;font-size:12px}
`;

function PointCard({ p, current, can, onAnswer }: { p: Point; current: boolean; can: boolean; onAnswer: (p: Point) => void }) {
  return (
    <div className="f1-point" aria-label={`Open point: ${p.about}`}>
      <p style={{ margin: 0 }}>
        <strong>{p.row !== null ? `Row ${p.row}: ` : ""}{p.about}</strong>{" "}
        <Pill tone={p.kind === "check" ? "failed" : "open"}>{KIND[p.kind]}</Pill>{current ? <> <Pill tone="draft">Now</Pill></> : null}
        {p.flagged ? <> <Pill tone="late">Flagged</Pill></> : null}
      </p>
      <p style={{ margin: "4px 0" }}><span className="ds-muted">Span understood: </span>{p.understood}</p>
      <p style={{ margin: "4px 0" }}><span className="ds-muted">Span needs: </span>{p.needs}</p>
      {p.sql ? <pre>{p.sql}</pre> : null}
      {p.kind === "deviation" ? <p style={{ margin: "4px 0" }}><Link className="ds-link" relative="path" to="../deviations">Waiting for approval: open the request</Link></p> : null}
      {can && !current ? <Button onClick={() => onAnswer(p)}>Answer this one</Button> : null}
    </div>
  );
}

function RealEngineer({ points, can, iid, onFlag }: { points: Point[]; can: boolean; iid: string; onFlag: (id: string, note: string) => Promise<void> }) {
  const [pick, setPick] = useState("");
  const [note, setNote] = useState("");
  const flagged = points.filter((p) => p.flagged);
  return (
    <>
      <p className="ds-muted" style={{ marginTop: 0 }}>Flag a point for a data engineer. It stays open until someone answers it here.</p>
      {can && points.length ? (
        <form style={{ display: "flex", flexDirection: "column", gap: 8 }}
          onSubmit={(e) => { e.preventDefault(); if (pick) void onFlag(pick, note).then(() => setNote("")); }}>
          <select className="ds-input" aria-label="Point to flag" value={pick} onChange={(e) => setPick(e.target.value)}>
            <option value="">Choose a point</option>
            {points.map((p) => <option key={p.id} value={p.id}>{p.row !== null ? `Row ${p.row}: ` : ""}{p.about}</option>)}
          </select>
          <textarea className="ds-input" aria-label="Note for the data engineer" rows={2} value={note} onChange={(e) => setNote(e.target.value)}
            placeholder="What should they know?" />
          <Button type="submit" variant="primary" disabled={!pick}>Flag for a data engineer</Button>
        </form>
      ) : null}
      <h3 style={{ margin: "12px 0 4px", fontSize: 15 }}>Flagged ({flagged.length})</h3>
      {flagged.length ? flagged.map((p) => (
        <p key={p.id} style={{ margin: "4px 0" }}><strong>{p.about}</strong>: {p.flagged?.note || "no note"} <span className="ds-muted">({p.flagged?.by}, {when(p.flagged?.at ?? "")})</span></p>
      )) : <p className="ds-muted" style={{ margin: 0 }}>Nothing is flagged.</p>}
      <p style={{ marginBottom: 0 }}><button type="button" className="ds-link" onClick={() => void downloadFlagged(iid)}>Download as Markdown</button></p>
    </>
  );
}

function Pipeline({ runs, can, busy, onRun, iid }: { runs: Runs | null; can: boolean; busy: boolean; onRun: () => void; iid: string }) {
  const [signed, setSigned] = useState("");
  const [problem, setProblem] = useState("");
  if (!runs) return <p className="ds-muted">The pipeline could not be read yet.</p>;
  return (
    <>
      {can ? <Button onClick={() => { setProblem(""); signPack(iid).then(() => setSigned("The build pack is signed."), (e: unknown) => setProblem(plain(e))); }}>Sign the build pack</Button> : null}
      {signed ? <p role="status" className="ds-muted">{signed}</p> : null}
      {problem ? <p role="alert">{problem}</p> : null}
      {can ? <Button variant="primary" disabled={busy} onClick={onRun}>{busy ? "Loading…" : "Run the load"}</Button> : null}
      {runs.contracts.length === 0 ? <p className="ds-muted">No mapping row is marked mapped yet, so there is nothing to load.</p> : runs.contracts.map((c) => {
        const last = runs.runs.find((r) => r.source === c.source);
        const bad = last ? last.rules.filter((x) => !x.passed) : [];
        return (
          <div key={c.source} className="f1-point">
            <p style={{ margin: 0 }}><strong>{c.title}</strong>{" "}
              {last ? <Pill tone={last.status === "ok" ? "ok" : last.status === "late" ? "late" : "failed"}>{last.status}</Pill> : <Pill tone="draft">No run yet</Pill>}</p>
            <p className="ds-muted" style={{ margin: "4px 0" }}>{c.schema.length} fields, {c.rules.length} checks{last ? `, ${last.rows} rows on ${when(last.started)}` : ""}.</p>
            {bad.length ? <ul style={{ margin: "4px 0" }}>{bad.map((x) => <li key={x.rule}>{x.rule}: {x.count} rows</li>)}</ul> : null}
            {last?.note ? (last.note.text ? <p style={{ margin: "4px 0" }}>{last.note.text}</p>
              : <ul style={{ margin: "4px 0" }}>{last.note.lines.map((l) => <li key={l}>{l}</li>)}</ul>) : null}
            {last?.note?.sentence ? <p className="ds-muted" style={{ margin: 0 }}>{last.note.sentence}</p> : null}
          </div>
        );
      })}
      <p style={{ marginBottom: 0 }}><Link className="ds-link" to={`/centre/build/${encodeURIComponent(iid)}/runs`}>Open the full run log</Link></p>
    </>
  );
}

/** The data engineer's screen: Span walks the open points one at a time; answers patch the mapping sheet. */
export default function EngineerPage() {
  const { iid = "" } = useParams();
  const { user } = useSession();
  const can = !!user?.roles.some((r) => r === "company_admin" || r === "analyst");
  const [data, setData] = useState<Engineer | null>(null);
  const [runs, setRuns] = useState<Runs | null>(null);
  const [failed, setFailed] = useState("");
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [target, setTarget] = useState<Point | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const box = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try { setData(await getEngineer(iid)); setFailed(""); } catch (err) {
      setFailed(err instanceof Refused ? "This conversation is for the data team." : err instanceof ApiError && err.status === 404
        ? "There is no mapping sheet for this intent yet. Span writes it once the scope is agreed." : plain(err));
    }
    getRuns(iid).then(setRuns).catch(() => setRuns(null));
  }, [iid]);
  useEffect(() => { void load(); }, [load]);
  const pr = useProposals(iid, data?.proposals, load);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [data, busy]);

  async function act(fn: () => Promise<Engineer>) {
    setBusy(true);
    setError("");
    try { setData(await fn()); return true; } catch (err) { setError(plain(err)); return false; } finally { setBusy(false); }
  }

  function send(said: string, up: File[]) {
    void act(async () => answer(iid, said, target?.id, await Promise.all(up.map(async (f) => ({ name: f.name, data: await readBase64(f), kind: kindOf(f.name) })))))
      .then((ok) => { if (ok) { setText(""); setFiles([]); setTarget(null); } });
  }
  const lastFlow = data?.turns.filter((t) => t.by === "flow").at(-1);
  useReadAloud(lastFlow ? { id: lastFlow.id, text: lastFlow.text } : null);

  async function onRun() {
    setBusy(true);
    try {
      const r = await runLoad(iid);
      const bad = r.runs.filter((x) => x.status === "failed").length;
      setMsg([`Ran ${r.runs.length} source${r.runs.length === 1 ? "" : "s"}${bad ? `, ${bad} failed` : ""}.`, ...r.missing.map((m) => m.reason)].join(" "));
      await load();
    } catch (err) {
      setMsg(plain(err));
    } finally {
      setBusy(false);
    }
  }

  if (failed) return <PageFrame title="Data engineer"><p role="alert">{failed} <Button onClick={() => void load()}>Try again</Button></p></PageFrame>;
  if (!data) return <PageFrame title="Data engineer"><p className="ds-muted">Opening the conversation…</p></PageFrame>;

  const turns = data.turns.length ? data.turns : [{ id: "opening", by: "flow" as const, name: "Span", text: data.opening, at: "", point: null }];
  const current = data.points.find((p) => p.id === data.current) ?? null;
  const c = data.context;
  const docs: Doc[] = [
    { id: "catalogue", title: "Data catalogue", render: () => (
      <>
        <p style={{ marginTop: 0 }}>Span has read the catalogue ({c.catalogue_tables} tables), the data model ({c.data_model_tables} tables) and {c.runs} runs.</p>
        <p className="ds-muted">Skill: {c.skill}</p>
        <p style={{ marginBottom: 0 }}><Link className="ds-link" to={`/centre/build/${encodeURIComponent(iid)}/mapping`}>Open the mapping sheet</Link></p>
      </>) },
    { id: "etl", title: "ETL mapping", proposes: ["mapping"], render: () => (
      <>
        <p style={{ marginTop: 0 }}>The mapping sheet has {c.mapping_rows} rows (version {c.mapping_version ?? "not stated"}), {c.transformations} transformations, {c.sql_rows} with SQL.</p>
        <h3 style={{ margin: "0 0 4px", fontSize: 15 }}>Open points ({data.points.length})</h3>
        {data.points.length
          ? data.points.map((p) => <PointCard key={p.id} p={p} current={p.id === (target?.id ?? current?.id)} can={can}
            onAnswer={(x) => { setTarget(x); box.current?.focus(); }} />)
          : <p className="ds-muted">Nothing is open.{data.handed_over ? " Span has handed over to the ops manager." : ""}</p>}
        <h3 style={{ margin: "12px 0 4px", fontSize: 15 }}>Real engineer</h3>
        <RealEngineer points={data.points} can={can} iid={iid} onFlag={async (id, note) => { await act(() => flag(iid, id, note)); }} />
      </>) },
    { id: "testing", title: "Testing approach", render: () => (
      <>{msg ? <p role="status" className="ds-muted">{msg}</p> : null}<Pipeline runs={runs} can={can} busy={busy} onRun={() => void onRun()} iid={iid} /></>) },
  ];
  return (
    <PageFrame title="Data engineer" crumbs="Build · Span" subline="Span asks about every doubt on the pipeline, one at a time. Your answers go onto the mapping sheet.">
      <style>{CSS}</style>
      <ProjectTag iid={iid} />
      <Workbench layoutKey="flow" documents={docs} agent="Span" iid={iid} proposals={pr.proposals} onAccept={pr.onAccept} onReject={pr.onReject} changeError={pr.error} changeBusy={pr.busy} canAdd={can}
        chatHead={<>
          <p style={{ margin: 0 }}><strong>Span</strong> <span className="ds-muted">Data engineer · {busy ? "Thinking" : data.points.length ? "Waiting for you" : "Idle"}</span></p>
          <ModeLine />
        </>}
        chatLog={<>
          {turns.map((t) => (
            <MessageBubble key={t.id} from={t.by === "flow" ? "agent" : "human"} who={t.name} when={t.at ? when(t.at) : undefined} text={t.text}>{t.by === "flow" && t.at ? <SpeakButton text={t.text} /> : null}</MessageBubble>
          ))}
          {busy ? <p className="ds-muted" role="status">Span is thinking…</p> : null}
          <div ref={end} />
        </>}
        composer={can ? (
          <>
            {target ? <p style={{ margin: 0 }} className="ds-muted">Answering: {target.about} <button type="button" className="ds-link" onClick={() => setTarget(null)}>back to the current point</button></p> : null}
            <Composer agent="Span" text={text} setText={setText} files={files} setFiles={setFiles} onSend={send} busy={busy} error={error} boxRef={box}
              placeholder="Confirm, give the rule in your words, or paste the SQL" />
          </>
        ) : <p className="ds-muted">You can read this conversation; the head of data answers Span.</p>} />
    </PageFrame>
  );
}
