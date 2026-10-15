import { useState } from "react";

import { ApiError, apiSend } from "../api/client";
import { Button, Chip } from "../design";
import type { ClockView } from "./StageClock";
import { fmt } from "./StageClock";

/** Monday to Friday, same time of day; the server repeats the sum and is the one that writes. */
function addWorkingDays(from: Date, days: number): Date {
  const d = new Date(from);
  while (d.getUTCDay() === 0 || d.getUTCDay() === 6) d.setUTCDate(d.getUTCDate() + 1);
  while (days > 0) {
    d.setUTCDate(d.getUTCDate() + 1);
    days -= d.getUTCDay() === 0 || d.getUTCDay() === 6 ? 0 : 1;
  }
  return d;
}

const t = {
  title: "Extend the time",
  now: (when: string) => `Now ends ${when}`,
  days: "Extra working days",
  day: (n: number) => `${n} ${n === 1 ? "day" : "days"}`,
  newEnd: (when: string) => `New end ${when}`,
  chooseDays: "Choose how many days",
  reason: "Reason",
  placeholder: "Why more time is needed",
  need: "A reason is needed.",
  short: (n: number) => `The reason needs ${n} to 300 characters.`,
  which: "Which clock",
  whole: "The whole intent",
  stage: "This stage only",
  needs: (who: string) => `This extension needs ${who} to approve.`,
  extend: "Extend",
  ask: (who: string) => `Ask ${who} to approve`,
  notNow: "Not now",
  failed: "The extension could not be saved. Try again.",
};

/** Screen B of spec 07: a modal over the stage bar (a full-screen sheet on a phone). Nothing is written until "Extend". */
export default function ExtendDialog({ intentId, view, draft, onClose, onDone }: {
  intentId: string; view: ClockView; draft?: { days: number; reason: string }; onClose: () => void; onDone: () => void;
}) {
  const [days, setDays] = useState<number | null>(draft?.days ?? null);
  const [reason, setReason] = useState(draft?.reason ?? "");
  const [scope, setScope] = useState<"intent" | "stage">("intent");
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const ends = view.box?.ends ?? "";
  const asking = view.approval.needed;
  const who = view.approval.approver.includes("(") ? (view.approval.approver.split(" ")[0] ?? "") : view.approval.approver;
  const text = reason.trim();
  const valid = days !== null && text.length >= view.reason_min && text.length <= view.reason_max;

  const send = async () => {
    setBusy(true);
    try {
      await apiSend("POST", `/api/intents/${intentId}/time-box/extend`, { days, reason: text, scope: view.single_stage ? "intent" : scope });
      onDone();
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : t.failed);
      setBusy(false);
    }
  };

  return (
    <div className="scx-back">
      <div role="dialog" aria-modal="true" aria-label={t.title} className="ds-card scx">
        <h2>{t.title}</h2>
        <p className="sc__note">{t.now(fmt(ends, view.tz, true))}</p>
        <fieldset className="scx__days">
          <legend className="sc__note">{t.days}</legend>
          {view.day_choices.map((n) => (
            <Chip key={n} tone={days === n ? "active" : "default"} onClick={() => setDays(n)}>{t.day(n)}</Chip>
          ))}
        </fieldset>
        <p className="sc__note" aria-live="polite">{days === null ? t.chooseDays : t.newEnd(fmt(addWorkingDays(new Date(ends), days).toISOString(), view.tz, true))}</p>
        <label className="sc__note">{t.reason}
          <textarea value={reason} placeholder={t.placeholder} maxLength={view.reason_max} onChange={(e) => setReason(e.target.value)} />
        </label>
        {text === "" ? <p className="sc__note">{t.need}</p> : text.length < view.reason_min ? <p className="sc__note">{t.short(view.reason_min)}</p> : null}
        {view.single_stage ? null : (
          <fieldset className="scx__days">
            <legend className="sc__note">{t.which}</legend>
            <Chip tone={scope === "intent" ? "active" : "default"} onClick={() => setScope("intent")}>{t.whole}</Chip>
            <Chip tone={scope === "stage" ? "active" : "default"} onClick={() => setScope("stage")}>{t.stage}</Chip>
          </fieldset>
        )}
        {asking ? <p className="sc__note">{t.needs(view.approval.approver)}</p> : null}
        {problem ? <p role="alert" className="sc__err">{problem}</p> : null}
        <div className="scx__buttons">
          <Button variant="primary" disabled={!valid || busy} onClick={() => void send()}>{asking ? t.ask(who) : t.extend}</Button>
          <Button onClick={onClose}>{t.notNow}</Button>
        </div>
      </div>
    </div>
  );
}
