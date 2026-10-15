import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, Pill, when } from "../../design";
import { addComment, deleteComment, editComment, getPeople, getThread, raiseComment, type Comment, type Target, type Thread, type Written } from "./api";

// N2: <Comments target={{ kind, id }} /> puts a thread on a dashboard, widget, line, case or figure. Closed it is one small button; it asks the
// server for the thread only when opened. A person who may not see the thing gets the server's one-sentence refusal and no words.
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not work. Please try again.");

function Box({ initial = "", people, label, onSend, onCancel }: { initial?: string; people: string[]; label: string; onSend: (t: string) => Promise<void>; onCancel?: () => void }) {
  const [text, setText] = useState(initial);
  const [busy, setBusy] = useState(false);
  const m = /@([\p{L} ]*)$/u.exec(text);
  const hints = m ? people.filter((p) => p.toLowerCase().startsWith((m[1] ?? "").toLowerCase()) && p.toLowerCase() !== (m[1] ?? "").toLowerCase()).slice(0, 4) : [];
  const send = async () => { setBusy(true); try { await onSend(text); setText(""); } finally { setBusy(false); } };
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <textarea aria-label={`${label} text`} rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder="Write a comment. Type @ to name a person." />
      {hints.length ? <div style={{ display: "flex", gap: 6 }}>{hints.map((h) => <Button key={h} onClick={() => setText(text.replace(/@[\p{L} ]*$/u, `@${h} `))}>@{h}</Button>)}</div> : null}
      <div style={{ display: "flex", gap: 6 }}>
        <Button variant="primary" disabled={busy || !text.trim()} onClick={send}>{label}</Button>
        {onCancel ? <Button onClick={onCancel}>Cancel</Button> : null}
      </div>
    </div>
  );
}

function Item({ c, target, people, act, reply }: { c: Comment; target: Target; people: string[]; act: (p: Promise<Written>) => Promise<void>; reply: boolean }) {
  const [mode, setMode] = useState<"" | "reply" | "edit" | "history">("");
  const done = async (p: Promise<Written>) => { await act(p); setMode(""); };
  return (
    <li style={{ marginLeft: reply ? 24 : 0, listStyle: "none" }}>
      <div><strong>{c.by}</strong> <span className="ds-muted">{when(c.at)}</span>{c.edited && !c.deleted ? <> <Pill tone="draft">edited</Pill></> : null}</div>
      {c.deleted ? <p className="ds-muted">Deleted by {c.deleted_by}</p> : <p style={{ margin: "2px 0", whiteSpace: "pre-wrap" }}>{c.text}</p>}
      {c.case ? <p>{c.case.link ? <Link className="ds-link" to={c.case.link}>Case {c.case.number}</Link> : `Case ${c.case.number}`}</p> : null}
      {c.ticket ? <p>Ticket {c.ticket.number}</p> : null}
      {c.deleted ? null : (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {c.may.reply && !reply ? <Button onClick={() => setMode("reply")}>Reply</Button> : null}
          {c.may.edit ? <Button onClick={() => setMode("edit")}>Edit</Button> : null}
          {c.may.delete ? <Button onClick={() => { if (window.confirm("Delete this comment? The thread will say you deleted it.")) void act(deleteComment(c.id)); }}>Delete</Button> : null}
          {c.may.raise ? <Button onClick={() => void act(raiseComment(c.id, "case"))}>Raise as a case</Button> : null}
          {c.may.raise ? <Button onClick={() => void act(raiseComment(c.id, "ticket"))}>Raise as a ticket</Button> : null}
          {c.history.length ? <Button onClick={() => setMode(mode === "history" ? "" : "history")}>Earlier wording</Button> : null}
        </div>)}
      {mode === "history" ? <ul>{c.history.map((h, i) => <li key={i}><span className="ds-muted">{when(h.at)}</span> {h.text}</li>)}</ul> : null}
      {mode === "edit" ? <Box initial={c.text ?? ""} people={people} label="Save" onSend={(t) => done(editComment(c.id, t))} onCancel={() => setMode("")} /> : null}
      {mode === "reply" ? <Box people={people} label="Reply" onSend={(t) => done(addComment(target, t, c.id))} onCancel={() => setMode("")} /> : null}
    </li>
  );
}

// CL1: `eager` reads the thread once on mount so the closed button can say "3 comments"; the thread itself stays collapsed.
export default function Comments({ target, startOpen = false, eager = false }: { target: Target; startOpen?: boolean; eager?: boolean }) {
  const [open, setOpen] = useState(startOpen);
  const [thread, setThread] = useState<Thread | null>(null);
  const [people, setPeople] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const load = useCallback(() => getThread(target).then(setThread).catch((e) => setError(plain(e))), [target.kind, target.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (eager && !open) void load();
    if (!open) return;
    setThread(null); setError("");
    void load();
    getPeople().then((p) => setPeople(p.map((x) => x.name))).catch(() => setPeople([]));
  }, [open, load]);
  const act = async (p: Promise<Written>) => {
    try { const w = await p; setThread(w.thread); setNote(w.not_told?.length ? `${w.not_told.join(", ")} cannot see this, so they were not told.` : ""); setError(""); } catch (e) { setError(plain(e)); }
  };
  const roots = thread?.comments.filter((c) => !c.parent_id) ?? [];
  return (
    <div className="ds-comments" aria-label="Comments">
      <Button onClick={() => setOpen(!open)}>{open ? "Hide comments" : thread && thread.count ? `${thread.count} comment${thread.count === 1 ? "" : "s"}` : "Comments"}</Button>
      {open ? (
        <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
          {error ? <p role="alert">{error}</p> : null}
          {note ? <p role="status">{note}</p> : null}
          {!thread && !error ? <p className="ds-muted" role="status">Loading comments.</p> : null}
          {thread && !roots.length ? <p className="ds-muted">No comments yet.</p> : null}
          <ul style={{ padding: 0, margin: 0, display: "grid", gap: 10 }}>
            {roots.map((c) => (
              <div key={c.id}>
                <Item c={c} target={target} people={people} reply={false} act={act} />
                {thread!.comments.filter((r) => r.parent_id === c.id).map((r) => <Item key={r.id} c={r} target={target} people={people} reply act={act} />)}
              </div>))}
          </ul>
          {thread ? <Box people={people} label="Comment" onSend={(t) => act(addComment(target, t))} /> : null}
        </div>) : null}
    </div>
  );
}
