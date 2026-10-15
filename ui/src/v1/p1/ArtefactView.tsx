import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { Button, Pill } from "../../design";
import { addComment, exportDoc, getDoc, type Doc, type Kind } from "./api";
import CommentThread from "./CommentThread";
import RunBookBar from "./RunBookBar";

// P1: each artefact as a document of numbered lines with a comment gutter. A comment is addressed to one person.
const said = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not work. Please try again.");
const plain = (t: string) => t.replace(/\*\*/g, "");

function Write({ pid, kind, lineRef, people, done }: { pid: string; kind: Kind; lineRef: string | null; people: string[]; done: () => void }) {
  const [to, setTo] = useState(people[0] ?? "");
  const [text, setText] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  return (
    <form style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "6px 0" }} onSubmit={(ev) => {
      ev.preventDefault();
      if (!text.trim() || !to) return;
      addComment(pid, { artefact: kind, line_ref: lineRef, to, text }).then(() => { setText(""); done(); }).catch((e: unknown) => setProblem(said(e)));
    }}>
      <select className="ds-input" aria-label="Addressed to" value={to} onChange={(ev) => setTo(ev.target.value)}>
        {people.map((p) => <option key={p} value={p}>{p}</option>)}
      </select>
      <input className="ds-input" aria-label={`Your comment on ${lineRef ? `line ${lineRef}` : "the document"}`} value={text}
        onChange={(ev) => setText(ev.target.value)} style={{ flex: "1 1 200px" }} />
      <Button type="submit" disabled={!text.trim() || !to}>Send comment</Button>
      {problem ? <span role="alert" className="ds-muted">{problem}</span> : null}
    </form>
  );
}

export default function ArtefactView({ pid, kind, people, line = null, comment = null }: {
  pid: string; kind: Kind; people: string[]; line?: string | null; comment?: string | null;
}) {
  const [doc, setDoc] = useState<Doc | null>(null);
  const [state, setState] = useState<"loading" | "error" | "refused" | "empty" | "populated">("loading");
  const [writing, setWriting] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const reload = useCallback(() => setAttempt((a) => a + 1), []);

  useEffect(() => {
    let live = true;
    getDoc(pid, kind).then((d) => { if (live) { setDoc(d); setState("populated"); } })
      .catch((e: unknown) => {
        if (live) setState(e instanceof ApiError && e.status === 403 ? "refused" : e instanceof ApiError && e.status === 404 ? "empty" : "error");
      });
    return () => { live = false; };
  }, [pid, kind, attempt]);

  useEffect(() => {  // a link from Pulse: bring the line into view once the document is there
    if (doc && line) document.getElementById(`line-${line}`)?.scrollIntoView?.({ block: "center" });
  }, [doc, line]);

  if (!doc || state !== "populated") return <ScreenState state={state} onRetry={reload} />;
  const on = (ref: string | null) => doc.comments.filter((c) => c.line_ref === ref);
  const close = () => { setWriting(null); reload(); };
  const sheet = kind === "build_pack";
  return (
    <article aria-label={doc.name}>
      <p style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <Pill tone={doc.state === "signed" ? "signed" : "draft"}>{doc.state === "signed" ? `Signed by ${doc.signed_by ?? ""}` : "Draft"}</Pill>
        {doc.version ? <span className="ds-muted">Version {doc.version}</span> : null}
        <Button onClick={() => void exportDoc(pid, kind, sheet ? "xlsx" : "docx")}>{sheet ? "Download .xlsx" : "Download .docx"}</Button>
        <Button onClick={() => void exportDoc(pid, kind, "md")}>Download .md</Button>
        <button type="button" className="ds-link" onClick={() => setWriting(writing === "doc" ? null : "doc")}>Comment on the document</button>
      </p>
      {kind === "run_book" ? <RunBookBar pid={pid} doc={doc} changed={reload} /> : null}
      {writing === "doc" ? <Write pid={pid} kind={kind} lineRef={null} people={people} done={close} /> : null}
      <CommentThread pid={pid} comments={on(null)} highlight={comment} me={doc.me} signers={doc.signers} changed={reload} />
      {doc.sections.map((s) => (
        <section key={s.n} className="ds-card" style={{ padding: 16, marginBottom: 12 }}>
          <h2 style={{ margin: "0 0 8px" }}>{s.heading}</h2>
          {s.lines.length ? s.lines.map((ln) => {
            const here = on(ln.ref);
            return (
              <div key={ln.ref} id={`line-${ln.ref}`} style={{ background: ln.ref === line ? "var(--ds-highlight, rgba(255, 196, 0, 0.15))" : undefined, display: "grid", gridTemplateColumns: "3.5em 1fr auto", gap: 8, alignItems: "start", margin: "4px 0" }}>
                <span className="ds-muted">{ln.ref}</span>
                <div>
                  <span>{plain(ln.text)}</span>
                  <CommentThread pid={pid} comments={here} highlight={comment} me={doc.me} signers={doc.signers} changed={reload} />
                  {writing === ln.ref ? <Write pid={pid} kind={kind} lineRef={ln.ref} people={people} done={close} /> : null}
                </div>
                <button type="button" className="ds-link" aria-label={`Comment on line ${ln.ref}`} onClick={() => setWriting(writing === ln.ref ? null : ln.ref)}>
                  {here.length ? `${here.length} comment${here.length > 1 ? "s" : ""}` : "Comment"}
                </button>
              </div>
            );
          }) : <p className="ds-muted" style={{ margin: 0 }}>Nothing yet.</p>}
        </section>
      ))}
    </article>
  );
}
