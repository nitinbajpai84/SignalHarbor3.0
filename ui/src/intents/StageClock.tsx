import { useCallback, useEffect, useState } from "react";

import { ApiError, apiGet, apiSend } from "../api/client";
import { Button } from "../design";
import "../modules/m1_intent/wall/wall.css";
import "./StageClock.css";
import ExtendDialog from "./ExtendDialog";
import TimeCard, { type TimeCardData } from "./TimeCard";

export interface ClockPart {
  starts: string; ends: string; working_days_total: number; working_days_left: number; hours_left: number;
  percent_left: number; words?: string; state: "not_started" | "on_time" | "at_half" | "at_risk" | "overdue" | "closing" | "closed" | "cancelled"; extensions: number; day_of: number; unit: "days" | "hours";
}
interface Ext { n: number; by: string; at: string; reason: string | null; days: number; scope: string; status: string }
export interface ClockView {
  id: string; state: string; tz: string; started: boolean; box: ClockPart | null; stage: ClockPart | null;
  stages: { key: string; name: string; status: "done" | "current" | "later"; due: string | null }[];
  extensions: { count: number; show_reason: boolean; list: Ext[]; latest: Ext | null };
  is_organiser?: boolean; pending: Ext | null; can_extend: boolean; may_act: boolean; can_decide: boolean;
  approval: { needed: boolean; approver: string }; time_card?: TimeCardData | null; single_stage: boolean; day_choices: number[]; reason_min: number; reason_max: number;
}

function times(n: number): string {
  return n === 1 ? "once" : n === 2 ? "twice" : `${n} times`;
}
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

const t = {
  label: "Stages and time",
  noClock: "No clock yet",
  notStarted: "Not started",
  starts: "Starts when opened",
  step: (n: number, of: number, name: string) => `Step ${n} of ${of}: ${name}`,
  left: (c: ClockPart) => {
    if (c.words) return c.words; // the server's wording (clock.py), the one used on every screen
    if (c.state === "overdue") {
      const h = -c.hours_left;
      return h >= 24 ? `Overdue by ${plural(Math.floor(h / 24), "working day", "working days")}` : `Overdue by ${plural(h, "hour", "hours")}`;
    }
    return c.unit === "hours" ? `${plural(c.hours_left, "hour", "hours")} left` : `${plural(c.working_days_left, "day", "days")} left`;
  },
  dayOf: (c: ClockPart) => `Day ${c.day_of} of ${c.working_days_total}`,
  stageTip: (when: string) => `Stage due ${when}. Working days only.`,
  boxTip: (when: string, n: number) => `Intent ends ${when}. ${n === 0 ? "Not extended." : `Extended ${times(n)}.`} Working days only.`,
  due: (when: string) => `due ${when}`,
  closes: (when: string, over: boolean) => `${over ? "Ended" : "Closes"} ${when}`,
  thisStep: "This step",
  wholeIntent: "Whole intent",
  extend: "Extend",
  closed: "Nothing to extend. The intent is closed.",
  seeAll: "See all",
  hide: "Hide",
  sure: "Are you sure?",
  yes: "Yes",
  no: "No",
  failed: "That did not work. Try again.",
  unavailable: "Not available yet. The clock could not be loaded.",
  extended: (n: number, by: string | null, when: string, why: string | null) => `Extended ${times(n)}${by ? `: ${by}, ${when}${why ? `, ${why}` : ""}` : ""}`,
  waiting: (by: string, days: number, why: string | null) => `${by} asked for ${plural(days, "more working day", "more working days")}${why ? `: ${why}` : ""}. Waiting for approval.`,
  approve: "Approve",
  decline: "Decline",
};

/** "Wed 8 Oct" or, with the time, "Wed 8 Oct 17:00", in the company's time zone. */
export function fmt(iso: string, tz: string, time = false): string {
  if (!iso || Number.isNaN(Date.parse(iso))) return "";
  const o: Intl.DateTimeFormatOptions = { weekday: "short", day: "numeric", month: "short", ...(time ? { hour: "2-digit", minute: "2-digit" } : {}) };
  try {
    return new Date(iso).toLocaleString("en-GB", { ...o, timeZone: tz }).replace(",", "");
  } catch {
    return new Date(iso).toLocaleString("en-GB", { ...o, timeZone: "UTC" }).replace(",", "");
  }
}
const COLOUR: Record<string, string> = { at_half: " sc__chip--amber", at_risk: " sc__chip--red", overdue: " sc__chip--over" };

function Chip({ text, state, tip, label }: { text: string; state: string; tip: string; label?: string }) {
  return <span className={`sc__chip${COLOUR[state] ?? ""}`} title={tip || undefined} tabIndex={0}>{label ? <span className="sc__lbl">{label}: </span> : null}{text}</span>;
}

/** Top of every intent screen: the stages, the stage clock, the time box clock, the closing line, Extend.
 *  The server is the one source of time. `next` is the organiser's next-step button, behind "Are you sure?". */
export default function StageClock({ intentId, next, onChange, draft }: {
  intentId: string;
  next?: { label: string; run: () => Promise<unknown> };
  onChange?: () => void;
  draft?: { days: number; reason: string };
}) {
  const [v, setV] = useState<ClockView | null>(null);
  const [gone, setGone] = useState<string | null>(null);
  const [dialog, setDialog] = useState(false);
  const [all, setAll] = useState(false);
  const [sure, setSure] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const load = useCallback(() => {
    apiGet<ClockView>(`/api/intents/${intentId}/clock`).then(setV).catch((e) => setGone(e instanceof ApiError && (e.status === 403 || e.status === 404) ? "" : t.unavailable));
  }, [intentId]);
  useEffect(() => {
    load();
    const every = window.setInterval(load, 3600000); // recalculated every hour while the page is open
    return () => window.clearInterval(every);
  }, [load]);

  if (gone !== null) return gone ? <p className="sc__note">{gone}</p> : null;
  if (v === null) return null;
  const done = () => { setDialog(false); load(); onChange?.(); };
  const decide = async (decision: "approve" | "decline") => {
    try {
      await apiSend("POST", `/api/intents/${intentId}/extend/${v.pending!.n}/decide`, { decision, comment: "" });
      done();
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : t.failed);
    }
  };
  const go = async () => {
    try {
      await next!.run();
      setSure(false);
      done();
    } catch (e) {
      setSure(false);
      setProblem(e instanceof ApiError ? e.message : t.failed);
    }
  };

  const at = Math.max(0, v.stages.findIndex((s) => s.status === "current"));
  const box = v.box, stage = v.stage, ext = v.extensions;
  const open = v.state !== "closed" && v.state !== "cancelled";
  const day = (iso: string) => fmt(iso, v.tz).replace(/^\w+ /, "");

  return (
    <div className="sc-wrap">
    {v.time_card && open ? <TimeCard intentId={intentId} card={v.time_card} canExtend={v.can_extend} isOrganiser={!!v.is_organiser} onExtend={() => setDialog(true)} /> : null}
    <nav aria-label={t.label} className="ds-card ds-stagebar sc">
      <div className="sc__row">
        <ol className="sc__steps">
          {v.stages.map((s) => (
            <li key={s.key} aria-current={s.status === "current" ? "step" : undefined} title={s.due ? t.due(fmt(s.due, v.tz)) : undefined} tabIndex={0}
              className={`ds-stagebar__stage${s.status === "current" ? " ds-stagebar__stage--now" : s.status === "done" ? " ds-stagebar__stage--done" : ""}`}>{s.name}</li>
          ))}
        </ol>
        {v.stages.length && box && open ? <p className="sc__short">{t.step(at + 1, v.stages.length, v.stages[at]?.name ?? "")}</p> : null}
        {!box && v.stages.length ? <span className="sc__note">{t.starts}</span> : null}
        <div className="sc__clocks">
          {box ? (
            <>
              {stage && Date.parse(stage.ends) === Date.parse(box.ends) ? null : stage ? <Chip text={t.left(stage)} state={stage.state} tip={t.stageTip(fmt(stage.ends, v.tz, true))} label={t.thisStep} /> : open && v.state !== "closing" && v.stages.length && box.state !== "overdue" && !v.stages.some((s) => s.status === "current") ? <Chip text={t.notStarted} state="" tip="" /> : null}
              {open ? <Chip text={box.state === "closing" ? t.left(box) : `${t.left(box)} · ${t.dayOf(box)}`} label={stage && Date.parse(stage.ends) !== Date.parse(box.ends) ? t.wholeIntent : undefined} state={box.state} tip={t.boxTip(fmt(box.ends, v.tz, true), ext.count)} /> : <Chip text={t.left(box)} state="" tip="" />}
            </>
          ) : <Chip text={t.noClock} state="" tip="" />}
        </div>
        {open && v.may_act && v.can_extend ? <Button onClick={() => setDialog(true)}>{t.extend}</Button> : null}
        {!open && v.may_act ? <Button disabled>{t.extend}</Button> : null}
      </div>
      {v.stages.length && box ? <div className="sc__bar" aria-hidden="true"><span style={{ width: `${((at + 1) / v.stages.length) * 100}%` }} /></div> : null}
      {!open && v.may_act ? <p className="sc__note">{t.closed}</p> : null}
      {box && open && box.state !== "closing" ? <p className={`sc__note sc__note--when${box.state === "overdue" ? " sc__note--late" : ""}`}>{t.closes(fmt(box.ends, v.tz, true).replace(/^(\w+) \d+ \w+ /, "$1 "), box.state === "overdue")}</p> : null}
      {ext.latest ? (
        <p className="sc__note">
          {t.extended(ext.count, ext.show_reason ? ext.latest.by : null, day(ext.latest.at), ext.latest.reason)}
          {ext.show_reason && ext.list.length > 0 ? <button type="button" className="sc__link" onClick={() => setAll(!all)}>{all ? t.hide : t.seeAll}</button> : null}
        </p>
      ) : null}
      {all ? (
        <ol className="sc__all">
          {ext.list.map((e) => <li key={e.n}>{`${e.by}, ${day(e.at)}: ${plural(e.days, "working day", "working days")}, ${e.reason ?? ""} (${e.status})`}</li>)}
        </ol>
      ) : null}
      {v.pending && open ? (
        <div className="sc__row">
          <p className="sc__note">{t.waiting(v.pending.by, v.pending.days, v.pending.reason)}</p>
          {v.can_decide ? <><Button variant="primary" onClick={() => void decide("approve")}>{t.approve}</Button><Button onClick={() => void decide("decline")}>{t.decline}</Button></> : null}
        </div>
      ) : null}
      {next && !sure ? <Button variant="primary" onClick={() => setSure(true)}>{next.label}</Button> : null}
      {next && sure ? (
        <div role="alertdialog" aria-label={t.sure} className="sc__sure">
          <span>{t.sure}</span>
          <Button variant="primary" onClick={() => void go()}>{t.yes}</Button>
          <Button onClick={() => setSure(false)}>{t.no}</Button>
        </div>
      ) : null}
      {problem ? <p role="alert" className="sc__err">{problem}</p> : null}
      {dialog ? <ExtendDialog intentId={intentId} view={v} draft={draft} onClose={() => setDialog(false)} onDone={done} /> : null}
    </nav>
    </div>
  );
}
