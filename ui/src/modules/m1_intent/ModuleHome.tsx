import { Link } from "react-router-dom";

import AgentCard from "../../components/AgentCard";
import PageHead from "../../components/PageHead";
import Panel from "../../components/Panel";
import ScreenState from "../../components/ScreenState";
import StatusPill from "../../components/StatusPill";
import Sticky from "../../components/Sticky";
import { listSessions, type SessionRow } from "./api";
import { m1, m1Look } from "./copy";
import { useLoad } from "./useLoad";

const BASE = "/modules/m1_intent";

function statusOf(state: string): string {
  if (state === "draft") return m1.home.status.draft;
  if (state === "paused") return m1.home.status.paused;
  if (state === "closed") return m1.home.status.closed;
  return m1.home.status.started;
}

function when(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString();
}

/** The earlier Intent Centre's Sessions tab (screens/intent-center.js sessionsTab): each session is a teal sticky with its state and Open. */
function Group({ title, rows }: { title: string; rows: SessionRow[] }) {
  if (rows.length === 0) return null;
  return (
    <Panel title={title} eyebrow={m1Look.sessionsEyebrow} actions={<span className="n-muted">{m1Look.sessionCount(rows.length)}</span>}>
      <ul className="m1-list n-sticky-board">
        {rows.map((s) => (
          <li key={s.id}>
            <Sticky tone="teal" question={s.label}>
              <div className="n-flex wrap">
                <StatusPill tone={s.state === "closed" ? "muted" : s.state === "draft" ? "warning" : "info"}>{statusOf(s.state)}</StatusPill>
              </div>
              <div className="n-muted n-sticky-pain">
                {m1.home.seats(s.seats)} · {m1.home.updated} {when(s.updated_at)}
              </div>
              <Link className="n-btn sm" to={`${BASE}/sessions/${s.id}`}>
                {m1.home.open}
              </Link>
            </Sticky>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

/** The module home: my sessions (drafts, in progress, closed) and the way to prepare a new one. */
export default function ModuleHome() {
  const { state, data, message, retry } = useLoad(listSessions, "sessions", (rows) => rows.length === 0);
  const rows = data ?? [];
  return (
    <>
      <PageHead
        title={m1.home.title}
        sub={m1.home.intro}
        crumbs={[{ label: m1Look.crumbModules, to: "/" }, { label: m1Look.crumbSessions }]}
        actions={
          <Link className="n-btn primary" to={`${BASE}/prepare`}>
            {m1.home.prepare}
          </Link>
        }
      />
      <ScreenState state={state} onRetry={retry} message={state === "empty" ? m1.home.empty : message}>
        <Group title={m1.home.drafts} rows={rows.filter((s) => s.state === "draft")} />
        <Group title={m1.home.inProgress} rows={rows.filter((s) => s.state !== "draft" && s.state !== "closed")} />
        <Group title={m1.home.closed} rows={rows.filter((s) => s.state === "closed")} />
      </ScreenState>
      {state === "empty" ? <p className="n-muted">{m1.home.soloHint}</p> : null}
      <Panel eyebrow={m1Look.helpEyebrow} title={m1Look.helpTitle} className="m1-help-panel">
        <div className="n-roster-grid">
          <AgentCard
            name="North"
            status="idle"
            work={m1Look.north.work}
            may={[...m1Look.north.may]}
            mayNot={[...m1Look.north.mayNot]}
            mayLabel={m1Look.mayLabel}
            mayNotLabel={m1Look.mayNotLabel}
          />
          <AgentCard
            name="Nira"
            status="idle"
            work={m1Look.nira.work}
            may={[...m1Look.nira.may]}
            mayNot={[...m1Look.nira.mayNot]}
            mayLabel={m1Look.mayLabel}
            mayNotLabel={m1Look.mayNotLabel}
          />
        </div>
      </Panel>
    </>
  );
}
