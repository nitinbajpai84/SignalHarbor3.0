import { useCallback, useEffect, useRef, useState } from "react";

import Icon from "../../../components/Icon";
import ScreenState, { type ScreenStateName } from "../../../components/ScreenState";
import { ApiError, Refused } from "../../../api/client";
import { extendTimer, getTimer, type TimerView } from "../api";
import { m1Timer } from "../copy";

const POLL_MS = 15000;

export function formatLeft(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  if (s >= 172800) return `${Math.round(s / 86400)} days`; // a wall window runs for days: say so, not 7197:29
  if (s >= 3600) return `${Math.round(s / 3600)} hours`;
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

interface Props {
  sessionId: string;
  /** Called when the server says the stage has changed (for example the rooms ended), so the screen can reload. */
  onStageChange?: (stage: string) => void;
  /** Called once when the time left reaches the warning time, so the screen can show Nira's warning. */
  onWarning?: () => void;
  /** Called whenever the time left enters or leaves the warning window (true while inside it). */
  onWarningState?: (inWarning: boolean) => void;
}

/**
 * The stage timer (M1-14). The server decides the time; this shows it, counting down in between short polls.
 * Shown on every timed stage, with the one-minute warning and, for the organiser, the extend control.
 */
export default function StageTimer({ sessionId, onStageChange, onWarning, onWarningState }: Props) {
  const [view, setView] = useState<TimerView | null>(null);
  const [failure, setFailure] = useState<"error" | "refused" | null>(null);
  const [message, setMessage] = useState<string | undefined>(undefined);
  const [fetchedAt, setFetchedAt] = useState(() => Date.now());
  const [now, setNow] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const stage = useRef<string | null>(null);
  const asked = useRef<number>(0);

  const take = useCallback(
    (v: TimerView) => {
      setView(v);
      setFailure(null);
      setFetchedAt(Date.now());
      setNow(Date.now());
      if (stage.current !== null && stage.current !== v.stage) onStageChange?.(v.stage);
      stage.current = v.stage;
    },
    [onStageChange],
  );

  const load = useCallback(() => {
    getTimer(sessionId)
      .then(take)
      .catch((e: unknown) => {
        setMessage(e instanceof ApiError && e.status !== 0 && e.status < 500 ? e.message : undefined);
        setFailure(e instanceof Refused ? "refused" : "error");
      });
  }, [sessionId, take]);

  useEffect(() => {
    load();
    const poll = setInterval(load, POLL_MS);
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      clearInterval(poll);
      clearInterval(tick);
    };
  }, [load]);

  const left = view && view.timed ? Math.max(0, view.remaining_seconds - Math.floor((now - fetchedAt) / 1000)) : 0;
  useEffect(() => {
    // The countdown reached zero: ask the server once what happens next (it may have moved the stage on).
    if (view && view.timed && view.remaining_seconds > 0 && left === 0 && asked.current !== fetchedAt) {
      asked.current = fetchedAt;
      load();
    }
  }, [left, view, fetchedAt, load]);

  const warnKey = view && view.timed && left > 0 && left <= view.warning_seconds ? `${view.stage}:${view.ends_at}` : null;
  const warned = useRef<string | null>(null);
  useEffect(() => {
    // Once per stage end time (an extension moves it, so a new warning can follow).
    if (warnKey !== null && warned.current !== warnKey) {
      warned.current = warnKey;
      onWarning?.();
    }
  }, [warnKey, onWarning]);

  const inWarning = warnKey !== null;
  useEffect(() => {
    onWarningState?.(inWarning);
  }, [inWarning, onWarningState]);

  const extend = (minutes: number) => {
    setBusy(true);
    setNote(null);
    extendTimer(sessionId, minutes)
      .then((v) => {
        take(v);
        setNote(m1Timer.extended);
      })
      .catch((e: unknown) => setNote(e instanceof ApiError && e.status !== 0 && e.status < 500 ? e.message : m1Timer.unavailable))
      .finally(() => setBusy(false));
  };

  const state: ScreenStateName = failure ?? (view === null ? "loading" : view.timed ? "populated" : "empty");
  if (state === "empty") return null;
  return (
    <section className="m1-timer" aria-label={m1Timer.label}>
      <ScreenState state={state} message={state === "error" ? (message ?? m1Timer.unavailable) : state === "refused" ? message : undefined} onRetry={load}>
        {view && view.timed ? (
          <TimerBody view={view} left={left} busy={busy} note={note} onExtend={extend} />
        ) : null}
      </ScreenState>
    </section>
  );
}

function TimerBody(props: {
  view: Extract<TimerView, { timed: true }>;
  left: number;
  busy: boolean;
  note: string | null;
  onExtend: (minutes: number) => void;
}) {
  const { view, left, busy, note, onExtend } = props;
  const over = left === 0;
  const warn = !over && left <= view.warning_seconds;
  const tone = over ? "over" : warn ? "warning" : "running";
  const total = (Date.parse(view.ends_at) - Date.parse(view.started_at)) / 1000; // not a date (or no length): no bar
  const share = Number.isFinite(total) && total > 0 ? Math.min(100, Math.max(0, Math.round(((total - left) / total) * 100))) : null;
  return (
    <div className={`n-panel tight m1-timer-body ${tone}`}>
      <div className="m1-timer-clock" role="timer" aria-label={m1Timer.label}>
        <span className="m1-timer-icon" aria-hidden="true">
          <Icon name="clock" size={20} />
        </span>
        <span className="m1-timer-digits">{formatLeft(left)}</span>
        <span className="n-muted">{m1Timer.label}</span>
      </div>
      {share !== null ? (
        <div className="m1-timer-bar n-room-progress-bar" aria-hidden="true">
          <div className="fill" style={{ width: `${share}%` }} />
        </div>
      ) : null}
      {warn ? (
        <p role="alert" className="m1-timer-flag">
          {m1Timer.warning(view.warning_seconds)}
        </p>
      ) : null}
      {over ? <p role="status" className="m1-timer-flag">{view.may_extend ? m1Timer.overOrganiser : m1Timer.over}</p> : null}
      {view.may_extend ? (
        <div className="m1-timer-extend" role="group" aria-label={m1Timer.extendTitle}>
          {view.extension_minutes.map((m) => (
            <button key={m} type="button" className="n-btn" disabled={busy} onClick={() => onExtend(m)}>
              {busy ? m1Timer.extending : m1Timer.extend(m)}
            </button>
          ))}
        </div>
      ) : null}
      {note ? <p role="status" className="n-muted">{note}</p> : null}
    </div>
  );
}
