import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, PageFrame, Pill } from "../../design";
import { act, CLOSE_CODES, getCase, MATERIALITY_NAMES, type Action, type Case } from "./api";
import Comments from "../n2/Comments";
import { dueText, kindName, money } from "./CasesPage";
import TallyPanel from "./TallyPanel";

// E4c: one case. A button is shown only when the server says this person may press it.
const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");
const NEEDS_WORDS: Partial<Record<Action, string>> = { send_back: "Reason for sending back", dismiss: "Reason for dismissing", submit: "Explanation to send for check",
  ask_finance: "Who in Finance should look" };
const STATES: Record<string, string> = { new: "New", assigned: "Assigned", investigating: "Being investigated", waiting_check: "Waiting for a check", resolved: "Resolved", rejected: "Dismissed" };
const LABELS: [Action, string][] = [["take", "Take case"], ["explain", "Ask Tally to write this up"], ["submit", "Submit for check"], ["approve", "Approve"],
  ["send_back", "Send back"], ["dismiss", "Dismiss with reason"], ["ask_finance", "Ask Finance"]];

/** `extra` is drawn just above the history (the Action Centre puts "Where is this from?" and the evidence there). */
export default function CasePage({ extra }: { extra?: (c: Case) => ReactNode } = {}) {
  const { caseId = "" } = useParams();
  const [c, setC] = useState<Case | null>(null);
  const [error, setError] = useState("");
  const [asking, setAsking] = useState<Action | null>(null);
  const [note, setNote] = useState("");
  const [code, setCode] = useState("");

  const load = useCallback(() => getCase(caseId).then(setC).catch((e) => setError(plain(e))), [caseId]);
  useEffect(() => { void load(); }, [load]);
  const run = async (a: Action, text = "") => {
    setError("");
    try { setC(await act(caseId, a, text, code)); setAsking(null); setNote(""); setCode(""); } catch (e) { setError(plain(e)); }
  };
  const press = (a: Action) => { if (NEEDS_WORDS[a]) { setNote(a === "submit" ? c?.proposal?.text ?? "" : ""); setAsking(a); } else void run(a); };

  if (!c) return <PageFrame title="Case">{error ? <p role="alert">{error}</p> : <p className="ds-muted" role="status">Loading the case.</p>}</PageFrame>;
  const who = [kindName(c.exception_type), MATERIALITY_NAMES[c.materiality], c.maker_name && `maker ${c.maker_name}`, c.checker_name && `checker ${c.checker_name}`, dueText(c.due)].filter(Boolean).join(" · ");
  return (
    <PageFrame title={`${c.number}: ${c.title}${c.amount != null ? `, ${money(c.amount, c.currency)}` : ""}`}
      crumbs={<Link className="ds-link" to="/centre/desk">All cases</Link>} subline={who}>
      <p><Pill tone="open">{c.state_label ?? STATES[c.state] ?? c.state}</Pill></p>
      {error ? <p role="alert">{error}</p> : null}
      <TallyPanel caseId={caseId} canFile={!!(c.is_owner && c.can.explain)} onFiled={() => void load()} />
      {c.proposal ? <section aria-label="Proposed by Tally" className="ds-card" style={{ padding: 12 }}>
        <h2>Proposed by Tally</h2><p style={{ whiteSpace: "pre-wrap" }}>{c.proposal.text}</p>
        {c.proposal.sources.length ? <p className="ds-muted">Sources: {c.proposal.sources.join("; ")}</p> : null}</section> : null}
      {c.affects.length ? <p>Affects: {c.affects.join("; ")}</p> : null}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "12px 0" }}>
        {LABELS.filter(([a]) => c.can[a]).map(([a, label]) => <Button key={a} variant={a === "approve" ? "primary" : undefined} onClick={() => press(a)}>{label}</Button>)}
      </div>
      {asking ? <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        {asking === "submit" ? <select className="ds-input" aria-label="Closes as" value={code} onChange={(e) => setCode(e.target.value)}>
          {CLOSE_CODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select> : null}
        <input className="ds-input" aria-label={NEEDS_WORDS[asking]} placeholder={NEEDS_WORDS[asking]} value={note} onChange={(e) => setNote(e.target.value)} style={{ flex: "1 1 280px" }} />
        <Button variant="primary" disabled={!note.trim()} onClick={() => run(asking, note.trim())}>Confirm</Button>
        <Button onClick={() => { setAsking(null); setNote(""); }}>Cancel</Button></div> : null}
      {extra ? extra(c) : null}
      {/* CM1 line 5: the case's own thread */}
      <Comments target={{ kind: "case", id: c.id }} eager />
      <section aria-label="History"><h2>History</h2>
        <ol>{c.history.map((h, i) => <li key={`${h.at}:${i}`}>{h.by ? `${h.by}: ` : ""}{h.text}</li>)}</ol></section>
    </PageFrame>
  );
}
