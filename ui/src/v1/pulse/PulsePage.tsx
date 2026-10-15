import type { ReactElement } from "react";
import { Link, useNavigate } from "react-router-dom";

import { apiGet } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { useLoad } from "../../components/useLoad";
import ProjectAccessCard from "../g1/ProjectAccessCard";
import {
  ActionCard, ActivityIcon, Button, ChatIcon, CheckIcon, Chip, ClockIcon, DocumentIcon, Footnote, MapIcon, PageFrame, PenIcon, PeopleIcon,
  PulseIcon, WarningIcon,
} from "../../design";

// P2 Pulse (/centre/home, replaces X2 Home): what needs the person, their projects today, and what is worth a look. GET /api/v1/pulse.
export interface Card { id: string; kind: string; project: string; pid: string | null; text: string; action: string; href: string; since: string | null }
export interface Moved { code: string; name: string; unit: string | null; period: string; from: number; to: number; change: number | null }
export interface ProjectLine {
  pid: string | null; intent_id: string; title: string; stage: string; on: boolean; href: string;
  last_load: { period: string; state: string; reason: string | null } | null; daily?: { date: string; state: string } | null; moved: Moved | null; open_comments: number; open_tickets: number;
}
export interface LookItem { id: string; kind: string; text: string; href: string | null }
export interface Pulse {
  name: string; seats: { id: string; name: string }[]; may_start: boolean;
  needs_you: { refreshed: string; cards: Card[] }; projects: { refreshed: string; lines: ProjectLine[] }; worth_a_look: { refreshed: string; items: LookItem[] };
}

const ICON: Record<string, () => ReactElement> = {
  thread: () => <PeopleIcon />, sign: () => <PenIcon />, scope: () => <CheckIcon />, loaded: () => <ClockIcon />, comment: () => <ChatIcon />,
  ticket: () => <WarningIcon />, formula: () => <ActivityIcon />,
};
const LOOK_ICON: Record<string, () => ReactElement> = {
  anomaly: () => <PulseIcon />, source: () => <WarningIcon />, document: () => <DocumentIcon />, map_note: () => <MapIcon />,
};
const ROW = { display: "flex", flexWrap: "wrap" as const, gap: 8, alignItems: "center" };
const BAND = { display: "flex", flexDirection: "column" as const, gap: 8, padding: 14 };
const time = (iso: string) => new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;
const pct = (m: Moved) => (m.change === null ? "" : ` (${m.change >= 0 ? "+" : ""}${(m.change * 100).toFixed(1)} %)`);

function Head({ title, refreshed }: { title: string; refreshed: string }) {
  return <span style={{ ...ROW, justifyContent: "space-between" }}><strong>{title}</strong><span className="ds-soft">refreshed {time(refreshed)}</span></span>;
}

function Line({ p }: { p: ProjectLine }) {
  const load = p.last_load ? `${p.last_load.period} ${p.last_load.state === "loaded" ? "loaded" : `not loaded${p.last_load.reason ? `: ${p.last_load.reason}` : ""}`}` : "No load yet";
  return (
    <div style={{ ...ROW, justifyContent: "space-between", borderTop: "1px solid var(--ds-line)", paddingTop: 8 }}>
      <span style={ROW}><Link className="ds-link" to={p.href}>{p.title}</Link><Chip>{p.stage}</Chip>{p.pid && <span className="ds-soft">{p.pid}</span>}</span>
      <span style={ROW} className="ds-soft">
        <span>{load}</span>
        {p.daily && <span>Today: {p.daily.state.replace(/_/g, " ")}</span>}
        {p.moved && <span>{p.moved.name}: {p.moved.to.toLocaleString("en-GB")}{p.moved.unit ? ` ${p.moved.unit}` : ""}{pct(p.moved)}</span>}
        {p.open_comments > 0 && <span>{plural(p.open_comments, "open comment")}</span>}
        {p.open_tickets > 0 && <span>{plural(p.open_tickets, "open ticket")}</span>}
      </span>
    </div>
  );
}

export default function PulsePage() {
  const { state, data, message, retry } = useLoad(() => apiGet<Pulse>("/api/v1/pulse"), "v1-pulse");
  const first = data?.name.split(/\s+/)[0];
  const nav = useNavigate();
  const start = data?.may_start ? <Button variant="primary" onClick={() => nav("/centre/intent")}>Start a project</Button> : undefined;
  return (
    <PageFrame crumbs="Pulse" title={first ? `Pulse, ${first}` : "Pulse"}
      subline={data?.seats.length ? <span style={ROW}>Your seats: {data.seats.map((s) => <Chip key={s.id}>{s.name}</Chip>)}</span> : undefined}
      actions={start}>
      <ScreenState state={state} message={message} onRetry={retry}>
        {data && (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--ds-s3)" }}>
            <section aria-label="Needs you" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <Head title="Needs you" refreshed={data.needs_you.refreshed} />
              <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fill, minmax(min(340px, 100%), 1fr))" }}>
                {data.needs_you.cards.length === 0
                  ? <p className="ds-soft">Nothing needs you now.</p>
                  : data.needs_you.cards.map((c) => c.kind === "access" && c.pid ? (
                    <ProjectAccessCard key={c.id} pid={c.pid} title={c.project} onDone={retry} />
                  ) : (
                    <ActionCard key={c.id} icon={(ICON[c.kind] ?? (() => <DocumentIcon />))()} title={c.project} detail={c.text}
                      due={c.since ? `since ${c.since}` : undefined} action={c.action} href={c.href} />
                  ))}
              </div>
            </section>
            <section aria-label="Your projects today" className="ds-card" style={BAND}>
              <Head title="Your projects today" refreshed={data.projects.refreshed} />
              {data.projects.lines.length === 0 ? <p className="ds-soft">No project yet.</p> : data.projects.lines.map((p) => <Line key={p.intent_id} p={p} />)}
            </section>
            <section aria-label="Worth a look" className="ds-card" style={BAND}>
              <Head title="Worth a look" refreshed={data.worth_a_look.refreshed} />
              {data.worth_a_look.items.length === 0 ? <p className="ds-soft">Nothing unusual.</p> : data.worth_a_look.items.map((i) => (
                <span key={i.id} style={{ ...ROW, borderTop: "1px solid var(--ds-line)", paddingTop: 8 }}>
                  {(LOOK_ICON[i.kind] ?? (() => <ActivityIcon />))()}
                  {i.href ? <Link className="ds-link" to={i.href}>{i.text}</Link> : <span>{i.text}</span>}
                </span>
              ))}
            </section>
            <Footnote>Every line is read from the project's own records: its artefacts and comments, the loads, the figures and the review queue.</Footnote>
          </div>
        )}
      </ScreenState>
    </PageFrame>
  );
}
