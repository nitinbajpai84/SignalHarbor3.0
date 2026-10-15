import { useState } from "react";

import { ApiError } from "../../api/client";
import { Button, Pill } from "../../design";
import { answerComment, resolveComment, type Comment } from "./api";

// P1: the comments on one line (or on the whole document). The addressee answers; the author or a signer resolves.
const said = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not work. Please try again.");
const TONE = { open: "open", answered: "draft", resolved: "ok" } as const;

function One({ pid, c, me, signers, changed, lit }: { pid: string; c: Comment; me: string; signers: string[]; changed: () => void; lit: boolean }) {
  const [text, setText] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const act = (p: Promise<unknown>) => p.then(() => { setProblem(null); changed(); }).catch((e: unknown) => setProblem(said(e)));
  const mayResolve = c.state !== "resolved" && (c.by === me || signers.includes(me));
  return (
    <li className="ds-card" aria-current={lit ? "true" : undefined}
      style={{ padding: 8, margin: "6px 0", listStyle: "none", outline: lit ? "2px solid var(--ds-accent, #c48a00)" : undefined }}>
      <p style={{ margin: 0 }}>
        <Pill tone={TONE[c.state]}>{c.state === "open" ? "Open" : c.state === "answered" ? "Answered" : "Resolved"}</Pill>{" "}
        <strong>{c.name}</strong>{c.to ? <> to {c.to}</> : null}: {c.text}
      </p>
      {c.answer ? <p style={{ margin: "4px 0 0" }}><span className="ds-muted">{c.to} answered:</span> {c.answer}</p> : null}
      {c.state === "open" && c.to === me ? (
        <form style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 6 }}
          onSubmit={(ev) => { ev.preventDefault(); if (text.trim()) void act(answerComment(pid, c.id, text)); }}>
          <input className="ds-input" aria-label={`Answer ${c.name}`} value={text} onChange={(ev) => setText(ev.target.value)} style={{ flex: "1 1 200px" }} />
          <Button type="submit" disabled={!text.trim()}>Answer</Button>
        </form>
      ) : null}
      {mayResolve ? <Button onClick={() => void act(resolveComment(pid, c.id))}>Resolve</Button> : null}
      {problem ? <p role="alert" className="ds-muted">{problem}</p> : null}
    </li>
  );
}

export default function CommentThread({ pid, comments, me, signers, changed, highlight = null }: {
  pid: string; comments: Comment[]; me: string; signers: string[]; changed: () => void; highlight?: string | null;
}) {
  if (!comments.length) return null;
  return <ul style={{ padding: 0, margin: "4px 0" }}>{comments.map((c) => <One key={c.id} pid={pid} c={c} me={me} signers={signers} changed={changed} lit={c.id === highlight} />)}</ul>;
}
