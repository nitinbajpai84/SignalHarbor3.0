import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, PageFrame, Pill } from "../../design";
import { comment, delegate, downloadLog, getPeople, getTicket, setState, STATE_NAMES, work, type Ticket } from "./api";

// T2: one ticket: its body, links that open the exact line (or show the lock), the actions, and the audit log in plain words.
const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");
const AGENTS = ["north", "span", "flow", "lumen", "watcher", "nira"];

export default function TicketPage() {
  const { id = "" } = useParams();
  const [t, setT] = useState<Ticket | null>(null);
  const [error, setError] = useState("");
  const [to, setTo] = useState("");
  const [note, setNote] = useState("");
  const [names, setNames] = useState<string[]>([]);

  const load = useCallback(() => getTicket(id).then(setT).catch((e) => setError(plain(e))), [id]);
  useEffect(() => { void load(); getPeople().then((p) => setNames(p.people)).catch(() => undefined); }, [load]);
  const act = async (fn: () => Promise<Ticket>) => { setError(""); try { setT(await fn()); setNote(""); setTo(""); } catch (e) { setError(plain(e)); } };

  if (!t) return <PageFrame title="Ticket">{error ? <p role="alert">{error}</p> : <p className="ds-muted" role="status">Loading the ticket.</p>}</PageFrame>;
  const active = t.state !== "resolved" && t.state !== "closed";
  return (
    <PageFrame title={`${t.id}: ${t.title}`} crumbs={<Link className="ds-link" to="/centre/tickets">All tickets</Link>}
      subline={`${t.stage_name}${t.project_title ? `, ${t.project_title}` : ""}. Assigned to ${t.assigned_name}. Raised by ${t.raised_name}.`}
      actions={<Button onClick={() => { void downloadLog(t.id).catch((e) => setError(plain(e))); }}>Export the log (.csv)</Button>}>
      <p><Pill tone={active ? "open" : "signed"}>{STATE_NAMES[t.state]}</Pill> {t.priority === "high" ? <Pill tone="late">High priority</Pill> : null} {t.due ? `Due ${t.due}` : null}</p>
      {t.body ? <p style={{ whiteSpace: "pre-wrap" }}>{t.body}</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {t.links.length ? (
        <section aria-label="Links"><h2>Links</h2><ul>{t.links.map((k) => (
          <li key={`${k.kind}:${k.ref}`}>{k.locked ? <span>{`Locked: ${k.preview ?? k.label}. Ask the project owner for access.`}</span>
            : k.href ? <Link className="ds-link" to={k.href}>{k.label}</Link> : <span>{k.label}</span>}</li>))}</ul></section>
      ) : null}
      {t.can_act ? (
        <section aria-label="Actions"><h2>What next</h2>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <input className="ds-input" aria-label="A note" placeholder="A note (optional)" value={note} onChange={(e) => setNote(e.target.value)} style={{ flex: "1 1 240px" }} />
            {active ? <>
              {t.state !== "in_progress" ? <Button onClick={() => act(() => setState(t.id, "in_progress", note))}>Start</Button> : null}
              {t.state !== "waiting" ? <Button onClick={() => act(() => setState(t.id, "waiting", note))}>Waiting</Button> : null}
              <Button variant="primary" onClick={() => act(() => setState(t.id, "resolved", note))}>Resolve</Button>
              <Button onClick={() => act(() => setState(t.id, "closed", note))}>Close</Button>
              <input className="ds-input" aria-label="Delegate to" placeholder="Delegate to" list="t2-people-page" value={to} onChange={(e) => setTo(e.target.value)} />
              <datalist id="t2-people-page">{names.map((n) => <option key={n} value={n} />)}</datalist>
              <Button disabled={!to.trim()} onClick={() => act(() => delegate(t.id, to.trim(), note))}>Delegate</Button>
              {AGENTS.includes(t.assigned_to) ? <Button onClick={() => act(() => work(t.id))}>Let the agent take it</Button> : null}
            </> : <Button variant="primary" onClick={() => act(() => setState(t.id, "open", note))}>Reopen</Button>}
            <Button disabled={!note.trim()} onClick={() => act(() => comment(t.id, note))}>Add as a comment</Button>
          </div>
        </section>
      ) : null}
      <section aria-label="Audit log"><h2>Audit log</h2>
        <ol>{t.log.map((h, i) => <li key={`${h.at}:${i}`}>{h.text}</li>)}</ol>
      </section>
    </PageFrame>
  );
}
