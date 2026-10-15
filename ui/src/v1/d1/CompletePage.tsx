import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { PageFrame, Pill, day } from "../../design";
import StepperShell from "../b9/StepperShell";
import { useProjectTitle } from "../s1/useProjectTitle";
import * as api from "./api";
import type { Summary } from "./api";
import "./d1.css";

// V5 D1: /centre/build/p/:projectId/complete. Design: D5-ProjectComplete. Every line comes from the project's own records; a line is left out when no record says it.
export default function CompletePage() {
  const { projectId = "" } = useParams();
  const title = useProjectTitle(projectId);
  const [s, setS] = useState<Summary | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.getSummary(projectId).then(setS).catch((e) => setError(e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.")); }, [projectId]);
  const p = encodeURIComponent(projectId);
  return (
    <StepperShell pid={projectId} current="dashboards">
      <PageFrame title={s?.complete ? `${s.title || title || "This project"} is live.` : "Not live yet"}
        crumbs={s?.complete ? <span className="ds-eyebrow">PROJECT COMPLETE{s.live_at ? ` · ${day(s.live_at).toUpperCase()}` : ""}</span> : undefined}
        subline={s?.complete ? "Lumen now runs it; you only hear from it when something needs you." : "Press Go live on the delivery step when the channels are approved."}
        actions={<><Link className="ds-btn" to="/centre/map">Open in the map</Link> <Link className="ds-btn" to="/centre/build">Back to Build</Link></>}>
        {error && <p role="alert">{error}</p>}
        {s && <>
          {s.steps && <ol className="d1-steps" aria-label="The four steps">{s.steps.map((x) => <li key={x.n}><small>{x.n} · {x.label.toUpperCase()}</small><strong>{x.who}</strong><span className="d1-note">{x.state ?? "Not recorded"}</span></li>)}</ol>}
          {s.complete && <p className="d1-card" role="note" style={{ margin: 0 }}><strong className="ds-eyebrow">BEFORE THIS</strong>
            Go live was pressed{s.live_at ? ` on ${day(s.live_at)}` : ""}. Lumen switched on the {s.delivered_to.filter((c) => c.live).length === 1 ? "approved channel" : `${s.delivered_to.filter((c) => c.live).length} approved channels`}; each sends at its own next time, and nothing went out at once.</p>}
          {s.verified.length > 0 && <section className="d1-card" aria-label="What was verified"><h3>What was verified</h3>
            <ul className="d1-ticks">{s.verified.map((v) => <li key={v.text}><span>{v.text}{v.by ? `. ${v.by}.` : ""}</span></li>)}</ul></section>}
          <section className="d1-card" aria-label="Delivered to"><h3>Delivered to</h3>
            {s.delivered_to.length ? <ul className="d1-list">{s.delivered_to.map((c) => <li key={c.id} className="d1-row"><strong>{c.label}</strong>{c.title !== c.label && <span>{c.title}</span>}
              <Pill tone={c.live ? "ok" : "draft"}>{c.live ? "Live" : "Approved, not live"}</Pill><span className="d1-note">Approved by {c.approved_by}</span></li>)}</ul>
              : <p>No channel is approved yet.</p>}
            {s.not_approved.length > 0 && <p role="status">{s.not_approved.length === 1 ? "1 channel is" : `${s.not_approved.length} channels are`} still waiting and will not be sent.</p>}</section>
          {s.knowledge && s.knowledge.length > 0 && <section className="d1-card" aria-label="Added to the company knowledge map"><h3>Added to the company knowledge map</h3>
            <p>{s.knowledge.reduce((n, g) => n + g.items.length, 0)} items. {s.knowledge.some((g) => g.items.some((i) => !i.verified)) ? "Each is marked verified only where a record says so. " : "Each is marked verified. "}The next project can reuse them.{" "}
              <Link className="ds-link" to="/centre/map">See them on the map</Link></p>
            <div className="d1-know">{s.knowledge.map((g) => <div key={g.group}><h4>{g.group}</h4>
              <ul className="d1-list">{g.items.map((i) => <li key={i.text} className="d1-row"><span>{i.text}</span>{i.verified && <Pill tone="ok">Verified</Pill>}</li>)}</ul></div>)}</div></section>}
          <p><Link className="ds-link" to={`/centre/build/p/${p}/delivery`}>Back to delivery</Link></p></>}
      </PageFrame>
    </StepperShell>
  );
}
