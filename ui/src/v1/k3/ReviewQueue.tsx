import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import ScreenState from "../../components/ScreenState";
import { useLoad } from "../../components/useLoad";
import { Button, PageFrame } from "../../design";
import { approveItems, getReview, rejectItem, type Review, type ReviewItem, type ReviewProject } from "./api";
import { day } from "./dates";

// The head of data admits what a finished project made into the verified map. Approve turns it solid for everyone; reject sends it back with the reason.
function Project({ p, can: head, reload, openMap }: { p: ReviewProject; can: boolean; reload: () => void; openMap: (id: string) => void }) {
  const can = head && !p.mine; // maker never checker: whoever built the project does not review what it made
  const waiting = p.items.filter((i) => i.status === "waiting");
  const [pick, setPick] = useState<Set<string>>(new Set(waiting.map((i) => i.id)));
  const [open, setOpen] = useState<string | null>(waiting[0]?.id ?? null);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { setPick(new Set(p.items.filter((i) => i.status === "waiting").map((i) => i.id))); }, [p.items]);
  const cur: ReviewItem | undefined = p.items.find((i) => i.id === open);
  const run = async (f: () => Promise<unknown>) => {
    setBusy(true); setErr(null);
    try { await f(); setReason(""); reload(); } catch (e) { setErr(e instanceof Error ? e.message : "That did not save. Try again."); } finally { setBusy(false); }
  };
  const flip = (id: string) => setPick((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const by = (s: ReviewItem["status"]) => p.items.filter((i) => i.status === s);
  return (
    <section aria-label={p.title} className="ds-card" style={{ padding: 16, display: "grid", gap: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div><h2 style={{ margin: 0, fontSize: 18 }}>{p.title}</h2>
          <div className="ds-muted">Completed {day(p.completed_at)} · owner {p.owner ?? "not named yet"}{p.built_by ? ` · built by ${p.built_by}` : ""}</div></div>
        <Button onClick={() => openMap(p.id)}>How it grew</Button>
      </div>
      <div className="ds-muted">{p.counts.waiting} waiting · {p.counts.approved} approved · {p.counts.sent_back} sent back</div>
      {waiting.length ? (
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-start" }}>
          <div style={{ flex: "1 1 300px", display: "grid", gap: 6 }}>
            {can ? <Button variant="primary" disabled={busy || pick.size === 0} onClick={() => run(() => approveItems([...pick]))}>Approve the {pick.size} selected</Button> : null}
            <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 6 }}>
              {waiting.map((i) => (
                <li key={i.id} className="ds-card" style={{ padding: 8, display: "flex", gap: 8, alignItems: "flex-start", outline: open === i.id ? "2px solid var(--ds-teal-bright)" : "none" }}>
                  {can ? <input type="checkbox" aria-label={`Select ${i.label}`} checked={pick.has(i.id)} onChange={() => flip(i.id)} /> : null}
                  <button type="button" onClick={() => setOpen(i.id)} style={{ all: "unset", cursor: "pointer", display: "block" }}>
                    <div className="ds-footnote" style={{ textTransform: "uppercase", fontSize: 12 }}>New · {i.kind}</div>
                    <strong>{i.label}</strong>
                    <div className="ds-muted" style={{ fontSize: 13 }}>{[i.owner, day(i.at)].filter(Boolean).join(" · ")}</div>
                  </button>
                </li>))}
            </ul>
          </div>
          {cur && cur.status === "waiting" ? (
            <div style={{ flex: "1 1 320px", display: "grid", gap: 10 }} aria-live="polite">
              <div className="ds-footnote">{cur.kind}</div>
              <h3 style={{ margin: 0, fontSize: 17 }}>{cur.label}</h3>
              {cur.sub ? <p style={{ margin: 0 }}>{cur.sub}</p> : null}
              <p className="ds-muted" style={{ margin: 0 }}>Approve and it turns solid on the map for everyone. Reject and it goes back to its owner with your reason.</p>
              {can ? <>
                <label>Reason, if you reject (the owner will see this)
                  <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} style={{ display: "block", width: "100%", font: "inherit", background: "var(--ds-surface)", color: "var(--ds-ink)", border: "1px solid var(--ds-line-2)", borderRadius: 10, padding: 8 }} /></label>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <Button variant="primary" disabled={busy} onClick={() => run(() => approveItems([cur.id]))}>Approve into the verified map</Button>
                  <Button disabled={busy || !reason.trim()} onClick={() => run(() => rejectItem(cur.id, reason))}>Reject and send back</Button>
                </div></> : <p className="ds-muted" style={{ margin: 0 }}>{head ? "You built this project, so another person has to review what it made." : "Only the head of data approves."}</p>}
              {err ? <p role="alert" style={{ margin: 0, color: "var(--ds-red)" }}>{err}</p> : null}
            </div>
          ) : null}
        </div>
      ) : <p style={{ margin: 0 }}>Nothing is waiting for this project.</p>}
      {by("approved").length ? <details><summary>Approved ({by("approved").length})</summary>
        <ul>{by("approved").map((i) => <li key={i.id}>{i.label} <span className="ds-muted">({i.kind.toLowerCase()}) approved by {i.by ?? "the head of data"}, {day(i.decided_at)}</span></li>)}</ul></details> : null}
      {by("sent_back").length ? <details open><summary>Sent back ({by("sent_back").length})</summary>
        <ul>{by("sent_back").map((i) => (
          <li key={i.id}>{i.label}: {i.reason} <span className="ds-muted">sent back by {i.by}, {day(i.decided_at)}</span>{can ? <> <Button disabled={busy} onClick={() => run(() => approveItems([i.id]))}>Approve it after all</Button></> : null}</li>))}</ul></details> : null}
    </section>
  );
}

export default function ReviewQueue() {
  const nav = useNavigate();
  const [n, setN] = useState(0);
  const { state, data, message, retry } = useLoad<Review>(getReview, `k3-review-${n}`, (r) => r.allowed && r.projects.length === 0);
  return (
    <PageFrame title="Waiting to enter the verified map" subline="When a project completes, everything new it made waits here for the head of data. Approve and it turns solid on the map for everyone.">
      <ScreenState state={state} message={state === "empty" ? "No project has completed yet, so nothing is waiting." : message} onRetry={retry}>
        {data && !data.allowed ? <p>The review queue is for the data team.</p> : data ? (
          <div style={{ display: "grid", gap: 16 }}>
            <div className="ds-muted">{data.totals.waiting ?? 0} waiting · {data.totals.approved ?? 0} approved · {data.totals.sent_back ?? 0} sent back</div>
            {data.projects.map((p) => <Project key={p.id} p={p} can={data.can_review} reload={() => setN(n + 1)} openMap={(id) => nav(`/centre/map?project=${encodeURIComponent(id)}`)} />)}
            <div><Button onClick={() => nav("/centre/map")}>See it on the whole company map</Button></div>
          </div>
        ) : null}
      </ScreenState>
    </PageFrame>
  );
}
