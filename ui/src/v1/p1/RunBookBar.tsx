import { useState } from "react";

import { ApiError } from "../../api/client";
import { Button } from "../../design";
import { draftRunBook, saveRunBook, signRunBook, type Doc } from "./api";

// G2: the run book's own acts. Span drafts it from the build pack; the ops manager edits the lines and signs it (the server refuses anyone else,
// and a signature while a comment on it is unresolved, in a plain sentence).
const said = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not work. Please try again.");
const plain = (t: string) => t.replace(/\*\*/g, "");

export default function RunBookBar({ pid, doc, changed }: { pid: string; doc: Doc; changed: () => void }) {
  const [edit, setEdit] = useState<string[] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const act = (p: Promise<unknown>) => p.then(() => { setProblem(null); setEdit(null); changed(); }).catch((e: unknown) => setProblem(said(e)));
  const empty = doc.sections.every((s) => !s.lines.length);
  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "6px 0" }}>
      {empty ? <Button variant="primary" onClick={() => void act(draftRunBook(pid))}>Ask Span to draft the run book</Button> : null}
      {!empty && !edit ? <Button onClick={() => setEdit(doc.sections.map((s) => s.lines.map((l) => plain(l.text)).join("\n")))}>Edit the run book</Button> : null}
      {!empty && doc.state === "draft" && !edit ? <Button variant="primary" onClick={() => void act(signRunBook(pid))}>Sign the run book</Button> : null}
      {edit ? (
        <div style={{ flex: "1 1 100%" }}>
          {doc.sections.map((s, i) => (
            <label key={s.n} style={{ display: "block", margin: "6px 0" }}>{s.heading} (one line each)
              <textarea className="ds-input" style={{ width: "100%" }} rows={Math.max(3, (edit[i] ?? "").split("\n").length)} value={edit[i] ?? ""}
                onChange={(ev) => setEdit(edit.map((t, j) => (j === i ? ev.target.value : t)))} />
            </label>
          ))}
          <Button variant="primary" onClick={() => void act(saveRunBook(pid, edit.map((t) => ({ lines: t.split("\n") }))))}>Save the run book</Button>{" "}
          <Button onClick={() => setEdit(null)}>Cancel</Button>
        </div>
      ) : null}
      {problem ? <span role="alert" className="ds-warn">{problem}</span> : null}
    </div>
  );
}
