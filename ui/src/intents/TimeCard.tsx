import { useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiGet, apiSend } from "../api/client";
import { Button } from "../design";

export interface TimeCardData { line: string; organiser: string; who_picks: string }

const t = {
  name: "North",
  extend: "Extend the time box",
  close: "Close with what we have",
  cancel: "Cancel this intent",
  remind: "Remind me tomorrow",
  why: "Why are you cancelling it?",
  confirm: "Cancel this intent",
  keep: "Keep it running",
  failed: "That did not work. Try again.",
};

const key = (id: string) => `north-time-card:${id}:${new Date().toISOString().slice(0, 10)}`;
const snoozed = (id: string) => { try { return localStorage.getItem(key(id)) === "1"; } catch { return false; } };

/** Spec 07, screen C: North's time card above the stage bar once the box is at risk or over. Shown to the organiser and sponsor
 *  only (the clock route sends it to no one else). "Remind me tomorrow" hides it in this browser until tomorrow and writes nothing. */
export default function TimeCard({ intentId, card, canExtend, isOrganiser, onExtend }: {
  intentId: string; card: TimeCardData; canExtend: boolean; isOrganiser: boolean; onExtend: () => void;
}) {
  const [gone, setGone] = useState(() => snoozed(intentId));
  const [cancelling, setCancelling] = useState(false);
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  if (gone) return null;
  const hide = () => { try { localStorage.setItem(key(intentId), "1"); } catch { /* the card just comes back on reload */ } setGone(true); };
  const cancel = async () => {
    try {
      const rec = await apiGet<{ version: number }>(`/api/intents/${encodeURIComponent(intentId)}`);
      await apiSend("POST", `/api/intents/${encodeURIComponent(intentId)}/cancel`, { version: rec.version, cancel_reason: reason.trim() });
      window.location.reload();
    } catch (e) {
      setProblem(e instanceof ApiError && e.message ? e.message : t.failed);
    }
  };
  return (
    <section className="ds-card tc" aria-label={t.name} data-testid="time-card">
      <p className="tc__line"><strong>{t.name}:</strong> {card.line}</p>
      <div className="tc__buttons">
        {canExtend ? <Button variant="primary" onClick={onExtend}>{t.extend}</Button> : null}
        <Link className="ds-btn" to={`/centre/intent/${intentId}/close`}>{t.close}</Link>
        <Button onClick={() => setCancelling(true)}>{t.cancel}</Button>
      </div>
      {cancelling ? (
        <div className="tc__cancel">
          <label>{t.why}<textarea value={reason} onChange={(e) => setReason(e.target.value)} /></label>
          <Button variant="primary" disabled={reason.trim().length < 3} onClick={() => void cancel()}>{t.confirm}</Button>
          <Button onClick={() => setCancelling(false)}>{t.keep}</Button>
        </div>
      ) : null}
      <p className="tc__picks">{card.who_picks}</p>
      {isOrganiser ? <button type="button" className="sc__link" onClick={hide}>{t.remind}</button> : null}
      {problem ? <p role="alert" className="sc__err">{problem}</p> : null}
    </section>
  );
}
