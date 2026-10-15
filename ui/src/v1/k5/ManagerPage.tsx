import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, PageFrame } from "../../design";
import { WhereFrom } from "../a5/TrailHost";
import { addNote, answerQuestion, day, getChanges, getInbox, getProfile, money, revisedWords, type ChangeItem, type Changes, type Inbox, type Note, type Profile, type TimelineRow } from "./api";
import { FundLine } from "./ManagersInbox";

// K3: Consume > Managers. The research page for one manager: what we hold, what they sent, what we noted, and what changed since we last met.
// Nothing here says whether a manager is good or bad; every line is a dated record with its source.
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");
const LOCKED = ["request", "requested", "denied"];
const KIND_WORD: Record<string, string> = { note: "Note", meeting: "Meeting", question: "Open question" };
type Page = Profile & { can_write?: boolean };
const lateWords = (n?: number) => (n ? `, ${n} business day${n === 1 ? "" : "s"} late` : "");

export function ManagerList() {
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { getInbox().then(setInbox).catch((e) => { setInbox({ as_of: "", due_rule_signed: true, rule_note: null, managers: [] }); setError(plain(e)); }); }, []);
  return (
    <PageFrame title="Managers" subline="Research on the managers you invest with.">
      {error ? <p role="alert">{error}</p> : null}
      {inbox === null ? <p className="ds-muted" role="status">Loading the managers.</p>
        : !inbox.managers.length ? <p className="ds-muted">No managers are set up yet, or none of their funds are open to you.</p>
          : <ul>{inbox.managers.map((m) => <li key={m.manager_id}><Link className="ds-link" to={`/centre/consume/managers/${m.manager_id}`}>{m.name}</Link>{" "}
            <span className="ds-muted">{m.funds.length} fund{m.funds.length === 1 ? "" : "s"}</span></li>)}</ul>}
    </PageFrame>
  );
}

const SAVE_WORD: Record<Note["kind"], string> = { note: "Save the note", meeting: "Save the meeting", question: "Add the question" };

function NoteForm({ id, onSaved }: { id: string; onSaved: () => void }) {
  const [kind, setKind] = useState<Note["kind"]>("note");
  const [text, setText] = useState("");
  const [on, setOn] = useState("");
  const [error, setError] = useState("");
  async function save(e: FormEvent) {
    e.preventDefault(); setError("");
    try { await addNote(id, text, kind, on || undefined); setText(""); setOn(""); onSaved(); } catch (x) { setError(plain(x)); }
  }
  return (
    <form onSubmit={(e) => void save(e)} style={{ display: "grid", gap: 6, margin: "8px 0" }}>
      <label>What kind <select className="ds-input" value={kind} onChange={(e) => setKind(e.target.value as Note["kind"])}>
        <option value="note">Note</option><option value="meeting">Meeting</option><option value="question">Question</option></select></label>
      <label>Add a note<textarea className="ds-input" rows={2} value={text} onChange={(e) => setText(e.target.value)} style={{ width: "100%" }} /></label>
      {kind === "meeting" ? <label>Date of the meeting <input className="ds-input" type="date" value={on} onChange={(e) => setOn(e.target.value)} /></label> : null}
      {error ? <p role="alert">{error}</p> : null}
      <div><Button type="submit" disabled={!text.trim()}>{SAVE_WORD[kind]}</Button></div>
    </form>
  );
}

function WhatChanged({ id, lastMeeting }: { id: string; lastMeeting: string | null }) {
  const [since, setSince] = useState("");
  const [out, setOut] = useState<Changes | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function ask() {
    setError(""); setBusy(true);
    try { setOut(await getChanges(id, since || undefined)); } catch (e) { setError(plain(e)); } finally { setBusy(false); }
  }
  return (
    <section aria-label="What changed">
      <h2>What changed since the last meeting?</h2>
      <p className="ds-muted">{lastMeeting ? `The last meeting on record was on ${day(lastMeeting)}.` : "No meeting is on record yet; pick a date or save a meeting note."}</p>
      <label>Since <input className="ds-input" type="date" value={since} onChange={(e) => setSince(e.target.value)} /></label>{" "}
      <Button variant="primary" disabled={busy} onClick={() => void ask()}>Show what changed</Button>
      {error ? <p role="alert">{error}</p> : null}
      {out ? (
        <div>
          <p role="status"><strong>{out.answer}</strong></p>
          <ul>{out.items.map((i: ChangeItem & { valuation_id?: string }, n) => (
            <li key={n}>{day(i.date)}: {i.text}{" "}
              {i.source.link ? <Link className="ds-chip" to={i.source.link}>{i.source.label}</Link> : <span className="ds-chip">{i.source.label}</span>}
              {i.valuation_id ? <>{" "}<WhereFrom kind="valuation" id={i.valuation_id} /></> : null}</li>))}</ul>
          {out.passages?.length ? <><h3>From the documents</h3>
            <ul>{out.passages.map((p, n) => <li key={n}>&ldquo;{p.text}&rdquo; <span className="ds-chip">{p.file}, lines {p.from} to {p.to}</span></li>)}</ul></> : null}
          {out.note ? <p className="ds-muted">{out.note}</p> : null}
        </div>) : null}
    </section>
  );
}

export default function ManagerPage() {
  const { managerId = "" } = useParams();
  const [p, setP] = useState<Page | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => { getProfile(managerId).then((d) => { setP(d); setError(""); }).catch((e) => setError(plain(e))); }, [managerId]);
  useEffect(load, [load]);

  if (error && !p) return <PageFrame title="Manager"><p role="alert">{error}</p><Link className="ds-link" to="/centre/consume/managers">All managers</Link></PageFrame>;
  if (!p) return <PageFrame title="Manager"><p className="ds-muted" role="status">Loading the manager.</p></PageFrame>;
  const done = async (n: Note) => { try { await answerQuestion(managerId, n.id); load(); } catch (e) { setError(plain(e)); } };
  const openQs = p.questions.filter((q) => q.state === "open");
  return (
    <PageFrame title={p.name} subline="Funds, statements, notes and what changed." crumbs={<Link className="ds-link" to="/centre/consume/managers">All managers</Link>}>
      {error ? <p role="alert">{error}</p> : null}

      <WhatChanged id={managerId} lastMeeting={p.last_meeting} />

      <section aria-label="Funds"><h2>Funds</h2>
        <ul style={{ listStyle: "none", padding: 0 }}>{p.funds.map((f) => <FundLine key={f.fund_id} f={f} where />)}</ul>
      </section>

      <section aria-label="Commitments"><h2>Commitments</h2>
        {p.commitments.rows.length ? (
          <div style={{ overflowX: "auto", maxWidth: "100%" }}><table><thead><tr><th>Fund</th><th>Entity</th><th>Committed</th><th>Called</th><th>Not yet called</th></tr></thead>
            <tbody>{p.commitments.rows.map((c) => (
              <tr key={c.commitment_id}><td>{p.funds.find((f) => f.fund_id === c.fund_id)?.fund_name}</td><td>{c.entity ?? "Not available yet"}</td>
                <td>{money({ amount: c.commitment, currency: c.currency })}</td><td>{money({ amount: c.called, currency: c.currency })}</td>
                <td>{money({ amount: c.uncalled, currency: c.currency })}</td></tr>))}</tbody></table></div>
        ) : <p className="ds-muted">{p.commitments.message ?? "Not available yet."}</p>}
      </section>

      <section aria-label="Statements"><h2>Statements and revisions</h2>
        {p.timeline.length ? (
          <ul>{p.timeline.map((t: TimelineRow) => (
            <li key={t.document_id}><Link className="ds-link" to={`/centre/action/evidence/${t.document_id}`}>{t.fund_name}, valued {day(t.valuation_date)}</Link>{" "}
              <span className="ds-muted">{t.title}: received {day(t.received_at)}, {t.status.replace(/_/g, " ")}{lateWords(t.days_late)}{t.value ? `, ${money(t.value)}` : ""}{t.replaces ? (t.revision ? `, replaces an earlier statement: ${revisedWords(t.revision)}` : ", replaces an earlier statement") : ""}{t.current ? "" : ", replaced by a later one"}</span></li>))}</ul>
        ) : <p className="ds-muted">No statements have arrived yet.</p>}
      </section>

      <section aria-label="Notes"><h2>Notes and meetings</h2>
        {p.notes.length ? <ul>{p.notes.map((n) => <li key={n.id}>{day(n.on)}, {KIND_WORD[n.kind]} by {n.by}: {n.text}</li>)}</ul> : <p className="ds-muted">No notes yet.</p>}
        {p.can_write === false ? null : <NoteForm id={managerId} onSaved={load} />}
      </section>

      <section aria-label="Open questions"><h2>Open questions</h2>
        {openQs.length ? <ul>{openQs.map((q) => <li key={q.id}>{q.text} <span className="ds-muted">asked by {q.by}, {day(q.on)}</span>{" "}
          {p.can_write === false ? null : <Button onClick={() => void done(q)}>Mark answered</Button>}</li>)}</ul> : <p className="ds-muted">No open questions.</p>}
      </section>

      <section aria-label="Diligence documents"><h2>Diligence documents</h2>
        {p.documents.length ? (
          <ul>{p.documents.map((d) => (
            <li key={d.id}>{d.name} <span className="ds-muted">{d.kind}, added {day(d.at)} by {d.uploaded_by}{LOCKED.includes(d.access) ? ", restricted: ask the owner for access" : ""}</span>
              {d.passage ? <blockquote className="ds-muted" style={{ margin: "4px 0 8px 12px" }}>&ldquo;{d.passage}&rdquo;</blockquote> : null}</li>))}</ul>
        ) : <p className="ds-muted">No documents in the library name this manager.</p>}
      </section>
    </PageFrame>
  );
}
