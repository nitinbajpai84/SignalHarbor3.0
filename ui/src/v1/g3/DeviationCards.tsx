import { useCallback, useEffect, useState } from "react";

import { apiGet, ApiError, type Me } from "../../api/client";
import { Button, Pill } from "../../design";
import { decide, getDeviations, makeNow, type Deviation } from "./api";

// G4: a deviation as a card: before, after, why, the benchmark rows it would fix. The people it is addressed to (the head of data,
// and the raiser for a business definition) can approve or say "Not this" with a reason; everyone else reads.
const said = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not work. Please try again.");

function Card({ d, iid, me, changed }: { d: Deviation; iid: string; me: string; changed: () => void }) {
  const [declining, setDeclining] = useState(false);
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const mine = d.asks.some((a) => a.name === me) && d.status === "pending" && !d.decisions[me];
  const act = (decision: "approved" | "not approved") => decide(iid, d.id, decision, reason.trim()).then(changed).catch((e: unknown) => setProblem(said(e)));
  return (
    <article className="ds-card" style={{ padding: 12, marginBottom: 8 }} aria-label={`Deviation: ${d.summary}`}>
      <p style={{ margin: 0 }}><strong>{!d.by || d.by === "flow" ? "Span" : d.by} asks to {d.summary}</strong>{" "}
        <Pill tone={d.status === "pending" ? "open" : d.status === "approved" || d.status === "implemented" ? "ok" : "draft"}>{d.status === "pending" ? "Waiting for approval" : d.status}</Pill></p>
      <p style={{ margin: "4px 0" }}><span className="ds-muted">Before: </span>{d.before}</p>
      <p style={{ margin: "4px 0" }}><span className="ds-muted">After: </span>{d.after}</p>
      <p style={{ margin: "4px 0" }}><span className="ds-muted">Why: </span>{d.why}</p>
      <p style={{ margin: "4px 0" }}><span className="ds-muted">Rows it would fix: </span>{d.effect_labels.length ? d.effect_labels.join(", ") : `${d.effect.length} row${d.effect.length === 1 ? "" : "s"}`}</p>
      {Object.entries(d.decisions).map(([n, x]) => <p key={n} className="ds-muted" style={{ margin: "4px 0" }}>{n}: {x.decision}{x.reason ? `, ${x.reason}` : ""}</p>)}
      {mine ? (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <Button variant="primary" onClick={() => void act("approved")}>Approve</Button>
          <Button onClick={() => setDeclining(true)}>Not this</Button>
          {declining ? <>
            <input className="ds-input" aria-label="Why not" value={reason} onChange={(e) => setReason(e.target.value)} style={{ flex: "1 1 200px" }} />
            <Button disabled={!reason.trim()} onClick={() => void act("not approved")}>Send reason</Button></> : null}
        </div>
      ) : d.status === "pending" ? <p className="ds-muted" style={{ margin: 0 }}>Waiting for {d.asks.map((a) => a.name).join(" and ")}.</p> : null}
      {d.status === "approved" ? <div>
        <p className="ds-muted" style={{ margin: "4px 0" }}>Approved, not yet made{d.implement_error ? `: ${d.implement_error}` : ""}.</p>
        <Button onClick={() => void makeNow(iid, d.id).then(changed).catch((e: unknown) => setProblem(said(e)))}>Make it now</Button></div> : null}
      {problem ? <p role="alert" className="ds-warn">{problem}</p> : null}
    </article>
  );
}

export default function DeviationCards({ iid }: { iid: string }) {
  const [me, setMe] = useState("");
  const [list, setList] = useState<Deviation[] | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => { apiGet<Me>("/api/auth/me").then((m) => setMe(m.display_name ?? "")).catch(() => undefined); }, []);
  const reload = useCallback(() => setAttempt((a) => a + 1), []);
  useEffect(() => {
    let live = true;
    getDeviations(iid).then((r) => { if (live) setList(r.deviations); }).catch(() => { if (live) setList([]); });  // no deviations is the usual case
    return () => { live = false; };
  }, [iid, attempt]);
  if (!list?.length) return null;
  return <section aria-label="Deviations"><h2 style={{ margin: "0 0 8px" }}>Deviations</h2>{list.map((d) => <Card key={d.id} d={d} iid={iid} me={me} changed={reload} />)}</section>;
}
