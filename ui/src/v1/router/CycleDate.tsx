import { useEffect, useState } from "react";

import { apiGet, apiSend } from "../../api/client";

// FIXE2: the company's cycle date. The server holds it (sh_platform/v1/cy_routes.py); the header shows it discreetly when it is not the real day,
// and Settings > Cycle date lets the administrator or the head of data change it. One window event keeps the two in step.
export interface Cycle { cycle_date: string | null; today: string; real_today: string; pinned: boolean; can_set: boolean }
const EVENT = "sh-cycle-date";

/** "2026-07-31" as "31 Jul 2026". */
export const dayWords = (iso: string): string => {
  const [y, m, d] = iso.split("-").map(Number);
  return y && m && d ? `${d} ${["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m - 1]} ${y}` : iso;
};

/** The company's cycle state; null until read (or when it cannot be read). `save(null)` returns the company to the real day. */
export function useCycle(): [Cycle | null, (day: string | null) => Promise<void>] {
  const [state, setState] = useState<Cycle | null>(null);
  useEffect(() => {
    let live = true;
    apiGet<Cycle>("/api/v1/cycle-date").then((s) => live && setState(s)).catch(() => undefined);
    const on = (e: Event) => setState((e as CustomEvent<Cycle>).detail);
    window.addEventListener(EVENT, on);
    return () => { live = false; window.removeEventListener(EVENT, on); };
  }, []);
  const save = async (day: string | null) => {
    const got = await apiSend<Cycle>("PUT", "/api/v1/cycle-date", { cycle_date: day });
    window.dispatchEvent(new CustomEvent<Cycle>(EVENT, { detail: got }));
  };
  return [state, save];
}

/** Header: "Cycle: 31 Jul 2026", only when the company's day is not the real day. */
export function CycleBadge() {
  const [c] = useCycle();
  if (!c || c.today === c.real_today) return null;
  return <span className="ds-muted" style={{ fontSize: 12 }} title="The company's working date. Reports, checks and due dates run as of this day.">Cycle: {dayWords(c.today)}</span>;
}

/** Settings > Cycle date. */
export default function CycleDateSetting() {
  const [c, save] = useCycle();
  const [day, setDay] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { if (c) setDay(c.today); }, [c]);
  if (!c) return <p className="ds-muted" role="status">Loading.</p>;
  const go = (d: string | null) => save(d).then(() => setError("")).catch(() => setError("That did not go through. Please try again."));
  return (
    <div>
      <p>The cycle date is the company's working day. Reports, checks, intake and due dates run as of this day, so a month-end routine can be walked on any real day.</p>
      <p>{c.pinned ? <>Set to <strong>{dayWords(c.today)}</strong>. The real day is {dayWords(c.real_today)}.</> : <>Not set: the company works on the real day, {dayWords(c.real_today)}.</>}</p>
      {c.can_set ? (
        <p style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <label>Cycle date <input className="ds-input" type="date" value={day} onChange={(e) => setDay(e.target.value)} /></label>
          <button type="button" className="ds-btn ds-btn--primary" disabled={!day || day === c.cycle_date} onClick={() => void go(day)}>Save</button>
          {c.pinned ? <button type="button" className="ds-btn" onClick={() => void go(null)}>Use the real day</button> : null}
        </p>) : <p className="ds-muted">Only the administrator or the head of data can change it.</p>}
      {error ? <p role="alert">{error}</p> : null}
    </div>
  );
}
