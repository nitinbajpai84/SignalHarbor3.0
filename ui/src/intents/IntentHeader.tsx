import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { Chip } from "../design";

/** What every intent view needs to draw its top: filled from `GET /api/intents/<id>/wall` or, for other views, `headerFromRecord`. */
export interface HeaderInfo {
  id: string;
  title: string;
  purpose: string;
  state?: string | null;
  /** End of the time box (ISO). The clock chip reads it; file 07's own clock replaces it when that lands. */
  ends?: string | null;
  stages: { key: string; name: string; state?: string | null }[];
  people: { invited: number; joined: number | null; initials: string[] };
  frozenAt?: string | null;
}

export const headerCopy = {
  crumbRoot: "Intent Centre",
  untitled: "Untitled intent. The organiser has not named it yet.",
  purposeLead: "What are we here for:",
  noPurpose: "No purpose yet. Add one so people know why they are writing.",
  noClock: "No clock yet",
  closed: "Closed",
  closing: "Closing",
  cancelled: "Cancelled",
  daysLeft: (n: number) => `${n} ${n === 1 ? "day" : "days"} left`,
  overdue: (n: number) => `Overdue by ${n} working ${n === 1 ? "day" : "days"}`,
  noJoined: "Nobody has joined yet.",
  people: (joined: number, invited: number) => (invited > 0 ? `${joined} / ${invited} people` : `${joined} ${joined === 1 ? "person" : "people"}`),
  peopleUnknown: "Not available yet: no seats have been opened.",
  frozen: (when: string) => `Frozen on ${when}`,
  startsWhenOpened: "Starts when opened",
  stageBar: "Stages of this intent",
  step: (n: number, of: number, name: string) => `Step ${n} of ${of}: ${name}`,
};

const DAY = 86_400_000;

/** Working time (Monday to Friday, 24 hours a day, UTC) from a to b in ms; the same sum as clock.py working_seconds. */
function workingMs(a: number, b: number): number {
  let total = 0;
  for (let d = Math.floor(a / DAY) * DAY; d < b; d += DAY) {
    if (![0, 6].includes(new Date(d).getUTCDay())) total += Math.min(b, d + DAY) - Math.max(a, d);
  }
  return total;
}
const n = (k: number, one: string) => `${k} ${one}${k === 1 ? "" : "s"}`;

/** The same words as the stage clock (clock.py): "3 days left", "6 hours left", "Overdue by 1 working day", "No clock yet" while the intent
 *  is a draft or has no end, "Closing" while it closes, "Closed" once it ended: the clock stops. */
export function clockLabel(ends: string | null | undefined, state: string | null | undefined, now = Date.now()): string {
  if (state === "closed") return headerCopy.closed;
  if (state === "cancelled") return headerCopy.cancelled;
  if (state === "closing") return headerCopy.closing;
  const t = ends ? Date.parse(ends) : NaN;
  if (state === "draft" || Number.isNaN(t)) return headerCopy.noClock;
  const left = t > now ? workingMs(now, t) : 0;
  if (left > 0) {
    return left < 2 * DAY ? `${n(Math.ceil(left / 3_600_000), "hour")} left` : headerCopy.daysLeft(Math.ceil(left / DAY));
  }
  const h = Math.max(1, Math.ceil(workingMs(Math.min(t, now), Math.max(t, now)) / 3_600_000));
  return h >= 24 ? headerCopy.overdue(Math.floor(h / 24)) : `Overdue by ${n(h, "hour")}`;
}

/** The close time in UTC until the company profile carries a time zone (ruling 22). */
const closeTime = (iso: string): string => `${new Date(iso).toLocaleString("en-GB", { timeZone: "UTC", weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })} UTC`;

const frozenOn = (iso: string): string => new Date(iso).toLocaleString("en-GB", { timeZone: "UTC", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** Turns a section 3 intent record into header info, for the views that load the record rather than the wall. */
export function headerFromRecord(r: Record<string, any>): HeaderInfo { // eslint-disable-line @typescript-eslint/no-explicit-any
  const p = r.people ?? {};
  return {
    id: r.id, title: r.title ?? "", purpose: r.purpose ?? "", state: r.state, ends: r.time_box?.ends ?? null,
    stages: (r.stages ?? []).map((s: { key: string; state?: string }) => ({ key: s.key, name: s.key.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()), state: s.state })),
    people: { invited: new Set([...(p.participants ?? []), ...(p.observers ?? [])]).size, joined: null, initials: [] },
  };
}

function usePhone(): boolean {
  const [w, setW] = useState(window.innerWidth);
  useEffect(() => {
    const on = () => setW(window.innerWidth);
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return w < 700;
}

/** The stage bar of the intent: its stages in order, the current one lit. Read-only; the wall's own bar below it moves the wall. */
export function IntentStageBar({ stages, state, here }: { stages: HeaderInfo["stages"]; state?: string | null; here: string }) {
  const phone = usePhone();
  const at = Math.max(0, stages.findIndex((s) => s.key === here));
  if (stages.length === 0 || state === "closed" || state === "cancelled") return null; // a finished intent has no current step
  if (phone) return <p data-testid="stage-bar" className="ds-wall__sentence">{headerCopy.step(at + 1, stages.length, stages[at]?.name ?? "")}</p>;
  return (
    <nav data-testid="stage-bar" aria-label={headerCopy.stageBar} className="ds-wall__tools">
      {stages.map((s) => <Chip key={s.key} tone={s.key === here ? "active" : "default"}>{s.name}</Chip>)}
      {state === "draft" ? <span className="ds-wall__sentence">{headerCopy.startsWhenOpened}</span> : null}
    </nav>
  );
}

/** Title, purpose, clock and people of one intent. Every intent view places it at the top; `here` names the view in the crumb. */
export default function IntentHeader({ info, here, stageKey, extra }: { info: HeaderInfo; here: string; stageKey?: string; extra?: ReactNode }) {
  const phone = usePhone();
  const { people } = info;
  const joined = people.joined;
  return (
    <header data-testid="intent-header" className="ds-wall__head" style={{ display: "block" }}>
      <p className="ds-wall__crumb">
        <Link to="/centre/intent">{headerCopy.crumbRoot}</Link> / {info.title ? <Link to={`/centre/intent/${info.id}`}>{info.title}</Link> : headerCopy.untitled} / <strong>{here}</strong>
      </p>
      <h1 data-testid="intent-title" className="ds-wall__title">{info.title || headerCopy.untitled}</h1>
      {phone ? null : (
        <p data-testid="intent-purpose" className="ds-wall__purpose">
          {info.purpose ? <span><strong>{headerCopy.purposeLead}</strong> {info.purpose}</span> : <span>{headerCopy.noPurpose}</span>}
        </p>
      )}
      <div className="ds-wall__stats">
        <span data-testid="intent-clock" title={info.ends ? closeTime(info.ends) : undefined}>{clockLabel(info.ends, info.state)}</span>
        <span data-testid="intent-people">
          {phone || people.initials.length === 0 ? null : <span className="ds-wall__initials">{people.initials.map((i) => <span key={i} aria-hidden="true" className="ds-avatar">{i}</span>)}</span>}
          {joined === null ? headerCopy.peopleUnknown : joined === 0 ? headerCopy.noJoined : headerCopy.people(joined, people.invited)}
        </span>
        {info.frozenAt ? <span data-testid="intent-frozen">{headerCopy.frozen(frozenOn(info.frozenAt))}</span> : null}
        {extra}
      </div>
      {stageKey ? <IntentStageBar stages={info.stages} state={info.state} here={stageKey} /> : null}
    </header>
  );
}
