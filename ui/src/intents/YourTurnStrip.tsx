import { useEffect, useState, type ReactElement } from "react";

import { apiGet } from "../api/client";
import Panel from "../components/Panel";
import ScreenState from "../components/ScreenState";
import { useLoad } from "../components/useLoad";
import { ActionCard, CheckIcon, Chip, ClockIcon, DocumentIcon, PenIcon, PeopleIcon } from "../design";
import { yourTurnCopy as t } from "./yourTurnCopy";

// Nira's whole list for the signed-in person (spec 45, screen A). Built fresh on every read from the intent records: no tick, no snooze, no dismiss.
export interface TurnLine {
  id: string; kind: string; title: string; detail: string; href: string; action: string; due: string | null; group: "Signature" | "Decision" | "Question" | "Rating";
}
type Filter = keyof typeof t.filters;
const MATCH: Record<Filter, (l: TurnLine) => boolean> = {
  all: () => true, decide: (l) => l.group === "Signature" || l.group === "Decision", question: (l) => l.group === "Question", rating: (l) => l.group === "Rating",
};
const ICON: Record<string, () => ReactElement> = { invite: () => <PeopleIcon />, signature: () => <PenIcon />, decision: () => <CheckIcon />, clock: () => <ClockIcon />, request: () => <PeopleIcon /> };
const MORE = 3; // the strip is collapsed to the top three at every width (spec 04)

const day = (iso: string): string => new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
const dueText = (d: string | null): string | undefined => {
  if (!d) return undefined;
  return d < new Date().toISOString().slice(0, 10) ? t.overdue(day(d)) : t.due(day(d));
};

function useNarrow(): boolean {
  const q = typeof window !== "undefined" && window.matchMedia ? window.matchMedia("(max-width: 640px)") : null;
  const [narrow, setNarrow] = useState(q?.matches ?? false);
  useEffect(() => {
    if (!q) return;
    const on = () => setNarrow(q.matches);
    q.addEventListener("change", on);
    return () => q.removeEventListener("change", on);
  }, [q]);
  return narrow;
}

export default function YourTurnStrip() {
  const { state, data, retry } = useLoad(() => apiGet<{ lines: TurnLine[]; count: number }>("/api/intents/waiting"), "your-turn", (d) => d.lines.length === 0);
  const [filter, setFilter] = useState<Filter>("all");
  const [expanded, setExpanded] = useState(false);
  const narrow = useNarrow();
  const lines = data?.lines ?? [];
  const shown = lines.filter(MATCH[filter]);
  const rows = !expanded ? shown.slice(0, MORE) : shown;
  const say = state === "loading" ? t.loading : state === "empty" ? t.empty : t.error;
  return (
    <Panel title={t.heading} label="Your turn" className="n-yourturn" actions={state === "populated" ? <span className="n-muted">{t.count(lines.length)}</span> : undefined}>
      <span id="your-turn" />
      <ScreenState state={state === "refused" ? "error" : state} message={say} onRetry={retry}>
        {lines.length >= 4 && (
          <div className="n-yourturn-filter" role="group" aria-label="Filter">
            {(Object.keys(t.filters) as Filter[]).map((k) => <Chip key={k} tone={k === filter ? "active" : "default"} onClick={() => setFilter(k)}>{t.filters[k]}</Chip>)}
          </div>
        )}
        <div className="n-yourturn-list" style={{ display: "grid", gap: 10, gridTemplateColumns: narrow ? "1fr" : "repeat(auto-fill, minmax(340px, 1fr))" }}>
          {rows.map((l) => (
            <ActionCard key={l.id} icon={(ICON[l.kind] ?? (() => <DocumentIcon />))()} title={l.title} detail={l.detail} due={dueText(l.due)} action={l.action} href={l.href} />
          ))}
        </div>
        {shown.length > MORE && !expanded && <button type="button" className="n-btn" onClick={() => setExpanded(true)}>{t.showAll(shown.length)}</button>}
      </ScreenState>
    </Panel>
  );
}
