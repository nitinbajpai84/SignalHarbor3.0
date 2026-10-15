import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";

import { ApiError, apiGet } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { Chip, PageFrame } from "../../design";
import { EventsLink } from "./EventsView";
import { problemViewCopy as t } from "../problemCopy";
import { AlertLine, AsReported, DecisionCard, TriagePanels, act, day } from "./ProblemTriage";
import type { ProblemRecord } from "./problemTypes";
import { AffectedPanel, BiggerPanel, CauseBlock, ClosingBanner, FixBlock, LinkedPanel, Thread, WhatWeKnow } from "./ProblemWork";

// The Problem's stage view at /centre/intent/<id> (specs 41 and 42): triage while it waits for an owner, the working screen after.
const STYLE = `.pv-bar{position:sticky;bottom:0;z-index:2;background:var(--ds-bg,#fff);padding:8px 0}@media (min-width:900px){.pv-bar{position:static;padding:0}}`;

export default function ProblemView() {
  const { intentId = "" } = useParams<{ intentId: string }>();
  const [v, setV] = useState<ProblemRecord | { state: "draft" } | null>(null);
  const [fail, setFail] = useState<"" | "missing" | "error">("");
  const [error, setError] = useState("");
  const load = useCallback(() => {
    setFail("");
    apiGet<ProblemRecord | { state: "draft" }>(`/api/intents/${intentId}/problem`).then(setV, (e: unknown) => setFail(e instanceof ApiError && e.status === 404 ? "missing" : "error"));
  }, [intentId]);
  useEffect(load, [load]);

  if (fail === "missing") return <ScreenState state="empty" message={t.notFound} />;
  if (fail === "error") return <ScreenState state="error" message={t.loadFailed} onRetry={load} />;
  if (v === null) return <ScreenState state="loading" />;
  if (v.state === "draft") return <Navigate to={`/centre/intent/new?type=problem&draft=${intentId}`} replace />;
  const p = v as ProblemRecord;
  const reload = (r?: ProblemRecord) => { if (r) setV(r); else load(); };
  const waiting = p.triage === "waiting" || p.triage === "escalated";
  const content = p.tier === "content";
  const reads = content || !!p.reads; // the reporter, owner, advisers and affected read the work as it is written
  const checks = p.close_checks ?? [];
  const unmet = checks.find((c) => !c.ok);
  const closed = p.state === "closed";
  // one wording for the clock (clock.py's words, as the stage bar and North read it); a closed Problem shows when it closed, never hours left
  const clockText = closed ? (p.closed_at ? t.closedLine(day(p.closed_at, p.tz)) : "") : !p.clock ? t.notStarted : p.clock.state === "overdue" ? (p.clock.words ?? t.pastBox)
    : `${p.clock.words ?? ""}${p.clock.words ? " · " : ""}${t.clock(p.clock.day_of, p.clock.working_days_total, day(p.clock.ends, p.tz))}`;
  const state = p.state === "closed" ? "Closed" : p.state === "closing" ? "Waiting for confirmation" : waiting ? (p.waiting_for ? t.waitingFor(p.waiting_for) : "Waiting for the company admin") : p.owner ? t.owner(p.owner) : t.noOwner;
  const props = { v: p, reload, setError };

  const decide = waiting || p.can.extend || (p.passes?.length ?? 0) > 0;
  return (
    <div className="ds-screen"><PageFrame title={p.title} crumbs={<>Problem{p.short_ref ? ` ${p.short_ref}` : ""} · <Link to="/centre/intent" className="ds-link">{t.back}</Link></>}
      subline={<><Chip>Problem</Chip> <Chip tone="active">{state}</Chip> {clockText && <Chip>{clockText}</Chip>} {p.stage && p.triage === "accepted" && !closed && <Chip>{p.stage}</Chip>}</>}>
      <style>{STYLE}</style>
      <p className="n-muted">{p.reporter ? t.reportedBy(p.reporter, day(p.created_at, p.tz)) : ""}{p.owner ? `. ${t.owner(p.owner)}` : ""}</p>
      {error && <p role="alert" className="state state-error">{error}</p>}
      {p.state === "closing" && <ClosingBanner {...props} />}
      {p.state === "closed" && <p role="status">{t.closed}{p.closed_summary ? ` ${p.closed_summary}` : ""}</p>}
      {p.became && <p>{p.became.may_open ? <Link className="ds-link" to={p.became.state === "draft" ? `/centre/intent/new?type=initiative&draft=${p.became.id}` : `/centre/intent/${p.became.id}`}>{t.became(p.became.title)}</Link> : t.became(p.became.title)}</p>}
      {content && waiting && decide && <DecisionCard {...props} />}
      {content && waiting && <><AsReported v={p} /><TriagePanels v={p} reload={reload} setError={setError} /><AlertLine v={p} reload={() => reload()} /></>}
      {reads && p.triage === "accepted" && (
        <>
          {p.north_banner && <p role="status" className="ds-card" style={{ padding: 12 }}><strong>North.</strong> {p.north_banner}</p>}
          <WhatWeKnow v={p} />
          <CauseBlock {...props} />
          <FixBlock {...props} />
          <AffectedPanel {...props} />
          <Thread {...props} />
          <BiggerPanel v={p} />
          <LinkedPanel v={p} />
          <AlertLine v={p} reload={() => reload()} />
          <AsReported v={p} />
          {decide && <DecisionCard {...props} />}
        </>
      )}
      {!content && <AsReported v={p} />}
      {!content && p.affected && p.affected.length > 0 && <AffectedPanel {...props} />}
      {!content && p.triage === "accepted" && p.fix && <div className="ds-card" style={{ padding: 12 }}><strong>{t.fixLine}:</strong> {p.fix.what ?? p.fix.reason}</div>}
      {content && p.can_resolve?.close && (
        <div className="pv-bar" style={{ textAlign: "right" }}>
          {unmet && <p className="n-muted" role="status">{t.closeNeeds}: {unmet.line}</p>}
          <button type="button" className="ds-btn ds-btn--primary" disabled={!!unmet} onClick={() => void act(`/api/intents/${p.id}/problem/close`, {}, setError, reload)}>{t.closeSend}</button>
        </div>
      )}
      <EventsLink intentId={intentId} />
    </PageFrame></div>
  );
}
