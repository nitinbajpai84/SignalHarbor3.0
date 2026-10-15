import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button } from "../../design";
import { day, time } from "../../design/dates";
import { addComment } from "../p1/api";
import type { Assignment, Waiting } from "../p2/api";

// V5W-1 / ACT1: the pieces of the Action page that ActionToday reuses: the assignment card, the "Before this" line, the words for what waits.
export const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");
export const KIND: Record<Waiting["kind"], string> = { dashboard: "Dashboard", plan: "Plan", pack: "Design pack", intent: "Intent to sign", delivery: "Delivery channel" };
export const ACTION: Partial<Record<Waiting["kind"], string>> = { intent: "Sign" };
export const hello = () => { const h = new Date().getHours(); return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"; };
export const things = (n: number) => (n === 0 ? "Nothing needs you today." : n === 1 ? "1 thing needs you today." : `${n} things need you today.`);

/** V6 design B5: the card a builder gets when a project is assigned or handed over: new, due date, who assigned it, the steps, the note, and a way to ask. */
export function Mine({ a, onDone }: { a: Assignment; onDone: (id: string) => void }) {
  const asker = a.assigned_by ?? a.by;
  const first = asker.split(" ")[0] || asker;
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [state, setState] = useState<"" | "sending" | "sent">("");
  const [problem, setProblem] = useState("");
  async function ask(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setState("sending"); setProblem("");
    try { await addComment(a.pid, { artefact: "intent", line_ref: null, to: asker, text: text.trim() }); setState("sent"); setText(""); setOpen(false); }
    catch (err) { setProblem(plain(err)); setState(""); }
  }
  return (
    <article className="ds-card" style={{ padding: 16 }}>
      <p className="ds-eyebrow" style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <span>NEW · ASSIGNED TO YOU</span>{a.due ? <span data-tone="amber" style={{ color: "var(--ds-amber)" }}>Due {day(a.due, a.due)}</span> : null}<span className="ds-muted">Build · assigned by {asker}</span>
      </p>
      <h3 className="ds-serif" style={{ margin: "6px 0", fontSize: 22 }}>Build: {a.title ?? "A project"}</h3>
      <p style={{ margin: "0 0 8px", display: "flex", gap: 8, flexWrap: "wrap" }}>{a.steps.map((s) => <span key={s} className="b9-agent" style={{ margin: 0 }}>{s}</span>)}</p>
      {a.message ? <p style={{ margin: "0 0 8px" }}>&ldquo;{a.message}&rdquo; <span className="ds-muted">{a.by}</span></p> : null}
      {state === "sent" ? <p role="status" className="ds-muted" style={{ margin: "0 0 8px" }}>Your question went to {first}. The answer comes back to you in Action.</p> : null}
      {open ? (
        <form onSubmit={(e) => void ask(e)} style={{ display: "grid", gap: 8, margin: "0 0 8px" }}>
          <label>Your question to {first}<textarea className="ds-input" rows={2} value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} style={{ display: "block", width: "100%" }} /></label>
          {problem ? <p role="alert" className="ds-warn" style={{ margin: 0 }}>{problem}</p> : null}
          <div style={{ display: "flex", gap: 8 }}><Button variant="primary" type="submit" disabled={!text.trim() || state === "sending"}>Send to {first}</Button><Button onClick={() => setOpen(false)}>Cancel</Button></div>
        </form>
      ) : null}
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <Link className="ds-btn ds-btn--primary" to={a.link}>Open project</Link>
        <Button onClick={() => { setOpen(true); setState(""); }}>Ask {first} a question</Button>
        <Button onClick={() => onDone(a.id)}>Mark my part done</Button>
      </div>
    </article>
  );
}

/** "Before this" and "Next" under the greeting, from the newest assignment to this person. */
export function Lead({ a }: { a: Assignment }) {
  const d = new Date(a.at);
  const verb = a.event === "handover" ? "handed you a new build" : "assigned you a step";
  const first = a.steps[0]?.toLowerCase() ?? "the first step";
  return (
    <p style={{ margin: "0 0 4px" }}>
      Before this: {a.assigned_by ?? a.by} {verb} on {Number.isNaN(d.getTime()) ? "an earlier day" : d.toLocaleDateString("en-GB", { weekday: "long" })}{time(a.at) ? ` at ${time(a.at)}` : ""}.
      {" "}Next: open the project and start {first} with Span.
    </p>
  );
}
