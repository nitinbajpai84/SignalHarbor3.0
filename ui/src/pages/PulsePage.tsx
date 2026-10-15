import { useCallback, useEffect, useState, type ReactElement, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { apiGet } from "../api/client";
import {
  ActionCard, ActivityIcon, BuildIcon, Button, ChatIcon, CheckIcon, ClockIcon, ConsumeIcon, DatabaseIcon, DataTable, DocumentIcon, EmptyState,
  Footnote, IntentIcon, MapIcon, PageFrame, PenIcon, PeopleIcon, PhoneTabBar, PulseIcon, SideCard, StatCard, StatGrid, Strip, WarningIcon,
} from "../design";
import { shellText } from "../shell/copy";
import { centresFor } from "../shell/roles";
import { pulseText as t, type Layout } from "./pulseCopy";

// The pulse (docs/plan/SHAPES.md section 1, artboards Main, Desk-Organiser, Desk-Data, Desk-Sponsor, Phone-Participant):
// what needs this person today, one click from each card to the exact screen.

type Kind = "invite" | "decision" | "request" | "measure" | "brief" | "ops" | "signature" | "rating" | "clock" | "outcome";
export interface Line { id: string; kind: Kind; title: string; detail: string; href: string; action: string; due: string | null; minutes?: number }
export interface Stat { label: string; value: string | null; note: string | null }
export interface Initiative { name: string; where: string; hurdle: string | null; who: string; href: string }
export interface Pulse {
  date: string;
  person: { name: string; roles: string[] };
  layout?: Layout;
  minutes: number | null;
  strips: { key: string; lines: Line[] }[];
  more?: number;
  map: { new_this_week: string[]; owned_changes: number; owned_new?: number };
  panels?: { quarter?: Stat[]; ops_report?: Stat[]; watch?: Stat[]; initiatives?: Initiative[]; drafts?: Record<string, number> };
}

const ICON: Record<Kind, () => ReactElement> = {
  invite: () => <PeopleIcon />, decision: () => <CheckIcon />, request: () => <DatabaseIcon />, measure: () => <ActivityIcon />,
  brief: () => <DocumentIcon />, ops: () => <WarningIcon />, signature: () => <PenIcon />,
  rating: () => <CheckIcon />, clock: () => <ClockIcon />, outcome: () => <DocumentIcon />,
};
const STRIP_ICON: Record<string, () => ReactElement> = { start: () => <ChatIcon />, running: () => <ClockIcon />, waiting: () => <WarningIcon /> };
const TAB_ICON: Record<string, () => ReactElement> = {
  pulse: () => <PulseIcon />, intent: () => <IntentIcon />, build: () => <BuildIcon />, consume: () => <ConsumeIcon />, map: () => <MapIcon />,
};

const due = (d: string | null): string | undefined =>
  d ? `Due ${new Date(`${d}T00:00:00`).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}` : undefined;

function Card({ line, strip, inset = false }: { line: Line; strip: string; inset?: boolean }) {
  const icon = (STRIP_ICON[strip] ?? ICON[line.kind] ?? ICON.brief)();
  return <ActionCard icon={icon} title={line.title} detail={line.detail} due={due(line.due)} action={line.action} href={line.href}
    tone={t.amber.has(strip) ? "amber" : "teal"} inset={inset} />;
}

/** A counter: a missing figure says so in words, never a zero. */
function Count({ s, bare = false }: { s: Stat; bare?: boolean }) {
  return s.value === null
    ? <StatCard bare={bare} label={s.label} value={t.notYet} text tone="muted" />
    : <StatCard bare={bare} label={s.label} value={s.value} note={s.note ?? undefined} valueTone={t.warnWhenAny.has(s.label) && s.value !== "0" ? "warn" : undefined} />;
}

/** A Watch line as a figure card: the line's title is the sentence, the whole card is the link. */
function WatchCard({ line }: { line: Line }) {
  const brief = line.kind === "brief";
  return <StatCard href={line.href} label={t.watchLabel[line.kind] ?? line.action} value={line.title} text
    note={brief ? t.outside : line.detail || undefined} tone={brief ? "muted" : "warn"} />;
}

// A schematic of the map's shape for the side card (artboards): no data, so it never shows a figure.
type G = { x: number; y: number; c: string; sq?: boolean };
const GREY = "var(--ds-node-grey)", AMBER = "var(--ds-amber)", TEAL = "var(--ds-teal-bright)", INK = "var(--ds-ink)";
const GLYPH: Record<Layout, { nodes: G[]; edges: [number, number, boolean?][] }> = {
  participant: {
    nodes: [{ x: 22, y: 20, c: AMBER }, { x: 22, y: 55, c: AMBER }, { x: 22, y: 90, c: AMBER }, { x: 120, y: 38, c: TEAL }, { x: 120, y: 80, c: TEAL },
      { x: 218, y: 22, c: GREY, sq: true }, { x: 218, y: 62, c: GREY, sq: true }, { x: 218, y: 98, c: INK }],
    edges: [[0, 3], [1, 3], [2, 4], [3, 5], [3, 6], [4, 6], [4, 7]],
  },
  data: {
    nodes: [{ x: 20, y: 58, c: TEAL }, { x: 100, y: 22, c: GREY, sq: true }, { x: 170, y: 22, c: GREY, sq: true }, { x: 100, y: 94, c: AMBER, sq: true },
      { x: 170, y: 94, c: GREY, sq: true }, { x: 240, y: 58, c: INK }],
    edges: [[0, 1], [1, 2], [2, 5], [0, 3], [3, 4, true], [4, 5]],
  },
  sponsor: {
    nodes: [{ x: 22, y: 30, c: TEAL, sq: true }, { x: 22, y: 86, c: TEAL, sq: true }, { x: 120, y: 18, c: AMBER }, { x: 120, y: 58, c: AMBER }, { x: 120, y: 98, c: AMBER },
      { x: 218, y: 30, c: INK }, { x: 218, y: 86, c: INK }],
    edges: [[0, 2], [0, 3], [1, 3], [1, 4], [2, 5], [3, 5], [3, 6], [4, 6]],
  },
  organiser: { nodes: [], edges: [] },
};
GLYPH.organiser = GLYPH.participant;
// The legend's marker colour and shape per label, as on the artboards.
const KEY: Record<Layout, [string | undefined, boolean][]> = {
  participant: [[undefined, false], [TEAL, false], [GREY, true], [INK, false]],
  organiser: [[undefined, false], [TEAL, false], [GREY, true], [INK, false]],
  data: [[TEAL, false], [GREY, true], [AMBER, true], [INK, false]],
  sponsor: [[TEAL, true], [AMBER, false], [INK, false]],
};

function MapGlyph({ layout, small = false }: { layout: Layout; small?: boolean }) {
  const { nodes, edges } = GLYPH[layout];
  const legend = t.map.legend[layout];
  return (
    <>
      <svg viewBox="0 0 260 116" role="img" aria-label={t.map.title} style={{ width: small ? 64 : "100%", height: "auto", display: "block" }}>
        {edges.map(([a, b, dash], i) => (
          <line key={i} x1={nodes[a]!.x} y1={nodes[a]!.y} x2={nodes[b]!.x} y2={nodes[b]!.y} style={{ stroke: dash ? AMBER : "var(--ds-line-2)", strokeWidth: 1.5, strokeDasharray: dash ? "4 3" : undefined }} />
        ))}
        {nodes.map((n, i) => n.sq
          ? <rect key={i} x={n.x - 8} y={n.y - 8} width={16} height={16} rx={3} style={{ fill: n.c }} />
          : <circle key={i} cx={n.x} cy={n.y} r={8} style={{ fill: n.c }} />)}
      </svg>
      {!small && (
        <p style={{ display: "flex", flexWrap: "wrap", gap: "4px 14px", fontSize: 12 }}>
          {legend.map((l, i) => { const [c, sq] = KEY[layout][i] ?? [undefined, false]; return <span key={l} style={{ color: c }}>{sq ? "■" : "●"} {l}</span>; })}
        </p>
      )}
    </>
  );
}

/** True under 480px, where the artboards drop the side cards and the date (design.css switches the tab bar on at the same width). */
function usePhone(): boolean {
  const q = typeof window.matchMedia === "function" ? window.matchMedia("(max-width: 480px)") : null;
  const [phone, setPhone] = useState(q?.matches ?? false);
  useEffect(() => {
    if (!q) return;
    const on = () => setPhone(q.matches);
    q.addEventListener("change", on);
    return () => q.removeEventListener("change", on);
  }, [q]);
  return phone;
}

/** The summary line: what needs this person (the Watch strip is for looking, not acting). Data team and sponsor read it as kinds of work. */
function summarise(pulse: Pulse, layout: Layout): string {
  const act = pulse.strips.filter((s) => s.key !== "watch");
  const all = act.flatMap((s) => s.lines);
  if (!all.length) return "";
  const minutes = all.reduce((n, l) => n + (l.minutes ?? 0), 0) || null;
  if (layout === "data" || layout === "sponsor") {
    const counts = new Map<number, number>();
    for (const l of all) { const i = t.kinds.findIndex((k) => k.test(l.id, l.kind)); counts.set(i, (counts.get(i) ?? 0) + 1); }
    const parts = [...counts].sort((a, b) => a[0] - b[0]).map(([i, n]) => `${n} ${n === 1 ? t.kinds[i]!.one : t.kinds[i]!.many}`);
    return [...parts, t.minutes(minutes)].filter(Boolean).join(" · ");
  }
  const drafted = layout === "organiser" && act.every((s) => ["start", "running", "waiting"].includes(s.key));
  return t.summary(all.length, minutes) + (drafted ? ` · ${t.drafted}` : "");
}

export default function PulsePage() {
  const [pulse, setPulse] = useState<Pulse | null>(null);
  const [failed, setFailed] = useState(false);
  const phone = usePhone();

  const load = useCallback(() => {
    setFailed(false);
    apiGet<Pulse>("/api/pulse").then(setPulse).catch(() => setFailed(true));
  }, []);
  useEffect(load, [load]);

  if (!pulse) {
    return (
      <div className="ds-screen">
        <PageFrame title={t.dayTitle} subline={failed ? undefined : <span role="status">{t.reading}</span>}>
          {failed && <><EmptyState title={t.error} lines={[t.errorLine]} /><div><Button variant="primary" onClick={load}>{t.retry}</Button></div></>}
        </PageFrame>
      </div>
    );
  }

  const layout: Layout = pulse.layout ?? "participant";
  const panels = pulse.panels ?? {};
  const strips = new Map(pulse.strips.filter((s) => s.lines.length > 0).map((s) => [s.key, s.lines]));
  const summary = summarise(pulse, layout);
  const date = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
  const first = pulse.person.name.split(/\s+/)[0] || pulse.person.name;
  const mine = centresFor(pulse.person.roles);
  const bar = shellText.bar.filter((c) => mine.has(c.id) && c.id !== "control");

  const section = (key: string): ReactNode => {
    const lines = strips.get(key) ?? [];
    const label = t.strips[key] ?? key;
    const tone = t.amber.has(key) ? "amber" : "teal";
    if (key === "ops") {
      const report = panels.ops_report ?? [];
      if (!report.length && !lines.length) return null;
      return (
        <Strip key={key} label={label} tone={tone}>
          <div className="ds-card ds-side">
            {report.length > 0 && <StatGrid cols={4}>{report.map((s) => <Count key={s.label} s={s} bare />)}</StatGrid>}
            {lines.map((l) => <Card key={l.id} line={l} strip={key} inset />)}
          </div>
        </Strip>
      );
    }
    if (key === "quarter") {
      const q = panels.quarter ?? [];
      return q.length ? <Strip key={key} label={label}><StatGrid cols={4}>{q.map((s) => <Count key={s.label} s={s} />)}</StatGrid></Strip> : null;
    }
    if (key === "initiatives") {
      const rows = panels.initiatives ?? [];
      return rows.length ? (
        <Strip key={key} label={label}>
          <DataTable columns={t.table} rows={rows.map((r) => ({
            name: <Link to={r.href} className="ds-link"><strong>{r.name}</strong></Link>, where: r.where,
            hurdle: r.hurdle ? <span className="ds-warn">{r.hurdle}</span> : t.none, who: r.who,
          }))} />
        </Strip>
      ) : null;
    }
    if (key === "watch") {
      const stats = panels.watch ?? [];
      if (!stats.length && !lines.length) return null;
      return (
        <Strip key={key} label={label}>
          <StatGrid>{stats.map((s) => <Count key={s.label} s={s} />)}{lines.map((l) => <WatchCard key={l.id} line={l} />)}</StatGrid>
        </Strip>
      );
    }
    return lines.length ? <Strip key={key} label={label} tone={tone}>{lines.map((l) => <Card key={l.id} line={l} strip={key} />)}</Strip> : null;
  };

  const drafts = Object.entries(panels.drafts ?? {}).filter(([, n]) => n > 0);
  const fresh = pulse.map.new_this_week;
  const mapNew = fresh.length ? (
    <>
      <p><strong>{t.map.newWeekTitle}</strong></p>
      <ul>{t.map.newWeekItems(fresh).map((n) => <li key={n}>{n}</li>)}</ul>
      {t.map.newWeekMore(fresh) && <p>{t.map.newWeekMore(fresh)}</p>}
      {t.map.owned(pulse.map.owned_new ?? 0) && <p>{t.map.owned(pulse.map.owned_new ?? 0).trim()}</p>}
    </>
  ) : <p>{t.map.none}</p>;
  const aside = phone ? (layout === "participant" || layout === "data") && (
    <Link to="/centre/intent/graph" className="ds-card ds-side" style={{ flexDirection: "row", alignItems: "center", gap: 14 }}>
      <MapGlyph layout={layout} small />
      <span><strong className="ds-side__title">{t.map.title}</strong><p>{t.phoneMap[layout]}</p></span>
    </Link>
  ) : (
    <>
      <SideCard title={t.map.title} action={{ label: t.map.openLabel[layout], href: "/centre/intent/graph" }}>
        <p>{t.map.body[layout]}</p>
        <MapGlyph layout={layout} />
        {layout !== "data" && layout !== "sponsor" && mapNew}
      </SideCard>
      {layout === "organiser" && drafts.length > 0 && (
        <SideCard title={t.drafts.title}>
          <p>{drafts.map(([k, n]) => `${n} ${(t.drafts.kinds[k] ?? [k, k])[n === 1 ? 0 : 1]}`).join(" · ")}</p>
        </SideCard>
      )}
      {layout === "data" && <SideCard title={t.buildOnly.title}><p>{t.buildOnly.body}</p></SideCard>}
      {layout === "sponsor" && (
        <SideCard title={t.ask.title}><p>{t.ask.body}</p><Link to="/centre/intent" className="ds-link">{t.ask.link}</Link></SideCard>
      )}
      {layout === "participant" && (
        <SideCard title={t.memory.title}><p>{t.memory.body}</p><Link to="/centre/memory" className="ds-link">{t.memory.link}</Link></SideCard>
      )}
      <Footnote>{t.footer[layout]}</Footnote>
    </>
  );

  return (
    <div className="ds-screen">
      <PageFrame title={t.greeting(new Date().getHours(), first)} subline={[phone ? "" : date, summary].filter(Boolean).join(" · ")} aside={aside}>
        {!summary && (
          <EmptyState title={t.nothing} lines={[t.nothingLine]}
            links={bar.filter((c) => c.id !== "pulse").map((c) => ({ label: t.centres[c.id] ?? c.label, href: c.to }))} />
        )}
        {t.order[layout].map(section)}
        {pulse.more ? (
          <p className="ds-muted">
            <Link to="/centre/intent#your-turn" className="ds-link">And {pulse.more} more in the Intent Centre.</Link>
          </p>
        ) : null}
      </PageFrame>
      <PhoneTabBar items={bar.map((c) => ({ label: t.tabs[c.id] ?? c.label, href: c.to, icon: TAB_ICON[c.id]?.(), active: c.id === "pulse" }))} />
    </div>
  );
}
